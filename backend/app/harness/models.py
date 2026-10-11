from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import MatcherName, PhaseStatus
from app.harness.schemas import ExecutorResult, MatchOutcome
from app.schemas.base import StrictModel


class PhaseType(StrEnum):
    PROGRAMMATIC = "programmatic"
    LLM_SINGLE = "llm_single"
    LLM_BATCH_AGENTS = "llm_batch_agents"


class HarnessType(StrEnum):
    CLAIM_PARSE = "claim_parse"


Executor = Callable[..., Awaitable[ExecutorResult]]


@dataclass
class PhaseDefinition:
    name: str
    description: str
    phase_type: PhaseType
    workspace_output: str
    system_prompt_template: str = ""
    model: str | None = None
    matcher: MatcherName | None = None
    # pydantic-ai output spec for LLM phases: a BaseModel subclass or list[Model].
    output_schema: Any = None
    workspace_inputs: list[str] = field(default_factory=list)
    executor: Executor | None = None
    context_loaders: list[Callable] = field(default_factory=list)  # async (db, project_id, session_id) -> dict
    internal: bool = False


@dataclass(frozen=True)
class PhaseRun:
    phase_def: PhaseDefinition
    db: AsyncSession
    project_id: uuid.UUID
    session_id: uuid.UUID


Matcher = Callable[[PhaseRun], Awaitable[MatchOutcome]]


@dataclass
class HarnessDefinition:
    harness_type: HarnessType
    display_name: str
    description: str
    phases: list[PhaseDefinition]


# --- SSE event models ---


class HarnessErrorEvent(BaseModel):
    type: Literal["harness_error"] = "harness_error"
    session_id: uuid.UUID
    error: str


class HarnessStartEvent(BaseModel):
    type: Literal["harness_start"] = "harness_start"
    session_id: uuid.UUID
    harness_type: HarnessType
    total_phases: int


class HarnessPhaseStartEvent(BaseModel):
    type: Literal["harness_phase_start"] = "harness_phase_start"
    phase_index: int
    phase_name: str
    phase_type: PhaseType


class HarnessPhaseErrorEvent(BaseModel):
    type: Literal["harness_phase_error"] = "harness_phase_error"
    phase_index: int
    phase_name: str
    error: str


class HarnessPhaseResultEvent(BaseModel):
    type: Literal["harness_phase_result"] = "harness_phase_result"
    phase_index: int
    phase_name: str
    status: PhaseStatus
    detail: str | None = None


class HarnessCompleteEvent(BaseModel):
    type: Literal["harness_complete"] = "harness_complete"
    session_id: uuid.UUID
    claim_id: uuid.UUID | None


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    prompt_tokens: int
    completion_tokens: int


class PhaseOutput(StrictModel):
    output_json: str
    summary: str
    detail: str | None = None
    usage: UsageEvent | None = None


HarnessEvent = (
    HarnessErrorEvent
    | HarnessStartEvent
    | HarnessPhaseStartEvent
    | HarnessPhaseErrorEvent
    | HarnessPhaseResultEvent
    | HarnessCompleteEvent
    | UsageEvent
)
