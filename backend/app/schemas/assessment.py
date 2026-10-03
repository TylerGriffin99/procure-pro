import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.assessment import AssessmentStatus, LineItemStatus


class AssessmentCreate(BaseModel):
    claim_id: uuid.UUID


class AssessmentLineItemResponse(BaseModel):
    id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    wbs_code_id: uuid.UUID | None
    description: str
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    percentage: Decimal
    variance_to_claim: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    status: LineItemStatus
    comments: str | None
    is_closed_out: bool = False
    sort_order: int
    adjustment_type: str | None = None
    source_assessment_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class AssessmentLineItemUpdate(BaseModel):
    total_recommended: Decimal | None = None
    wbs_code_id: uuid.UUID | None = None
    status: LineItemStatus | None = None
    comments: str | None = None


class AssessmentVariationResponse(BaseModel):
    id: uuid.UUID
    variation_id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    contractor_ref: str
    description: str
    contractor_submission: Decimal
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    status: LineItemStatus
    comments: str | None
    is_closed_out: bool = False
    adjustment_type: str | None = None
    source_assessment_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class AssessmentProvisionalSumResponse(BaseModel):
    id: uuid.UUID
    provisional_sum_id: uuid.UUID
    claim_line_item_id: uuid.UUID | None
    ps_number: int
    description: str
    contract_sum: Decimal
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    status: LineItemStatus
    comments: str | None
    is_closed_out: bool = False
    adjustment_type: str | None = None
    source_assessment_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class AssessmentVariationUpdate(BaseModel):
    total_recommended: Decimal | None = None
    status: LineItemStatus | None = None
    comments: str | None = None


class AssessmentProvisionalSumUpdate(BaseModel):
    total_recommended: Decimal | None = None
    status: LineItemStatus | None = None
    comments: str | None = None


class AssessmentResponse(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    project_id: uuid.UUID
    version: int
    status: AssessmentStatus
    contract_sum: Decimal | None
    adjusted_contract_sum: Decimal | None
    total_recommended: Decimal | None
    total_retention: Decimal | None
    total_payment_to_date: Decimal | None
    previously_certified: Decimal | None
    recommended_this_period: Decimal | None
    gst_amount: Decimal | None
    total_including_gst: Decimal | None
    line_items: list[AssessmentLineItemResponse] = []
    variation_items: list[AssessmentVariationResponse] = []
    provisional_sum_items: list[AssessmentProvisionalSumResponse] = []

    model_config = {"from_attributes": True}


class AggregatedWBSGroupResponse(BaseModel):
    wbs_code_id: uuid.UUID | None
    description: str
    contract_sum: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: AssessmentLineItemResponse | None
    child_rows: list[AssessmentLineItemResponse]
    model_config = {"from_attributes": True}


class AggregatedVariationGroupResponse(BaseModel):
    variation_id: uuid.UUID
    ci_number: int
    contractor_ref: str
    description: str
    contractor_submission: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: AssessmentVariationResponse | None
    child_rows: list[AssessmentVariationResponse]
    model_config = {"from_attributes": True}


class AggregatedPSGroupResponse(BaseModel):
    provisional_sum_id: uuid.UUID
    ps_number: int
    description: str
    contract_sum: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: AssessmentProvisionalSumResponse | None
    child_rows: list[AssessmentProvisionalSumResponse]
    model_config = {"from_attributes": True}


class AggregatedAssessmentResponse(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    project_id: uuid.UUID
    version: int
    status: str
    previously_certified: Decimal
    contract_sum: Decimal | None
    approved_variation_orders: Decimal | None
    adjustment_to_provisional_sums: Decimal | None
    adjusted_contract_sum: Decimal | None
    value_claimed_to_date: Decimal | None
    adjustments: Decimal | None
    total_recommended: Decimal | None
    total_retention: Decimal | None
    total_payment_to_date: Decimal | None
    recommended_this_period: Decimal | None
    gst_amount: Decimal | None
    total_including_gst: Decimal | None
    finalised_at: str | None
    wbs_groups: list[AggregatedWBSGroupResponse]
    variation_groups: list[AggregatedVariationGroupResponse]
    ps_groups: list[AggregatedPSGroupResponse]
    line_items: list[AssessmentLineItemResponse] = []
    variation_items: list[AssessmentVariationResponse] = []
    provisional_sum_items: list[AssessmentProvisionalSumResponse] = []
    model_config = {"from_attributes": True}


class ReclassifyNewRecord(BaseModel):
    description: str


_ItemType = Literal["line-item", "variation", "provisional-sum"]


class ReclassifyRequest(BaseModel):
    source_item_id: uuid.UUID
    source_type: _ItemType
    target_type: _ItemType
    target_id: uuid.UUID | None = None
    target_wbs_code_id: uuid.UUID | None = None
    new_record: ReclassifyNewRecord | None = None


class InterimAdjustRequest(BaseModel):
    item_type: Literal["line-item", "variation", "provisional-sum"]
    parent_id: uuid.UUID  # wbs_code_id, variation_id, or provisional_sum_id
    agreed_total: Decimal
    comments: str | None = None


class CloseOutRequest(BaseModel):
    item_type: Literal["line-item", "variation", "provisional-sum"]
    parent_id: uuid.UUID  # wbs_code_id, variation_id, or provisional_sum_id
