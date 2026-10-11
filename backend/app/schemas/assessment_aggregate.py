"""Typed output of app.utils.assessment_aggregator and the service that assembles it."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import LineItemStatus
from app.schemas.base import StrictModel


class AggregatedWBSGroup(StrictModel):
    wbs_code_id: uuid.UUID | None
    description: str
    contract_sum: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    total_recommended: Decimal
    contractor_claim_to_date: Decimal
    variance_to_claim: Decimal
    percentage: Decimal
    history_row: Any | None
    child_rows: list[Any] = Field(default_factory=list)


class AggregatedVariationGroup(StrictModel):
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
    history_row: Any | None
    child_rows: list[Any] = Field(default_factory=list)


class AggregatedPSGroup(StrictModel):
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
    history_row: Any | None
    child_rows: list[Any] = Field(default_factory=list)


class AssessmentTotals(StrictModel):
    sub_contract_works: Decimal
    approved_variation_orders: Decimal
    adjustment_to_provisional_sums: Decimal
    total_recommended: Decimal
    value_claimed_to_date: Decimal
    adjustments: Decimal


class AssessmentSummary(StrictModel):
    contract_sum: Decimal
    approved_variation_orders: Decimal
    adjustment_to_provisional_sums: Decimal
    adjusted_contract_sum: Decimal
    value_claimed_to_date: Decimal
    adjustments: Decimal
    total_recommended: Decimal
    total_retention: Decimal
    total_payment_to_date: Decimal
    recommended_this_period: Decimal
    gst_amount: Decimal
    total_including_gst: Decimal


class AssessmentRowValues(StrictModel):
    master_id: uuid.UUID | None
    claim_line_item_id: uuid.UUID | None
    contractor_claim_to_date: Decimal
    total_recommended: Decimal
    percentage: Decimal
    variance_to_claim: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    status: LineItemStatus
    comments: str | None = None
    description: str | None = None
    sort_order: int | None = None
    created_by: uuid.UUID


class AssessmentRows(StrictModel):
    line_items: list[AssessmentRowValues]
    variation_items: list[AssessmentRowValues]
    provisional_sum_items: list[AssessmentRowValues]


class ReclassifyCarry(StrictModel):
    assessment_id: uuid.UUID
    claim_line_item_id: uuid.UUID
    contractor_claim_to_date: Decimal
    recommended_this_period: Decimal
    description: str
    contract_value: Decimal


class AssessmentAggregate(BaseModel):
    """An assessment plus its pre-aggregated groups — what the service hands to the DTO."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    assessment: Any  # app.models.assessment.Assessment (ORM); Any keeps schemas free of ORM imports
    wbs_groups: list[AggregatedWBSGroup]
    variation_groups: list[AggregatedVariationGroup]
    ps_groups: list[AggregatedPSGroup]


class AggregatedAssessment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    aggregate: AssessmentAggregate
    # The master rows the groups were built from, so callers that update masters need not re-fetch them.
    variations: list[Any]  # app.models.variation.Variation (ORM)
    provisional_sums: list[Any]  # app.models.provisional_sum.ProvisionalSum (ORM)
