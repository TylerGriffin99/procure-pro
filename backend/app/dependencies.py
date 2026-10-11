import functools
import uuid
from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.llm_client import LlmClient
from app.config import Settings, get_settings
from app.constants.enums import MatcherName
from app.database import get_db, get_session_factory
from app.exceptions import UnauthorizedError
from app.harness.factory import EngineBuilder, build_matchers, engine_builder
from app.harness.models import Matcher
from app.models.user import User
from app.repos import user_repo
from app.utils.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_prefix}/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]
SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
AppSettings = Annotated[Settings, Depends(get_settings)]
BearerToken = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: BearerToken, db: DbSession) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("Invalid token")
    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token")
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError, AttributeError) as e:
        raise UnauthorizedError("Invalid token") from e
    user = await user_repo.get_by_id(db, user_uuid)
    if user is None:
        raise UnauthorizedError("User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# Process-wide: built once at first use, so the matcher table's "Jev key unset" warning logs once, not per stream.
@functools.cache
def get_llm_client() -> LlmClient:
    return LlmClient.from_settings(get_settings())


@functools.cache
def get_matchers() -> Mapping[MatcherName, Matcher]:
    return build_matchers(get_settings(), llm=get_llm_client())


def get_engine_builder(
    settings: AppSettings,
    llm: Annotated[LlmClient, Depends(get_llm_client)],
    matchers: Annotated[Mapping[MatcherName, Matcher], Depends(get_matchers)],
) -> EngineBuilder:
    return engine_builder(settings=settings, llm=llm, matchers=matchers)


BuildEngine = Annotated[EngineBuilder, Depends(get_engine_builder)]
