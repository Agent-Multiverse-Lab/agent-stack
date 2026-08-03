from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from server.utils.auth import (
    AuthenticatedUser,
    create_access_token,
    hash_password,
    verify_password,
)
from src.database import get_db
from src.database.repositories import UserRepository
from src.utils import logger

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    email = str(payload.email).lower()
    logger.info("Registration requested: email=%s.", email)
    user_repository = UserRepository(session)
    existing_user = await user_repository.get_by_email(email)
    if existing_user is not None:
        logger.warning(
            "Registration rejected; email already exists: %s.",
            email,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists.",
        )

    user = await user_repository.create(
        email=email,
        password_hash=hash_password(payload.password),
    )
    await session.commit()
    await session.refresh(user)
    logger.info("User registered: user_id=%s.", user.id)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    email = str(payload.email).lower()
    logger.info("Login requested: email=%s.", email)
    user_repository = UserRepository(session)
    user = await user_repository.get_by_email(email)
    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("Login failed: email=%s.", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        logger.warning("Login rejected; user is disabled: user_id=%s.", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    # FIXME: JWT 需要完整用户身份字段，不能只传数据库主键。
    token = create_access_token(
        user_id=user.id,
        uid=user.uid,
        email=user.email,
        is_active=user.is_active,
    )
    logger.info("Login succeeded: user_id=%s.", user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: AuthenticatedUser):
    logger.info("Current user requested: user_id=%s.", current_user.id)
    return UserResponse.model_validate(current_user)
