from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.constants.enums import AssessmentStatus
from app.constants.values import CENTS, EXPORT_STRIPPED_COMMENT_PREFIXES
from app.schemas.assessment_aggregate import (
    AggregatedPSGroup,
    AggregatedVariationGroup,
    AggregatedWBSGroup,
    AssessmentAggregate,
    AssessmentSummary,
)
from app.schemas.base import StrictModel
from app.utils.dates import auto_fill_dates, format_long_date


def export_display(history_row: Any, child_rows: list[Any]) -> tuple[str, str]:
    all_rows = ([history_row] if history_row else []) + list(child_rows)
    comments = "; ".join(r.comments for r in all_rows if r.comments)
    for prefix in EXPORT_STRIPPED_COMMENT_PREFIXES:
        if comments.startswith(prefix):
            comments = comments[len(prefix) :]
            break
    if any(r.is_closed_out for r in all_rows):
        status = "Closed Out"
    elif child_rows:
        status = child_rows[0].status.value.capitalize()
    elif history_row:
        status = history_row.status.value.capitalize()
    else:
        status = ""
    return comments.strip(), status


class RetentionDetail(StrictModel):
    percentage: str
    base: Decimal
    amount: Decimal


class ContractWorkLine(StrictModel):
    description: str
    contract_sum: Decimal
    contractor_claim: Decimal
    recommended: Decimal
    percentage: str
    variance: Decimal
    previously_paid: Decimal
    recommended_this_period: Decimal
    comments: str

    @classmethod
    def from_group(cls, g: AggregatedWBSGroup) -> ContractWorkLine:
        rows = ([g.history_row] if g.history_row else []) + g.child_rows
        return cls(
            description=g.description,
            contract_sum=g.contract_sum,
            contractor_claim=g.contractor_claim_to_date,
            recommended=g.total_recommended,
            percentage=f"{g.percentage:.1f}%",
            variance=g.variance_to_claim,
            previously_paid=g.previously_paid,
            recommended_this_period=g.recommended_this_period,
            comments="; ".join(r.comments for r in rows if r.comments),
        )


class VariationLine(StrictModel):
    ci_number: str
    description: str
    submission: Decimal
    type: str = ""
    claimed_to_date: Decimal
    recommended: Decimal
    previously_paid: Decimal
    this_period: Decimal
    status: str
    comments: str

    @classmethod
    def from_group(cls, g: AggregatedVariationGroup) -> VariationLine:
        comments, status = export_display(g.history_row, g.child_rows)
        return cls(
            ci_number=g.contractor_ref,
            description=g.description,
            submission=g.contractor_submission,
            claimed_to_date=g.contractor_claim_to_date,
            recommended=g.total_recommended,
            previously_paid=g.previously_paid,
            this_period=g.recommended_this_period,
            status=status,
            comments=comments,
        )


class ProvisionalSumLine(StrictModel):
    ps_number: int
    description: str
    contract_sum: Decimal
    claimed_to_date: Decimal
    recommended: Decimal
    previously_paid: Decimal
    this_period: Decimal
    percentage: str
    status: str
    comments: str

    @classmethod
    def from_group(cls, g: AggregatedPSGroup) -> ProvisionalSumLine:
        comments, status = export_display(g.history_row, g.child_rows)
        return cls(
            ps_number=g.ps_number,
            description=g.description,
            contract_sum=g.contract_sum,
            claimed_to_date=g.contractor_claim_to_date,
            recommended=g.total_recommended,
            previously_paid=g.previously_paid,
            this_period=g.recommended_this_period,
            percentage=f"{g.percentage:.1f}%",
            status=status,
            comments=comments,
        )


class ClaimDates(StrictModel):
    claim_received: str = ""
    provisional_payment_schedule_due: str = ""
    payment_schedule_due: str = ""
    payment_due: str = ""

    @classmethod
    def from_claim(cls, claim: Any) -> ClaimDates:
        if not claim:
            return cls()
        received = claim.claim_received
        if not received and claim.created_at:
            # No explicit claim_received: derive every date from created_at.
            received = as_date(claim.created_at)
            auto = auto_fill_dates(received)
            return cls.of(
                received, auto["provisional_payment_schedule_due"], auto["payment_schedule_due"], auto["payment_due"]
            )
        provisional, schedule, payment = (
            claim.provisional_payment_schedule_due,
            claim.payment_schedule_due,
            claim.payment_due,
        )
        if received and (not provisional or not schedule or not payment):
            auto = auto_fill_dates(received)
            provisional = provisional or auto.get("provisional_payment_schedule_due")
            schedule = schedule or auto.get("payment_schedule_due")
            payment = payment or auto.get("payment_due")
        return cls.of(received, provisional, schedule, payment)

    @classmethod
    def of(cls, received: Any, provisional: Any, schedule: Any, payment: Any) -> ClaimDates:
        return cls(
            claim_received=format_long_date(received),
            provisional_payment_schedule_due=format_long_date(provisional),
            payment_schedule_due=format_long_date(schedule),
            payment_due=format_long_date(payment),
        )


def as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def split_amount(amount: Decimal, pct: Decimal | None) -> Decimal:
    return (amount * pct).quantize(CENTS) if pct else Decimal("0")


class PaymentRecommendation(StrictModel):
    project_name: str
    project_number: str
    pr_number: int
    revision: int = 0
    issue_date: str
    principal: str
    end_client_name: str
    end_client_address_lines: list[str]
    end_client_representative_first_name: str
    landlord_split_pct: Decimal | None
    operator_split_pct: Decimal | None
    landlord_amount: Decimal
    operator_amount: Decimal
    engineer: str
    contractor: str
    claim_number: int
    claim_received: str
    provisional_payment_schedule_due: str
    payment_schedule_due: str
    payment_due: str
    contract_sum: Decimal
    adjustment_to_provisional_sums: Decimal
    approved_variation_orders: Decimal
    adjusted_contract_sum: Decimal
    value_claimed: Decimal
    adjustments: Decimal
    total_recommended: Decimal
    retention_details: list[RetentionDetail]
    total_retention: Decimal
    total_payment_to_date: Decimal
    previously_certified: Decimal
    recommended_this_period: Decimal
    gst_rate: Decimal
    gst_amount: Decimal
    total_including_gst: Decimal
    contract_works: list[ContractWorkLine]
    variation_works: list[VariationLine]
    provisional_sums: list[ProvisionalSumLine]
    is_draft: bool

    @classmethod
    def from_aggregate(
        cls,
        aggregate: AssessmentAggregate,
        *,
        project: Any,
        claim: Any,
        summary: AssessmentSummary,
        retention_details: list[RetentionDetail],
    ) -> PaymentRecommendation:
        assessment = aggregate.assessment
        number = claim.claim_number if claim else assessment.version
        this_period = summary.recommended_this_period
        return cls(
            project_name=project.name,
            project_number=project.project_number or "",
            pr_number=number,
            issue_date=assessment.created_at.strftime("%d %B %Y") if assessment.created_at else "",
            principal=project.client_name,
            end_client_name=project.end_client_name or project.client_name,
            end_client_address_lines=project.end_client_address.split("\n") if project.end_client_address else [],
            end_client_representative_first_name=(project.end_client_representative or "").split()[0]
            if project.end_client_representative
            else "",
            landlord_split_pct=project.landlord_split_pct,
            operator_split_pct=project.operator_split_pct,
            landlord_amount=split_amount(this_period, project.landlord_split_pct),
            operator_amount=split_amount(this_period, project.operator_split_pct),
            engineer=project.end_client_representative or "",
            contractor=project.contractor_name,
            claim_number=number,
            **ClaimDates.from_claim(claim).model_dump(),
            contract_sum=summary.contract_sum,
            adjustment_to_provisional_sums=summary.adjustment_to_provisional_sums,
            approved_variation_orders=summary.approved_variation_orders,
            adjusted_contract_sum=summary.adjusted_contract_sum,
            value_claimed=summary.value_claimed_to_date,
            adjustments=summary.adjustments,
            total_recommended=summary.total_recommended,
            retention_details=retention_details,
            total_retention=summary.total_retention,
            total_payment_to_date=summary.total_payment_to_date,
            previously_certified=assessment.previously_certified or Decimal("0"),
            recommended_this_period=this_period,
            gst_rate=project.gst_rate,
            gst_amount=summary.gst_amount,
            total_including_gst=summary.total_including_gst,
            contract_works=[ContractWorkLine.from_group(g) for g in aggregate.wbs_groups],
            variation_works=[VariationLine.from_group(g) for g in aggregate.variation_groups],
            provisional_sums=[ProvisionalSumLine.from_group(g) for g in aggregate.ps_groups],
            is_draft=assessment.status != AssessmentStatus.finalised,
        )


class ExportFile(StrictModel):
    content: bytes
    media_type: str
    filename: str
