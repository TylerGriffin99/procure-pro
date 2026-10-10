from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.harness.models import HarnessDefinition, HarnessType

if TYPE_CHECKING:
    from app.models.harness_session import HarnessSession


class HarnessPhaseInfo(BaseModel):
    index: int
    name: str
    phase_type: str
    status: str  # pending, running, completed, failed
    result_summary: str | None = None

    @classmethod
    def from_definition(
        cls,
        definition: HarnessDefinition,
        *,
        current_phase: int,
        phase_results: dict,
        status: str,
    ) -> list[HarnessPhaseInfo]:
        infos: list[HarnessPhaseInfo] = []
        for i, phase_def in enumerate(definition.phases):
            if status == "completed":
                phase_status = "completed"
            elif status == "failed" and i == current_phase:
                phase_status = "failed"
            elif str(i) in phase_results:
                phase_status = "completed"
            elif i == current_phase and status == "running":
                phase_status = "running"
            else:
                phase_status = "pending"
            infos.append(
                cls(
                    index=i,
                    name=phase_def.name,
                    phase_type=phase_def.phase_type.value,
                    status=phase_status,
                    result_summary=phase_results.get(str(i), {}).get("summary"),
                )
            )
        return infos


class HarnessSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    harness_type: HarnessType
    status: str
    current_phase: int
    phases: list[HarnessPhaseInfo]
    claim_id: uuid.UUID | None = None
    error_message: str | None = None
    created_at: datetime

    @classmethod
    def from_session(
        cls, session: HarnessSession, definition: HarnessDefinition | None
    ) -> HarnessSessionResponse:
        phases = (
            HarnessPhaseInfo.from_definition(
                definition,
                current_phase=session.current_phase,
                phase_results=session.phase_results,
                status=session.status.value,
            )
            if definition
            else []
        )
        return cls(
            id=session.id,
            user_id=session.user_id,
            project_id=session.project_id,
            harness_type=session.harness_type,
            status=session.status.value,
            current_phase=session.current_phase,
            phases=phases,
            claim_id=session.claim_id,
            error_message=session.error_message,
            created_at=session.created_at,
        )


class HarnessCancelResponse(BaseModel):
    id: uuid.UUID
    status: str


class HarnessRerunResponse(BaseModel):
    harness_session_id: uuid.UUID


class WorkspaceFileResponse(BaseModel):
    file_path: str
    created_at: datetime
    updated_at: datetime | None = None


class WorkspaceFileContentResponse(BaseModel):
    file_path: str
    content: str
