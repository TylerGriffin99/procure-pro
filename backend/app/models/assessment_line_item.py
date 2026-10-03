import uuid
from decimal import Decimal

from sqlalchemy import Boolean, String, ForeignKey, Numeric, Integer, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base
from app.models.assessment import LineItemStatus, AdjustmentType


class AssessmentLineItem(AuditMixin, Base):
    __tablename__ = "assessment_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"))
    claim_line_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claim_line_items.id"))
    wbs_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wbs_codes.id"))

    description: Mapped[str] = mapped_column(String(1000))
    contract_sum: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    contractor_claim_to_date: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    total_recommended: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    variance_to_claim: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    previously_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    recommended_this_period: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    status: Mapped[LineItemStatus] = mapped_column(Enum(LineItemStatus), default=LineItemStatus.unapproved)
    comments: Mapped[str | None] = mapped_column(Text)
    is_closed_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    adjustment_type: Mapped[AdjustmentType | None] = mapped_column(Enum(AdjustmentType), nullable=True)
    source_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)

    assessment: Mapped["Assessment"] = relationship(
        back_populates="line_items", foreign_keys=[assessment_id],
    )
