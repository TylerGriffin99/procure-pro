import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import user_repo
from app.schemas.user import UserCreate, Token, COUNTRY_CURRENCY_MAP
from app.utils.auth import hash_password, verify_password, create_access_token


async def register_user(db: AsyncSession, data: UserCreate):
    existing = await user_repo.get_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
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
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)
