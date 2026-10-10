import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.harness_session import HarnessSession


class FlagType(str, enum.Enum):
    total_mismatch = "total_mismatch"  # kept for DB compat with existing rows
    project_over_budget = "project_over_budget"
    over_claim = "over_claim"
    percentage_error = "percentage_error"
    ptd_decrease = "ptd_decrease"
    missing_ref = "missing_ref"
    duplicate_item = "duplicate_item"
    format_warning = "format_warning"
    confidence_low = "confidence_low"


class FlagSeverity(str, enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ClaimParseFlag(Base):
    __tablename__ = "claim_parse_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("harness_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True)
    flag_type: Mapped[FlagType] = mapped_column(Enum(FlagType, name="flag_type"), nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(Enum(FlagSeverity, name="flag_severity"), nullable=False)
    line_item_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["HarnessSession"] = relationship(back_populates="flags", foreign_keys=[session_id])
