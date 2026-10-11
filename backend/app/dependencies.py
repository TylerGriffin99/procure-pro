import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.user import User
from app.repos import user_repo
from app.utils.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("Invalid token")
    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token")
    user = await user_repo.get_by_id(db, uuid.UUID(user_id))
    if user is None:
        raise UnauthorizedError("User not found")
    return user
