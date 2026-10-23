"""联系人列表：附带最近一条消息摘要。"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Message


def _preview_text(content: str, max_len: int = 48) -> str:
    """将消息内容压缩为列表摘要一行。"""
    text = content.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _message_preview(content: str, attachment_kind: str | None, attachment_name: str | None) -> str:
    """根据消息内容与附件生成会话列表摘要。"""
    if attachment_kind == "image":
        return "[图片]"
    if attachment_kind == "file":
        name = (attachment_name or "文件").strip()
        if content.strip():
            return _preview_text(content)
        return f"[文件] {_preview_text(name, 20)}"
    return _preview_text(content)


async def fetch_contacts_with_last_message(
    db: AsyncSession,
    *,
    user_id: int,
) -> list[tuple[Contact, str | None, datetime | None]]:
    """
    查询指定用户的联系人及各自最近一条 user/assistant 消息。
    返回 (联系人, 摘要文本, 消息时间)，按最近聊天时间倒序。
    """
    contacts_result = await db.execute(select(Contact).where(Contact.user_id == user_id))
    contacts = list(contacts_result.scalars().all())
    if not contacts:
        return []

    row_num = func.row_number().over(
        partition_by=Message.contact_id,
        order_by=(Message.created_at.desc(), Message.id.desc()),
    )
    inner = (
        select(
            Message.contact_id,
            Message.content,
            Message.attachment_kind,
            Message.attachment_name,
            Message.created_at,
            row_num.label("rn"),
        )
        .where(Message.role.in_(["user", "assistant"]))
        .subquery()
    )
    last_result = await db.execute(select(inner).where(inner.c.rn == 1))
    last_map: dict[int, tuple[str, datetime]] = {}
    for row in last_result.all():
        preview = _message_preview(row.content, row.attachment_kind, row.attachment_name)
        last_map[row.contact_id] = (preview, row.created_at)

    rows: list[tuple[Contact, str | None, datetime | None]] = []
    for contact in contacts:
        last = last_map.get(contact.id)
        if last:
            rows.append((contact, last[0], last[1]))
        else:
            rows.append((contact, None, None))

    rows.sort(
        key=lambda item: (
            item[2] is not None,
            item[2] or item[0].updated_at or item[0].created_at,
        ),
        reverse=True,
    )
    return rows
