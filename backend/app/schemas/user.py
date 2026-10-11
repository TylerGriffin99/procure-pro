import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.constants.enums import Country, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    country: Country


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone_number: str | None = None
    role: UserRole
    email_verified: bool
    profile_image_url: str | None = None
    organization_id: uuid.UUID | None = None
    country: str
    currency: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
