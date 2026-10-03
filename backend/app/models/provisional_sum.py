import enum
import uuid
from decimal import Decimal

from sqlalchemy import String, ForeignKey, Numeric, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AuditMixin, Base
from app.models.variation import VariationStatus


class ProvisionalSum(AuditMixin, Base):
    __tablename__ = "provisional_sums"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    ps_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(1000))
    contract_sum: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    status: Mapped[VariationStatus] = mapped_column(Enum(VariationStatus), default=VariationStatus.unapproved)
    trade: Mapped[str | None] = mapped_column(String(255))
    wbs_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wbs_codes.id"))
