import uuid
from datetime import datetime
from pydantic import BaseModel

from app.harness.models import HarnessType


class HarnessSessionCreate(BaseModel):
    harness_type: HarnessType = HarnessType.CLAIM_PARSE
    config: dict = {}


class HarnessPhaseInfo(BaseModel):
    index: int
    name: str
    phase_type: str
    status: str  # pending, running, completed, failed
    result_summary: str | None = None


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


class WorkspaceFileResponse(BaseModel):
    file_path: str
    created_at: datetime
    updated_at: datetime | None = None


class WorkspaceFileContentResponse(BaseModel):
    file_path: str
    content: str
