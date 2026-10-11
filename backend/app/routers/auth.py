from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import CurrentUser, DbSession
from app.schemas.user import Token, UserCreate, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: DbSession):
    return await auth_service.register_user(db, user_in)


@router.post("/login", response_model=Token)
async def login(db: DbSession, form: OAuth2PasswordRequestForm = Depends()):
    return await auth_service.login_user(db, form.username, form.password)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return user
