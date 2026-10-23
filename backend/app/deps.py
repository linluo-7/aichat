"""FastAPI 依赖：当前登录用户、联系人归属校验。"""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Contact, User
from app.services.auth import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer Token 解析当前用户；无效则 401。"""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload.get("sub", "0"))
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录") from exc

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="账号不可用，请重新登录")
    return user


async def get_owned_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """获取属于当前用户的联系人；否则 404（不暴露他人存在）。"""
    contact = await db.get(Contact, contact_id)
    if not contact or contact.user_id != user.id:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return contact
