"""登录、邀请码校验与注册、改密。"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import InviteCode, User
from app.services.auth import (
    create_access_token,
    ensure_profile_for_user,
    get_unused_invite,
    get_user_by_username,
    hash_password,
    normalize_invite_code,
    verify_password,
)
from app.utils.datetime_util import utc_now

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 简易内存限流：ip -> [timestamps]
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60.0
_RATE_MAX = 30


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit(request: Request) -> None:
    """登录/注册接口简单防刷。"""
    ip = _client_ip(request)
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    _rate_buckets[ip] = [t for t in bucket if now - t < _RATE_WINDOW]
    if len(_rate_buckets[ip]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _rate_buckets[ip].append(now)


class InviteCheckIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)


class InviteCheckOut(BaseModel):
    ok: bool
    message: str = ""


class RegisterIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


class TokenOut(BaseModel):
    token: str
    user: UserOut


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, is_admin=bool(user.is_admin))


@router.post("/invite/check", response_model=InviteCheckOut)
async def check_invite(
    body: InviteCheckIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> InviteCheckOut:
    """校验邀请码是否可用（未使用）。"""
    _rate_limit(request)
    invite = await get_unused_invite(db, body.code)
    if not invite:
        return InviteCheckOut(ok=False, message="邀请码无效或已被使用")
    return InviteCheckOut(ok=True, message="邀请码可用")


@router.post("/register", response_model=TokenOut)
async def register(
    body: RegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """邀请码注册：核销邀请码并创建用户，返回登录 token。"""
    _rate_limit(request)
    username = body.username.strip()
    if not username or any(ch.isspace() for ch in username):
        raise HTTPException(status_code=400, detail="用户名不能包含空格")
    if await get_user_by_username(db, username):
        raise HTTPException(status_code=400, detail="用户名已被占用")

    code = normalize_invite_code(body.code)
    invite = await get_unused_invite(db, code)
    if not invite:
        raise HTTPException(status_code=400, detail="邀请码无效或已被使用")

    user = User(
        username=username,
        password_hash=hash_password(body.password),
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 原子核销：仅当仍未使用时写入
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.id == invite.id,
            InviteCode.used_by_user_id.is_(None),
        )
    )
    locked = result.scalar_one_or_none()
    if not locked:
        await db.rollback()
        raise HTTPException(status_code=400, detail="邀请码无效或已被使用")
    locked.used_by_user_id = user.id
    locked.used_at = utc_now()

    await ensure_profile_for_user(db, user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    return TokenOut(token=token, user=_user_out(user))


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """用户名密码登录。"""
    _rate_limit(request)
    user = await get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已停用")
    token = create_access_token(user.id, user.username)
    return TokenOut(token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    """返回当前登录用户。"""
    return _user_out(user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """修改当前用户密码。"""
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"status": "ok"}
