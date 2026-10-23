"""账号认证：密码哈希、JWT、邀请码、掩码。"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import InviteCode, User, UserProfile

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_INVITE_ALPHABET = string.ascii_uppercase + string.digits
_INVITE_ALPHABET = (
    _INVITE_ALPHABET.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
)


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希。"""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, username: str) -> str:
    """签发登录 JWT。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(days=max(1, settings.auth_token_days)),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """解析并校验 JWT，失败抛出 jwt 异常。"""
    return jwt.decode(token, settings.auth_secret, algorithms=["HS256"])


def mask_api_key(api_key: str | None) -> str:
    """将 API Key 脱敏为掩码展示。"""
    if not api_key:
        return ""
    key = api_key.strip()
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}***{key[-4:]}"


def normalize_invite_code(code: str) -> str:
    """规范化邀请码（去空格、大写）。"""
    return "".join(code.strip().upper().split())


def generate_invite_code(length: int = 10) -> str:
    """生成易读一次性邀请码。"""
    raw = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(length))
    if length >= 8:
        return f"{raw[:4]}-{raw[4:]}"
    return raw


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """按用户名查找用户。"""
    result = await db.execute(select(User).where(User.username == username.strip()))
    return result.scalar_one_or_none()


async def get_unused_invite(db: AsyncSession, code: str) -> InviteCode | None:
    """查找尚未使用的邀请码。"""
    normalized = normalize_invite_code(code)
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == normalized,
            InviteCode.used_by_user_id.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def ensure_profile_for_user(db: AsyncSession, user: User) -> UserProfile:
    """确保用户有且仅有一条资料记录（多余行删除）。"""
    result = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == user.id)
        .order_by(UserProfile.id.asc())
    )
    profiles = list(result.scalars().all())
    if profiles:
        keep = profiles[0]
        for extra in profiles[1:]:
            await db.delete(extra)
        await db.flush()
        return keep
    profile = UserProfile(user_id=user.id, nickname=user.username or "我")
    db.add(profile)
    await db.flush()
    return profile


async def bootstrap_admin_if_empty(db: AsyncSession) -> User | None:
    """
    库中无用户时，按配置创建管理员账号。
    返回新建或已有的第一个管理员；若未创建则返回 None。
    """
    result = await db.execute(select(User).limit(1))
    existing = result.scalar_one_or_none()
    if existing:
        admin = await db.execute(select(User).where(User.is_admin.is_(True)).limit(1))
        return admin.scalar_one_or_none() or existing

    username = (settings.bootstrap_admin_user or "").strip()
    password = settings.bootstrap_admin_password or ""
    if not username or not password:
        return None

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    # 暂不建资料：留给 assign_orphan 把旧 user_profile 挂过来
    await db.commit()
    await db.refresh(user)
    return user
