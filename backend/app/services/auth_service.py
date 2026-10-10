import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestError, UnauthorizedError
from app.repos import user_repo
from app.schemas.user import COUNTRY_CURRENCY_MAP, Token, UserCreate
from app.utils.auth import create_access_token, hash_password, verify_password


async def register_user(db: AsyncSession, data: UserCreate):
    existing = await user_repo.get_by_email(db, data.email)
    if existing:
        raise BadRequestError("Email already registered")
    user = await user_repo.create(
        db,
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        country=data.country,
        currency=COUNTRY_CURRENCY_MAP[data.country],
        created_by=uuid.uuid4(),
    )
    user.created_by = user.id
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> Token:
    user = await user_repo.get_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)
