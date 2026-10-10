import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base
from app.models.assessment import AdjustmentType, LineItemStatus

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.variation import Variation


class AssessmentVariation(AuditMixin, Base):
    __tablename__ = "assessment_variations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"))
    variation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("variations.id"))
    claim_line_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_line_items.id"), nullable=True
    )

    contractor_claim_to_date: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    total_recommended: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    variance_to_claim: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    previously_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    recommended_this_period: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    status: Mapped[LineItemStatus] = mapped_column(Enum(LineItemStatus), default=LineItemStatus.unapproved)
    comments: Mapped[str | None] = mapped_column(Text)
    is_closed_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    adjustment_type: Mapped[AdjustmentType | None] = mapped_column(Enum(AdjustmentType), nullable=True)
    source_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True
    )

    assessment: Mapped["Assessment"] = relationship(back_populates="variation_items", foreign_keys=[assessment_id])
    variation: Mapped["Variation"] = relationship()

    @property
    def contractor_ref(self) -> str:
        return (self.variation.contractor_ref or "") if self.variation else ""

    @property
    def description(self) -> str:
        return self.variation.description if self.variation else ""

    @property
    def contractor_submission(self) -> Decimal:
        return self.variation.contractor_submission if self.variation else Decimal("0")
