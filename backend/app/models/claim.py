import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.claim_line_item import ClaimLineItem


class ClaimItemType(str, enum.Enum):
    contract_work = "contract_work"
    variation = "variation"
    provisional_sum = "provisional_sum"


class Claim(AuditMixin, Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    claim_number: Mapped[int] = mapped_column(Integer)
    period_from: Mapped[date | None] = mapped_column(Date)
    period_to: Mapped[date | None] = mapped_column(Date)
    payment_due: Mapped[date | None] = mapped_column(Date)
    claim_received: Mapped[date | None] = mapped_column(Date)
    provisional_payment_schedule_due: Mapped[date | None] = mapped_column(Date)
    payment_schedule_due: Mapped[date | None] = mapped_column(Date)
    contractor_job_number: Mapped[str | None] = mapped_column(String(50))
    raw_pdf_path: Mapped[str | None] = mapped_column(String(1000))
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    original_contract_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    variations_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    revised_contract_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    retention_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    claimed_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    validation_warnings: Mapped[list | None] = mapped_column(JSONB, default=list)

    line_items: Mapped[list["ClaimLineItem"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
