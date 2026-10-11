import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import WBSLevel
from app.database import AuditMixin, Base

if TYPE_CHECKING:
    from app.models.project import Project


class WBSCode(AuditMixin, Base):
    __tablename__ = "wbs_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wbs_codes.id"))
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(500))
    level: Mapped[WBSLevel] = mapped_column(Enum(WBSLevel), default=WBSLevel.subcategory)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    contract_sum: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="wbs_codes")
    parent: Mapped[Optional["WBSCode"]] = relationship(back_populates="children", remote_side="WBSCode.id")
    children: Mapped[list["WBSCode"]] = relationship(back_populates="parent", order_by="WBSCode.sort_order")
