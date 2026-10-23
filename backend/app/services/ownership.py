"""将存量数据归属到管理员（V3 迁移后）。"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, User, UserProfile
from app.services.auth import bootstrap_admin_if_empty, ensure_profile_for_user


async def assign_orphan_data_to_admin(db: AsyncSession) -> None:
    """
    空用户时 bootstrap 管理员；将无 user_id 的联系人/资料挂到管理员。
    旧单机版可能已有一条 user_profile，优先复用，避免重复行导致启动失败。
    """
    admin = await bootstrap_admin_if_empty(db)
    if not admin:
        result = await db.execute(select(User).order_by(User.id.asc()).limit(1))
        admin = result.scalar_one_or_none()
    if not admin:
        return

    await db.execute(
        update(Contact).where(Contact.user_id.is_(None)).values(user_id=admin.id)
    )

    # 管理员是否已有资料
    owned = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == admin.id)
        .order_by(UserProfile.id.asc())
    )
    owned_rows = list(owned.scalars().all())

    orphans = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id.is_(None))
        .order_by(UserProfile.id.asc())
    )
    orphan_rows = list(orphans.scalars().all())

    if owned_rows:
        keep = owned_rows[0]
        for extra in owned_rows[1:]:
            await db.delete(extra)
        # 用旧资料补全昵称/头像
        if orphan_rows:
            old = orphan_rows[0]
            if (not keep.nickname or keep.nickname in ("我", admin.username)) and old.nickname:
                keep.nickname = old.nickname
            if not keep.avatar_url and old.avatar_url:
                keep.avatar_url = old.avatar_url
            for row in orphan_rows:
                await db.delete(row)
    elif orphan_rows:
        keep = orphan_rows[0]
        keep.user_id = admin.id
        if not (keep.nickname or "").strip():
            keep.nickname = admin.username
        for row in orphan_rows[1:]:
            await db.delete(row)
    else:
        await ensure_profile_for_user(db, admin)

    await ensure_profile_for_user(db, admin)
    await db.commit()
