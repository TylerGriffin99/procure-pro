import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.project import Project


class WBSLevel(str, enum.Enum):
    category = "category"
    subcategory = "subcategory"


class WBSCode(AuditMixin, Base):
    __tablename__ = "wbs_codes"

    # Allow the non-persisted `in_use` attribute below (not a Mapped column).
    __allow_unmapped__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wbs_codes.id"))
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(500))
    level: Mapped[WBSLevel] = mapped_column(Enum(WBSLevel), default=WBSLevel.subcategory)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    contract_sum: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Transient, non-persisted flag populated by the service layer for API
    # responses (whether any line item references this code). Defaults to False
    # so endpoints that don't compute it (create/update) still serialize cleanly.
    in_use: bool = False

    project: Mapped["Project"] = relationship(back_populates="wbs_codes")
    parent: Mapped[Optional["WBSCode"]] = relationship(back_populates="children", remote_side="WBSCode.id")
    children: Mapped[list["WBSCode"]] = relationship(back_populates="parent", order_by="WBSCode.sort_order")
