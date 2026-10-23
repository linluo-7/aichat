"""兼容旧调用：启动时不再强制创建全局资料（改由 ownership / ensure_profile_for_user）。"""
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_user_profile(session: AsyncSession) -> None:
    """保留空实现以免旧引用报错；真实逻辑见 assign_orphan_data_to_admin。"""
    _ = session
