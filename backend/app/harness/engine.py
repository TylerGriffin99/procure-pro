"""Harness engine — phase-based orchestration with SSE streaming."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass, field
from typing import Any, assert_never

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LlmClient
from app.constants.enums import HarnessSessionStatus, MatcherName, PhaseStatus
from app.harness.models import (
    HarnessCompleteEvent,
    HarnessDefinition,
    HarnessErrorEvent,
    HarnessEvent,
    HarnessPhaseErrorEvent,
    HarnessPhaseResultEvent,
    HarnessPhaseStartEvent,
    HarnessStartEvent,
    Matcher,
    PhaseDefinition,
    PhaseOutput,
    PhaseRun,
    PhaseType,
    UsageEvent,
)
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.harness.schemas import FormatDetection
from app.repos import harness_repo

logger = logging.getLogger(__name__)


def describe_error(exc: BaseException) -> str:
    """``"<ExceptionType>: <message>"``, or just the type name when the message is empty."""
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


async def mark_session_failed(db: AsyncSession, session_id: uuid.UUID, error: str) -> None:
    """Roll back any failed transaction first, so the status write cannot hit
    PendingRollbackError."""
    await db.rollback()
    await harness_repo.set_status(db, session_id, HarnessSessionStatus.failed, error_message=error)
    await db.commit()


@dataclass
class HarnessEngine:
    """Walks through phases, dispatching by type, yielding SSE events."""

    definition: HarnessDefinition
    session_id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    db: AsyncSession
    llm: LlmClient = field(kw_only=True)
    matchers: Mapping[MatcherName, Matcher] = field(kw_only=True)
    default_matcher: MatcherName = field(kw_only=True)

    async def run(self) -> AsyncGenerator[HarnessEvent, None]:
        """Execute harness from current_phase, yielding SSE events."""
        claimed = await harness_repo.try_claim_running(self.db, self.session_id)
        if not claimed:
            yield HarnessErrorEvent(session_id=self.session_id, error="Session already running")
            return

        await self.db.commit()

        session = await harness_repo.get_session(self.db, self.session_id)
        if session is None:
            yield HarnessErrorEvent(session_id=self.session_id, error="Session not found")
            return

        yield HarnessStartEvent(
            session_id=self.session_id,
            harness_type=self.definition.harness_type,
            total_phases=len(self.definition.phases),
        )

        for phase_index in range(session.current_phase, len(self.definition.phases)):
            if await self.is_cancelled():
                yield self.cancelled(phase_index)
                return
            phase_def = self.definition.phases[phase_index]
            yield HarnessPhaseStartEvent(
                phase_index=phase_index, phase_name=phase_def.name, phase_type=phase_def.phase_type
            )
            try:
                output = await self.run_phase(phase_def, session.config)
                cancelled = await self.is_cancelled()
                if cancelled:
                    await self.db.rollback()
                else:
                    await self.record_phase_result(phase_index, phase_def, output)
            except Exception as e:
                logger.exception("harness_engine.phase_error")
                await self.set_failed(f"Phase '{phase_def.name}' failed: {describe_error(e)}")
                yield HarnessPhaseErrorEvent(
                    phase_index=phase_index, phase_name=phase_def.name, error=describe_error(e)
                )
                yield HarnessErrorEvent(session_id=self.session_id, error=describe_error(e))
                return
            if cancelled:
                yield self.cancelled(phase_index)
                return
            if output.usage is not None:
                yield output.usage
            yield HarnessPhaseResultEvent(
                phase_index=phase_index, phase_name=phase_def.name, status=PhaseStatus.COMPLETED, detail=output.detail
            )

        completed = await harness_repo.complete_if_running(self.db, self.session_id)
        await self.db.commit()
        if not completed:
            yield self.cancelled(len(self.definition.phases))
            return

        session = await harness_repo.get_session(self.db, self.session_id)
        yield HarnessCompleteEvent(session_id=self.session_id, claim_id=session.claim_id if session else None)

    def cancelled(self, phase_index: int) -> HarnessErrorEvent:
        logger.info("harness_engine.cancelled session=%s at phase %d", self.session_id, phase_index)
        return HarnessErrorEvent(session_id=self.session_id, error="Cancelled")

    async def run_phase(self, phase_def: PhaseDefinition, session_config: dict[str, Any]) -> PhaseOutput:
        match phase_def.phase_type:
            case PhaseType.PROGRAMMATIC:
                return await self.run_programmatic_phase(phase_def, session_config)
            case PhaseType.LLM_SINGLE:
                return await self.run_llm_phase(phase_def)
            case PhaseType.LLM_BATCH_AGENTS:
                return await self.run_matcher_phase(phase_def)
            case _:
                assert_never(phase_def.phase_type)

    async def record_phase_result(self, phase_index: int, phase_def: PhaseDefinition, output: PhaseOutput) -> None:
        await harness_repo.write_workspace_file(
            self.db, self.session_id, phase_def.workspace_output, output.output_json, internal=phase_def.internal
        )
        await harness_repo.update_phase(
            self.db,
            self.session_id,
            str(phase_index),
            {"status": PhaseStatus.COMPLETED, "summary": output.summary},
            phase_index + 1,
        )
        await self.db.commit()

    async def is_cancelled(self) -> bool:
        return await harness_repo.get_status(self.db, self.session_id) == HarnessSessionStatus.failed

    async def run_programmatic_phase(self, phase_def: PhaseDefinition, session_config: dict[str, Any]) -> PhaseOutput:
        if not phase_def.executor:
            raise ValueError(f"Programmatic phase '{phase_def.name}' has no executor")
        result = await phase_def.executor(
            db=self.db,
            session_id=self.session_id,
            user_id=self.user_id,
            project_id=self.project_id,
            config=session_config,
            llm=self.llm,
        )
        return PhaseOutput(
            output_json=result.model_dump_json(exclude_none=True),
            summary=f"Produced {phase_def.workspace_output}",
            detail=result.detail() if isinstance(result, FormatDetection) else None,
        )

    async def run_llm_phase(self, phase_def: PhaseDefinition) -> PhaseOutput:
        if phase_def.output_schema is None:
            raise ValueError(
                f"LLM_SINGLE phase '{phase_def.name}' has no output_schema; a structured output type is required."
            )
        context = await build_phase_context(
            db=self.db, session_id=self.session_id, project_id=self.project_id, phase_def=phase_def
        )
        response = await self.llm.run_structured(
            output_type=phase_def.output_schema,
            system_prompt=render_system_prompt(phase_def, context),
            user_prompt=f"Process the input for phase: {phase_def.name}",
            model_name=phase_def.model,
            phase_name=phase_def.name,
        )
        return PhaseOutput(
            output_json=response.output_json,
            summary=f"Produced {phase_def.workspace_output}",
            usage=UsageEvent(prompt_tokens=response.input_tokens, completion_tokens=response.output_tokens),
        )

    async def run_matcher_phase(self, phase_def: PhaseDefinition) -> PhaseOutput:
        if phase_def.output_schema is None:
            raise ValueError(f"LLM_BATCH_AGENTS phase '{phase_def.name}' has no output_schema.")
        matcher = self.matchers[phase_def.matcher or self.default_matcher]
        outcome = await matcher(
            PhaseRun(phase_def=phase_def, db=self.db, project_id=self.project_id, session_id=self.session_id)
        )
        n = len(outcome.output)
        detail = f"matcher={outcome.matcher} fell_back={outcome.fell_back}/{n} residue={outcome.residue}/{n}"
        return PhaseOutput(
            output_json=outcome.output_json,
            summary=f"Produced {phase_def.workspace_output} ({detail})",
            detail=detail,
            usage=UsageEvent(prompt_tokens=outcome.input_tokens, completion_tokens=outcome.output_tokens),
        )

    async def set_failed(self, error: str) -> None:
        await mark_session_failed(self.db, self.session_id, error)
