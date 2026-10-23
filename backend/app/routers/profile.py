"""当前用户资料：昵称与头像。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserProfile
from app.schemas import ProfileOut, ProfileUpdate
from app.services.auth import ensure_profile_for_user
from app.services.files import save_upload

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_profile_row(db: AsyncSession, user: User) -> UserProfile:
    """读取当前用户资料，不存在则创建。"""
    await ensure_profile_for_user(db, user)
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    return result.scalar_one()


@router.get("", response_model=ProfileOut)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """获取我的资料。"""
    return await _get_profile_row(db, user)


@router.patch("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """更新我的昵称。"""
    profile = await _get_profile_row(db, user)
    if body.nickname is not None:
        profile.nickname = body.nickname.strip()
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/avatar", response_model=ProfileOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """上传我的头像。"""
    profile = await _get_profile_row(db, user)
    try:
        profile.avatar_url = await save_upload(
            settings.upload_dir, file, f"u{user.id}/profile"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(profile)
    return profile
