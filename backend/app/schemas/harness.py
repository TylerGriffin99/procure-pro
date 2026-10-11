from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.constants.enums import HarnessSessionStatus, PhaseStatus
from app.harness.models import HarnessDefinition, HarnessType


class HarnessPhaseInfo(BaseModel):
    index: int
    name: str
    phase_type: str
    status: PhaseStatus
    result_summary: str | None = None

    @classmethod
    def from_definition(
        cls, definition: HarnessDefinition, *, current_phase: int, phase_results: dict, status: HarnessSessionStatus
    ) -> list[HarnessPhaseInfo]:
        infos: list[HarnessPhaseInfo] = []
        for i, phase_def in enumerate(definition.phases):
            if status == HarnessSessionStatus.completed:
                phase_status = PhaseStatus.COMPLETED
            elif status == HarnessSessionStatus.failed and i == current_phase:
                phase_status = PhaseStatus.FAILED
            elif str(i) in phase_results:
                phase_status = PhaseStatus.COMPLETED
            elif i == current_phase and status == HarnessSessionStatus.running:
                phase_status = PhaseStatus.RUNNING
            else:
                phase_status = PhaseStatus.PENDING
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
    status: HarnessSessionStatus
    current_phase: int
    phases: list[HarnessPhaseInfo] = []
    claim_id: uuid.UUID | None = None
    error_message: str | None = None
    created_at: datetime

    @classmethod
    def from_session(cls, session: Any, definition: HarnessDefinition | None) -> HarnessSessionResponse:
        dto = cls.model_validate(session, from_attributes=True)
        if definition is None:
            return dto
        phases = HarnessPhaseInfo.from_definition(
            definition, current_phase=dto.current_phase, phase_results=session.phase_results, status=dto.status
        )
        return dto.model_copy(update={"phases": phases})


class HarnessCancelResponse(BaseModel):
    id: uuid.UUID
    status: HarnessSessionStatus


class HarnessRerunResponse(BaseModel):
    harness_session_id: uuid.UUID


class WorkspaceFileResponse(BaseModel):
    file_path: str
    created_at: datetime
    updated_at: datetime | None = None


class WorkspaceFileContentResponse(BaseModel):
    file_path: str
    content: str
