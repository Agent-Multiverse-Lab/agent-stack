from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs import config
from src.database import User, get_db
from src.utils import logger

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_required_auth_settings() -> None:
    if not config.jwt_secret:
        logger.error("Missing JWT_SECRET configuration.")
        raise RuntimeError("Missing JWT_SECRET configuration.")


def get_jwt_key() -> bytes:
    verify_required_auth_settings()
    return sha256(config.jwt_secret.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(
    user_id: int | str,
    uid: str,
    email: str,
    is_active: bool = True,
) -> str:
    verify_required_auth_settings()
    logger.info("Creating access token: user_id=%s.", user_id)
    expire_at = datetime.now(UTC) + timedelta(minutes=config.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "uid": uid,
        "email": email,
        "is_active": is_active,
        "exp": expire_at,
    }
    return jwt.encode(payload, get_jwt_key(), algorithm=config.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    verify_required_auth_settings()
    try:
        payload = jwt.decode(
            token,
            get_jwt_key(),
            algorithms=[config.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Access token decode failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired.",
        ) from exc

    # FIXME: 邮箱是唯一登录账号，JWT 只校验 sub、uid、email 三个身份字段。
    if "sub" not in payload or "uid" not in payload or "email" not in payload:
        logger.warning("Access token payload validation failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token payload is invalid.",
        )
    return payload


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = getattr(request.state, "user", None)
    if isinstance(user, User):
        return user

    payload = getattr(request.state, "auth_payload", None)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token payload is invalid.",
        ) from exc


    user = await db.get(User, user_id)
    
    # FIXME: JWT 的数据库用户主键存放在 sub；旧代码读取不存在的 id，导致所有登录用户都被拒绝。
    if user is None or not user.is_active or str(user.id) != str(payload["sub"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found.",
        )

    request.state.user = user
    return user


AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def is_admin_user(user: User) -> bool:
    admin_emails = {
        value.strip().casefold()
        for value in config.admin_emails.split(",")
        if value.strip()
    }
    return str(user.email).casefold() in admin_emails


async def get_current_admin_user(
    current_user: AuthenticatedUser,
) -> User:
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission is required.",
        )
    return current_user


AdminUser = Annotated[User, Depends(get_current_admin_user)]
