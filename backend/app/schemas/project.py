import uuid
from decimal import Decimal

from pydantic import BaseModel


class RetentionTierCreate(BaseModel):
    tier_order: int
    percentage: Decimal
    up_to_amount: Decimal | None = None


class RetentionTierResponse(BaseModel):
    id: uuid.UUID
    tier_order: int
    percentage: Decimal
    up_to_amount: Decimal | None

    model_config = {"from_attributes": True}


class WBSCodeCreate(BaseModel):
    code: str
    description: str
    level: str = "subcategory"
    parent_id: uuid.UUID | None = None
    parent_code: str | None = None
    sort_order: int = 0
    contract_sum: Decimal | None = None


class WBSCodeUpdate(BaseModel):
    code: str | None = None
    description: str | None = None
    level: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None
    contract_sum: Decimal | None = None


class WBSCodeResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str
    level: str
    parent_id: uuid.UUID | None
    sort_order: int
    contract_sum: Decimal | None = None
    in_use: bool = False
    children: list["WBSCodeResponse"] = []

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    project_number: str | None = None
    client_name: str
    client_contact: str | None = None
    contractor_name: str
    contract_sum: Decimal
    gst_rate: Decimal = Decimal("0.15")
    end_client_name: str | None = None
    end_client_representative: str | None = None
    end_client_address: str | None = None
    landlord_split_pct: Decimal | None = None
    operator_split_pct: Decimal | None = None
    provisional_sum_total: Decimal | None = None
    retention_tiers: list[RetentionTierCreate] = []
    wbs_codes: list[WBSCodeCreate] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    project_number: str | None = None
    client_name: str | None = None
    client_contact: str | None = None
    contractor_name: str | None = None
    contract_sum: Decimal | None = None
    gst_rate: Decimal | None = None
    end_client_name: str | None = None
    end_client_representative: str | None = None
    end_client_address: str | None = None
    landlord_split_pct: Decimal | None = None
    operator_split_pct: Decimal | None = None
    provisional_sum_total: Decimal | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    project_number: str | None
    client_name: str
    contractor_name: str
    contract_sum: Decimal
    gst_rate: Decimal
    end_client_name: str | None = None
    end_client_representative: str | None = None
    end_client_address: str | None = None
    landlord_split_pct: Decimal | None = None
    operator_split_pct: Decimal | None = None
    provisional_sum_total: Decimal | None = None
    retention_tiers: list[RetentionTierResponse] = []
    wbs_codes: list[WBSCodeResponse] = []

    model_config = {"from_attributes": True}
