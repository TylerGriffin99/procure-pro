import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AuditMixin, Base


class VariationStatus(str, enum.Enum):
    unapproved = "unapproved"
    in_review = "in_review"
    approved = "approved"


class Variation(AuditMixin, Base):
    __tablename__ = "variations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    ci_number: Mapped[int] = mapped_column(Integer)
    contractor_ref: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(1000))
    contractor_submission: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    status: Mapped[VariationStatus] = mapped_column(Enum(VariationStatus), default=VariationStatus.unapproved)
    trade: Mapped[str | None] = mapped_column(String(255))
    wbs_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wbs_codes.id"))
    comments: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
