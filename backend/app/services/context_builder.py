"""组装发给模型的对话上下文（最近 N 条 + 记忆块）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Message
from app.services.bubbles import im_system_prompt, proactive_user_trigger

# 错误前缀：不进入上下文
_ERROR_PREFIX = "[错误]"
HISTORY_LIMIT = 50


def message_to_llm_text(msg: Message) -> str | None:
    """将单条消息转为发给模型的文本；错误气泡返回 None。"""
    if msg.role not in ("user", "assistant"):
        return None
    text = msg.content or ""
    if msg.role == "assistant" and text.startswith(_ERROR_PREFIX):
        return None
    if msg.attachment_kind == "image" and not text.strip():
        text = "[用户发送了一张图片]"
    elif msg.attachment_kind == "file" and msg.attachment_name:
        text = f"[文件 {msg.attachment_name}] {text}".strip()
    return text


async def load_recent_messages(
    db: AsyncSession, contact_id: int, *, limit: int = HISTORY_LIMIT
) -> list[Message]:
    """取最近 limit 条消息（按 id 倒序取后反转为正序）。"""
    result = await db.execute(
        select(Message)
        .where(Message.contact_id == contact_id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def build_llm_messages(
    db: AsyncSession,
    contact: Contact,
    *,
    user_text: str | None = None,
    proactive: bool = False,
    memory_block: str = "",
) -> list[dict[str, str]]:
    """
    组装 DeepSeek messages。
    user_text：用户本轮文本（已落库时可传 None，从历史末条读取）。
    proactive：主动消息时追加触发语。
    """
    history = await load_recent_messages(db, contact.id)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": im_system_prompt(contact.persona, memory_block)},
    ]
    for msg in history:
        text = message_to_llm_text(msg)
        if text is None:
            continue
        messages.append({"role": msg.role, "content": text})

    if proactive:
        messages.append({"role": "user", "content": proactive_user_trigger()})
    elif user_text is not None:
        # 若历史末条已是本轮用户消息，不再重复追加
        if not (
            history
            and history[-1].role == "user"
            and (history[-1].content or "").strip() == user_text.strip()
        ):
            messages.append({"role": "user", "content": user_text})
    return messages
