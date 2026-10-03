import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base


class RetentionTier(AuditMixin, Base):
    __tablename__ = "retention_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    tier_order: Mapped[int] = mapped_column(Integer)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    up_to_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    project: Mapped["Project"] = relationship(back_populates="retention_tiers")
