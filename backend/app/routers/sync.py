"""增量同步与任务重试。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Contact, Message, User
from app.schemas import ContactListItem, FailedJobOut, SyncOut
from app.services.auth import mask_api_key
from app.services.contact_list import fetch_contacts_with_last_message
from app.services.memory_store import count_unseen
from app.services.reply_jobs import (
    list_busy_contact_ids,
    list_recent_failed_jobs,
    list_typing_contact_ids,
    retry_failed_job,
)
from app.utils.datetime_util import to_utc_iso, utc_now

router = APIRouter(prefix="/api", tags=["sync"])


@router.get("/sync", response_model=SyncOut)
async def sync(
    after_id: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncOut:
    """增量拉取新消息、正在输入、失败任务与联系人摘要（仅当前用户）。"""
    result = await db.execute(
        select(Message)
        .join(Contact, Contact.id == Message.contact_id)
        .where(
            Message.id > after_id,
            Message.role.in_(["user", "assistant"]),
            Contact.user_id == user.id,
        )
        .order_by(Message.id.asc())
        .limit(201)
    )
    rows = list(result.scalars().all())
    has_more = len(rows) > 200
    rows = rows[:200]

    typing_ids = await list_typing_contact_ids(db, user_id=user.id)
    busy_ids = await list_busy_contact_ids(db, user_id=user.id)
    failed = await list_recent_failed_jobs(db, user_id=user.id)
    failed_out = [
        FailedJobOut(id=j.id, contact_id=j.contact_id, error=j.error) for j in failed
    ]

    all_rows = await fetch_contacts_with_last_message(db, user_id=user.id)
    contacts_out: list[ContactListItem] = []
    for c, preview, last_at in all_rows:
        unseen = await count_unseen(db, c.id) if c.memory_enabled else 0
        contacts_out.append(
            ContactListItem(
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
                memory_unseen=unseen,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message_preview=preview,
                last_message_at=last_at,
            )
        )

    return SyncOut(
        messages=rows,
        has_more=has_more,
        typing_contact_ids=typing_ids,
        busy_contact_ids=busy_ids,
        contacts=contacts_out,
        failed_jobs=failed_out,
        server_time=to_utc_iso(utc_now()) or "",
    )


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """重试失败的回复任务（须属于当前用户）。"""
    from app.models import ReplyJob

    job = await db.get(ReplyJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    contact = await db.get(Contact, job.contact_id)
    if not contact or contact.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        job = await retry_failed_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "id": job.id}
