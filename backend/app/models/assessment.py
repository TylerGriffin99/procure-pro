import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.assessment_line_item import AssessmentLineItem
    from app.models.assessment_provisional_sum import AssessmentProvisionalSum
    from app.models.assessment_variation import AssessmentVariation


class AssessmentStatus(str, enum.Enum):
    draft = "draft"
    finalised = "finalised"


class LineItemStatus(str, enum.Enum):
    unapproved = "unapproved"
    approved = "approved"
    interim = "interim"


class AdjustmentType(str, enum.Enum):
    interim_adjustment = "interim_adjustment"


class Assessment(AuditMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus), default=AssessmentStatus.draft
    )

    contract_sum: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    adjustment_to_provisional_sums: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    approved_variation_orders: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    adjusted_contract_sum: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    value_claimed_to_date: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    adjustments: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total_recommended: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total_retention: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total_payment_to_date: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    previously_certified: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    recommended_this_period: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    gst_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total_including_gst: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    finalised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    line_items: Mapped[list["AssessmentLineItem"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        foreign_keys="[AssessmentLineItem.assessment_id]",
    )
    variation_items: Mapped[list["AssessmentVariation"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        foreign_keys="[AssessmentVariation.assessment_id]",
    )
    provisional_sum_items: Mapped[list["AssessmentProvisionalSum"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        foreign_keys="[AssessmentProvisionalSum.assessment_id]",
    )
