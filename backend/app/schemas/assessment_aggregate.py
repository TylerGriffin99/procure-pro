"""Typed output of app.utils.assessment_aggregator and the service that assembles it."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class AssessmentAggregate(BaseModel):
    """An assessment plus its pre-aggregated groups — what the service hands to the DTO."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    assessment: Any  # app.models.assessment.Assessment (ORM); Any keeps schemas free of ORM imports
    wbs_groups: list[AggregatedWBSGroup]
    variation_groups: list[AggregatedVariationGroup]
    ps_groups: list[AggregatedPSGroup]
