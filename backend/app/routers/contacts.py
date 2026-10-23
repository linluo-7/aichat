"""联系人 CRUD 与头像、聊天背景上传。"""
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_owned_contact
from app.models import Contact, User
from app.schemas import ContactCreate, ContactListItem, ContactOut, ContactUpdate
from app.services.auth import mask_api_key
from app.services.contact_list import fetch_contacts_with_last_message
from app.services.files import save_upload
from app.services.memory_store import count_unseen
from app.utils.datetime_util import utc_now

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _contact_out(c: Contact, *, memory_unseen: int = 0) -> ContactOut:
    """组装联系人输出（含 Key 掩码）。"""
    return ContactOut(
        id=c.id,
        name=c.name,
        persona=c.persona,
        api_key_masked=mask_api_key(c.api_key),
        avatar_url=c.avatar_url,
        chat_background_url=c.chat_background_url,
        chat_background_mobile_url=c.chat_background_mobile_url,
        auto_message_enabled=c.auto_message_enabled,
        auto_message_interval_minutes=c.auto_message_interval_minutes,
        auto_message_last_at=c.auto_message_last_at,
        memory_enabled=bool(getattr(c, "memory_enabled", True)),
        memory_unseen=memory_unseen,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=list[ContactListItem])
async def list_contacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ContactListItem]:
    """列出当前用户的联系人（含最近消息摘要）。"""
    rows = await fetch_contacts_with_last_message(db, user_id=user.id)
    out: list[ContactListItem] = []
    for c, preview, last_at in rows:
        unseen = await count_unseen(db, c.id) if getattr(c, "memory_enabled", True) else 0
        base = _contact_out(c, memory_unseen=unseen)
        out.append(
            ContactListItem(
                id=base.id,
                name=base.name,
                persona=base.persona,
                api_key_masked=base.api_key_masked,
                avatar_url=base.avatar_url,
                chat_background_url=base.chat_background_url,
                chat_background_mobile_url=base.chat_background_mobile_url,
                auto_message_enabled=base.auto_message_enabled,
                auto_message_interval_minutes=base.auto_message_interval_minutes,
                auto_message_last_at=base.auto_message_last_at,
                memory_enabled=base.memory_enabled,
                memory_unseen=base.memory_unseen,
                created_at=base.created_at,
                updated_at=base.updated_at,
                last_message_preview=preview,
                last_message_at=last_at,
            )
        )
    return out


@router.post("", response_model=ContactOut)
async def create_contact(
    body: ContactCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """创建新联系人。"""
    contact = Contact(
        user_id=user.id,
        name=body.name.strip(),
        persona=body.persona.strip(),
        api_key=body.api_key.strip(),
        memory_enabled=True,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return _contact_out(contact)


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact: Contact = Depends(get_owned_contact),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """获取单个联系人详情。"""
    unseen = await count_unseen(db, contact.id) if contact.memory_enabled else 0
    return _contact_out(contact, memory_unseen=unseen)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    body: ContactUpdate,
    contact: Contact = Depends(get_owned_contact),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """更新联系人名称、设定、API Key、自动消息等。"""
    if body.name is not None:
        contact.name = body.name.strip()
    if body.persona is not None:
        contact.persona = body.persona.strip()
    if body.api_key is not None and body.api_key.strip():
        key = body.api_key.strip()
        if len(key) < 8:
            raise HTTPException(status_code=400, detail="API Key 至少 8 位")
        contact.api_key = key
    if body.memory_enabled is not None:
        contact.memory_enabled = body.memory_enabled
    if body.auto_message_interval_minutes is not None:
        contact.auto_message_interval_minutes = body.auto_message_interval_minutes
        if contact.auto_message_enabled:
            contact.auto_message_next_at = utc_now() + timedelta(
                minutes=contact.auto_message_interval_minutes
            )
    if body.auto_message_enabled is not None:
        if body.auto_message_enabled and not contact.auto_message_enabled:
            contact.auto_message_last_at = utc_now()
            contact.auto_message_streak = 0
            contact.auto_message_next_at = utc_now() + timedelta(
                minutes=max(1, contact.auto_message_interval_minutes or 30)
            )
        if not body.auto_message_enabled:
            contact.auto_message_last_at = None
            contact.auto_message_next_at = None
            contact.auto_message_streak = 0
        contact.auto_message_enabled = body.auto_message_enabled
    await db.commit()
    await db.refresh(contact)
    unseen = await count_unseen(db, contact.id) if contact.memory_enabled else 0
    return _contact_out(contact, memory_unseen=unseen)


@router.delete("/{contact_id}")
async def delete_contact(
    contact: Contact = Depends(get_owned_contact),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除联系人及其消息。"""
    await db.delete(contact)
    await db.commit()
    return {"status": "ok"}


@router.post("/{contact_id}/avatar", response_model=ContactOut)
async def upload_avatar(
    contact: Contact = Depends(get_owned_contact),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """上传联系人头像。"""
    try:
        contact.avatar_url = await save_upload(
            settings.upload_dir, file, f"u{user.id}/avatars"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(contact)
    return _contact_out(contact)


@router.post("/{contact_id}/background/{platform}", response_model=ContactOut)
async def upload_background(
    platform: str,
    contact: Contact = Depends(get_owned_contact),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """上传该联系人的聊天背景图（platform: desktop | mobile）。"""
    if platform not in ("desktop", "mobile"):
        raise HTTPException(status_code=400, detail="platform 须为 desktop 或 mobile")
    try:
        url = await save_upload(settings.upload_dir, file, f"u{user.id}/backgrounds")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if platform == "mobile":
        contact.chat_background_mobile_url = url
    else:
        contact.chat_background_url = url
    await db.commit()
    await db.refresh(contact)
    return _contact_out(contact)


@router.delete("/{contact_id}/background/{platform}", response_model=ContactOut)
async def clear_background(
    platform: str,
    contact: Contact = Depends(get_owned_contact),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    """清除指定端的聊天背景，恢复默认。"""
    if platform not in ("desktop", "mobile"):
        raise HTTPException(status_code=400, detail="platform 须为 desktop 或 mobile")
    if platform == "mobile":
        contact.chat_background_mobile_url = None
    else:
        contact.chat_background_url = None
    await db.commit()
    await db.refresh(contact)
    return _contact_out(contact)
