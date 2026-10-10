import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.retention_tier import RetentionTier
    from app.models.wbs_code import WBSCode


class Project(AuditMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500))
    project_number: Mapped[str | None] = mapped_column(String(100))
    client_name: Mapped[str] = mapped_column(String(500))
    client_contact: Mapped[str | None] = mapped_column(String(255))

    # End client (principal) details
    end_client_name: Mapped[str | None] = mapped_column(String(500))
    end_client_representative: Mapped[str | None] = mapped_column(String(255))
    end_client_address: Mapped[str | None] = mapped_column(String(1000))

    # Landlord / Operator split (fractions, e.g. 0.25 and 0.75, must total 1.0 if set)
    landlord_split_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    operator_split_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    contractor_name: Mapped[str] = mapped_column(String(500))
    contract_sum: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    provisional_sum_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.15"))

    wbs_codes: Mapped[list["WBSCode"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    retention_tiers: Mapped[list["RetentionTier"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="RetentionTier.tier_order"
    )
