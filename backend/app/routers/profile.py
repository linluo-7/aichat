"""当前用户资料：昵称与头像。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import UserProfile
from app.schemas import ProfileOut, ProfileUpdate
from app.services.files import save_upload
from app.services.profile_seed import ensure_user_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_profile_row(db: AsyncSession) -> UserProfile:
    """读取 id=1 的用户资料，不存在则创建。"""
    await ensure_user_profile(db)
    result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    profile = result.scalar_one()
    return profile


@router.get("", response_model=ProfileOut)
async def get_profile(db: AsyncSession = Depends(get_db)) -> UserProfile:
    """获取我的资料。"""
    return await _get_profile_row(db)


@router.patch("", response_model=ProfileOut)
async def update_profile(body: ProfileUpdate, db: AsyncSession = Depends(get_db)) -> UserProfile:
    """更新我的昵称。"""
    profile = await _get_profile_row(db)
    if body.nickname is not None:
        profile.nickname = body.nickname.strip()
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/avatar", response_model=ProfileOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    """上传我的头像。"""
    profile = await _get_profile_row(db)
    try:
        profile.avatar_url = await save_upload(settings.upload_dir, file, "profile")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(profile)
    return profile
