import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ClaimParseFlagResponse(BaseModel):
    id: uuid.UUID
    flag_type: str
    severity: str
    line_item_ref: str | None
    description: str
    expected_value: Decimal | None
    actual_value: Decimal | None
    resolved: bool
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveFlagRequest(BaseModel):
    resolved: bool
