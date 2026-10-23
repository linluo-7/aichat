"""确保用户资料表存在默认行。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserProfile


async def ensure_user_profile(session: AsyncSession) -> None:
    """若尚无资料记录则插入 id=1 的默认用户。"""
    result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
    if result.scalar_one_or_none() is None:
        session.add(UserProfile(id=1, nickname="我"))
        await session.commit()
