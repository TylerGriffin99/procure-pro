import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base
from app.models.claim import ClaimItemType

if TYPE_CHECKING:
    from app.models.claim import Claim


class ClaimLineItem(AuditMixin, Base):
    __tablename__ = "claim_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    item_type: Mapped[ClaimItemType] = mapped_column(Enum(ClaimItemType))

    ref_code: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(1000))
    contract_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    percentage: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    ptd: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    previous: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    current: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2))

    suggested_wbs_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wbs_codes.id")
    )
    variation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variations.id")
    )
    provisional_sum_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provisional_sums.id")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    categorisation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSONB, default=list)

    claim: Mapped["Claim"] = relationship(back_populates="line_items")
