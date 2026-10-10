"""Harness engine — phase-based orchestration with SSE streaming."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.models import (
    HarnessCompleteEvent,
    HarnessDefinition,
    HarnessErrorEvent,
    HarnessEvent,
    HarnessPhaseErrorEvent,
    HarnessPhaseResultEvent,
    HarnessPhaseStartEvent,
    HarnessStartEvent,
    PhaseDefinition,
    PhaseStatus,
    PhaseType,
    UsageEvent,
)
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.repos import harness_repo

logger = logging.getLogger(__name__)


class HarnessEngine:
    """Walks through phases, dispatching by type, yielding SSE events."""

    def __init__(
        self,
        definition: HarnessDefinition,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        db: AsyncSession,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        self.definition = definition
        self.session_id = session_id
        self.user_id = user_id
        self.project_id = project_id
        self.db = db
        self.cancel_event = cancel_event or asyncio.Event()

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

        current_phase = session.current_phase

        yield HarnessStartEvent(
            session_id=self.session_id,
            harness_type=self.definition.harness_type,
            total_phases=len(self.definition.phases),
        )

        for phase_index in range(current_phase, len(self.definition.phases)):
            if self.cancel_event.is_set():
                await self._set_failed("Cancelled by user")
                yield HarnessErrorEvent(session_id=self.session_id, error="Cancelled")
                return

            phase_def = self.definition.phases[phase_index]

            yield HarnessPhaseStartEvent(
                phase_index=phase_index,
                phase_name=phase_def.name,
                phase_type=phase_def.phase_type,
            )

            try:
                async for event in self._run_phase(phase_index, phase_def, session.config):
                    yield event
            except Exception as e:
                logger.exception("harness_engine.phase_error")
                await self._set_failed(f"Phase '{phase_def.name}' failed: {e}")
                yield HarnessPhaseErrorEvent(
                    phase_index=phase_index,
                    phase_name=phase_def.name,
                    error=str(e),
                )
                yield HarnessErrorEvent(session_id=self.session_id, error=str(e))
                return

        # All phases complete
        from app.models.harness_session import HarnessSessionStatus
        await harness_repo.set_status(self.db, self.session_id, HarnessSessionStatus.completed)
        await self.db.commit()

        # Read claim_id if set by final phase
        session = await harness_repo.get_session(self.db, self.session_id)
        yield HarnessCompleteEvent(
            session_id=self.session_id,
            claim_id=session.claim_id if session else None,
        )

    async def _run_phase(
        self,
        phase_index: int,
        phase_def: PhaseDefinition,
        session_config: dict[str, Any],
    ) -> AsyncGenerator[HarnessEvent, None]:
        if phase_def.phase_type == PhaseType.PROGRAMMATIC:
            async for event in self._run_programmatic(phase_index, phase_def, session_config):
                yield event
        elif phase_def.phase_type == PhaseType.LLM_SINGLE:
            async for event in self._run_llm_single(phase_index, phase_def, session_config):
                yield event
        elif phase_def.phase_type == PhaseType.LLM_BATCH_AGENTS:
            async for event in self._run_decision_match(phase_index, phase_def, session_config):
                yield event
        else:
            raise ValueError(f"Unsupported phase type: {phase_def.phase_type}")

    async def _run_programmatic(
        self,
        phase_index: int,
        phase_def: PhaseDefinition,
        session_config: dict[str, Any],
    ) -> AsyncGenerator[HarnessEvent, None]:
        if not phase_def.executor:
            raise ValueError(f"Programmatic phase '{phase_def.name}' has no executor")

        result = await phase_def.executor(
            db=self.db,
            session_id=self.session_id,
            user_id=self.user_id,
            project_id=self.project_id,
            config=session_config,
        )

        result_str = json.dumps(result) if isinstance(result, dict) else str(result)
        await harness_repo.write_workspace_file(
            self.db, self.session_id, phase_def.workspace_output, result_str,
            internal=phase_def.internal,
        )

        await harness_repo.update_phase(
            self.db, self.session_id, str(phase_index),
            {"status": "completed", "summary": f"Produced {phase_def.workspace_output}"},
            phase_index + 1,
        )
        await self.db.commit()

        # Extract detail string from result for SSE event
        detail = None
        if isinstance(result, dict) and "format" in result:
            fmt = result["format"].upper()
            confidence = result.get("confidence")
            detail = f"Format: {fmt}" + (f" ({int(confidence * 100)}%)" if confidence else "")

        yield HarnessPhaseResultEvent(
            phase_index=phase_index,
            phase_name=phase_def.name,
            status=PhaseStatus.COMPLETED,
            detail=detail,
        )

    async def _run_llm_single(
        self,
        phase_index: int,
        phase_def: PhaseDefinition,
        session_config: dict[str, Any],
    ) -> AsyncGenerator[HarnessEvent, None]:
        from app.harness.agent_runner import build_model, run_structured

        if phase_def.output_schema is None:
            raise ValueError(
                f"LLM_SINGLE phase '{phase_def.name}' has no output_schema; "
                "a structured output type is required."
            )

        context = await build_phase_context(
            db=self.db,
            session_id=self.session_id,
            project_id=self.project_id,
            phase_def=phase_def,
        )
        system_prompt = render_system_prompt(phase_def, context)

        model = build_model(model_name=phase_def.model) if phase_def.model else None

        response = await run_structured(
            output_type=phase_def.output_schema,
            system_prompt=system_prompt,
            user_prompt=f"Process the input for phase: {phase_def.name}",
            model=model,
            phase_name=phase_def.name,
        )

        yield UsageEvent(
            prompt_tokens=response.input_tokens,
            completion_tokens=response.output_tokens,
        )

        # Write validated output to workspace (bare JSON matching the typed schema).
        await harness_repo.write_workspace_file(
            self.db, self.session_id, phase_def.workspace_output, response.output_json,
            internal=phase_def.internal,
        )

        await harness_repo.update_phase(
            self.db, self.session_id, str(phase_index),
            {"status": "completed", "summary": f"Produced {phase_def.workspace_output}"},
            phase_index + 1,
        )
        await self.db.commit()

        yield HarnessPhaseResultEvent(
            phase_index=phase_index,
            phase_name=phase_def.name,
            status=PhaseStatus.COMPLETED,
        )

    async def _run_decision_match(
        self,
        phase_index: int,
        phase_def: PhaseDefinition,
        session_config: dict[str, Any],
    ) -> AsyncGenerator[HarnessEvent, None]:
        from app.config import settings
        from app.harness.matchers.base import get_matcher

        if phase_def.output_schema is None:
            raise ValueError(
                f"LLM_BATCH_AGENTS phase '{phase_def.name}' has no output_schema."
            )

        name = phase_def.matcher or settings.matcher_default or "llm"
        # Unconfigured Jev -> run the whole phase on the LLM path (logged, not silent).
        if name == "jev" and not settings.open_router_api_key:
            logger.warning(
                "Phase '%s' requested matcher=jev but open_router_api_key is unset; "
                "falling back to matcher=llm for the whole phase.",
                phase_def.name,
            )
            name = "llm"

        matcher = get_matcher(name)
        outcome = await matcher.match(
            phase_def=phase_def,
            db=self.db,
            project_id=self.project_id,
            session_id=self.session_id,
        )

        yield UsageEvent(
            prompt_tokens=outcome.input_tokens,
            completion_tokens=outcome.output_tokens,
        )

        await harness_repo.write_workspace_file(
            self.db, self.session_id, phase_def.workspace_output, outcome.output_json,
            internal=phase_def.internal,
        )
        n = len(outcome.output)
        counts = f"fell_back={outcome.fell_back}/{n} residue={outcome.residue}/{n}"
        await harness_repo.update_phase(
            self.db, self.session_id, str(phase_index),
            {"status": "completed",
             "summary": f"Produced {phase_def.workspace_output} (matcher={name} {counts})"},
            phase_index + 1,
        )
        await self.db.commit()

        yield HarnessPhaseResultEvent(
            phase_index=phase_index,
            phase_name=phase_def.name,
            status=PhaseStatus.COMPLETED,
            detail=f"matcher={name} {counts}",
        )

    async def _set_failed(self, error: str) -> None:
        from app.models.harness_session import HarnessSessionStatus
        await harness_repo.set_status(self.db, self.session_id, HarnessSessionStatus.failed, error_message=error)
        await self.db.commit()
