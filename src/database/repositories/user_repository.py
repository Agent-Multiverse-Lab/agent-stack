from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        uid: str | None = None,
    ) -> User:
        user = User(
            email=email,
            uid=uid or str(uuid4()),
            password_hash=password_hash,
        )
        self.session.add(user)
        await self.session.flush()
        return user
