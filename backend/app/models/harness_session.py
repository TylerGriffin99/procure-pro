import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.claim_parse_flag import ClaimParseFlag
    from app.models.harness_workspace_file import HarnessWorkspaceFile


class HarnessSessionStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class HarnessSession(Base):
    __tablename__ = "harness_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    harness_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[HarnessSessionStatus] = mapped_column(
        Enum(HarnessSessionStatus, name="harness_session_status"),
        nullable=False,
        default=HarnessSessionStatus.pending,
    )
    current_phase: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase_results: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    workspace_files: Mapped[list["HarnessWorkspaceFile"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    flags: Mapped[list["ClaimParseFlag"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="ClaimParseFlag.session_id",
    )
