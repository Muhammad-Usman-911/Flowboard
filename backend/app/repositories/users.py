from sqlalchemy import func, select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_usernames(self, usernames: set[str]) -> list[User]:
        if not usernames:
            return []
        stmt = select(User).where(User.username.in_({u.lower() for u in usernames}))
        return list((await self.session.execute(stmt)).scalars().all())

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
