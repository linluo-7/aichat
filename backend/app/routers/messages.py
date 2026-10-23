"""发消息与历史分页（非流式；回复由后台 Worker 生成）。"""
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_owned_contact
from app.models import Contact, Message, User
from app.schemas import ChatRequest, MessageOut, MessagesPageOut
from app.services.files import save_chat_attachment
from app.services.reply_jobs import enqueue_user_reply
from app.utils.datetime_util import utc_now

router = APIRouter(prefix="/api/contacts", tags=["messages"])


def _display_content_for_file(kind: str, name: str, text_for_ai: str) -> str:
    """聊天界面展示用的用户消息文本。"""
    if kind == "image":
        return ""
    if kind == "file" and "内容如下" in text_for_ai:
        marker = "内容如下：\n\n"
        idx = text_for_ai.find(marker)
        if idx >= 0:
            body = text_for_ai[idx + len(marker) :].strip()
            if len(body) > 600:
                body = body[:599] + "…"
            return body
    return f"[文件] {name}"


async def _after_user_message(db: AsyncSession, contact: Contact) -> None:
    """用户发消息后：清零自动连发计数、推迟自动时间、入队回复任务。"""
    now = utc_now()
    contact.auto_message_streak = 0
    interval = max(1, contact.auto_message_interval_minutes or 30)
    contact.auto_message_next_at = now + timedelta(minutes=interval)
    await db.commit()
    await enqueue_user_reply(db, contact.id)


@router.get("/{contact_id}/messages", response_model=MessagesPageOut)
async def list_messages(
    contact: Contact = Depends(get_owned_contact),
    before_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> MessagesPageOut:
    """历史分页：按 id 倒序取、正序返回。"""
    q = select(Message).where(
        Message.contact_id == contact.id,
        Message.role.in_(["user", "assistant"]),
    )
    if before_id is not None:
        q = q.where(Message.id < before_id)
    q = q.order_by(Message.id.desc()).limit(limit + 1)
    result = await db.execute(q)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    return MessagesPageOut(messages=rows, has_more=has_more)


@router.post("/{contact_id}/messages", response_model=MessageOut, status_code=201)
async def post_message(
    body: ChatRequest,
    contact: Contact = Depends(get_owned_contact),
    db: AsyncSession = Depends(get_db),
) -> Message:
    """发送文本消息，创建回复任务后立即返回。"""
    user_text = body.content.strip()
    user_msg = Message(
        contact_id=contact.id,
        role="user",
        content=user_text,
        created_at=utc_now(),
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    await _after_user_message(db, contact)
    return user_msg


@router.post("/{contact_id}/messages/file", response_model=MessageOut, status_code=201)
async def post_message_file(
    contact: Contact = Depends(get_owned_contact),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Message:
    """上传图片/文件作为用户消息并入队回复。"""
    try:
        url, kind, name, text_for_ai, _raw = await save_chat_attachment(
            settings.upload_dir, file, subfolder=f"u{user.id}/chat_files"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    display = _display_content_for_file(kind, name, text_for_ai)
    content = display if display.strip() else (
        "[用户发送了一张图片]" if kind == "image" else f"[文件 {name}]"
    )
    if kind == "file" and text_for_ai and len(text_for_ai) > len(content):
        content = text_for_ai[:4000]

    user_msg = Message(
        contact_id=contact.id,
        role="user",
        content=display if kind == "image" else content,
        attachment_url=url,
        attachment_name=name,
        attachment_kind=kind,
        created_at=utc_now(),
    )
    if kind == "image":
        user_msg.content = ""
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    await _after_user_message(db, contact)
    return user_msg
