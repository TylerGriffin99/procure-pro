import enum
import uuid

from sqlalchemy import String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AuditMixin, Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(AuditMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    email_verified: Mapped[bool] = mapped_column(default=False)
    profile_image_url: Mapped[str] = mapped_column(String(255), nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    deleted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    country: Mapped[str] = mapped_column(String(2), default="NZ", server_default="NZ")
    currency: Mapped[str] = mapped_column(String(3), default="NZD", server_default="NZD")
