"""组装发给模型的对话上下文（最近 N 条 + 记忆块；图片走多模态）。"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Contact, Message
from app.services.bubbles import im_system_prompt, proactive_user_trigger

_ERROR_PREFIX = "[错误]"
HISTORY_LIMIT = 50


def _resolve_upload_path(attachment_url: str | None) -> Path | None:
    """将 /uploads/... URL 解析为本地文件路径。"""
    if not attachment_url or not attachment_url.startswith("/uploads/"):
        return None
    rel = attachment_url[len("/uploads/") :].lstrip("/")
    path = (settings.upload_dir / rel).resolve()
    try:
        path.relative_to(settings.upload_dir.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def image_to_data_url(attachment_url: str | None) -> str | None:
    """读取上传图片并转为 data URL，供多模态接口使用。"""
    path = _resolve_upload_path(attachment_url)
    if not path:
        return None
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    raw = path.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        # 过大则不塞进模型，避免超时
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def message_to_llm_text(msg: Message) -> str | None:
    """将单条消息转为纯文本（兼容旧逻辑）。"""
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


def message_to_llm_content(msg: Message) -> str | list[dict[str, Any]] | None:
    """
    转为 API content：普通文本为 str；用户图片为多模态 content 数组。
    """
    if msg.role not in ("user", "assistant"):
        return None
    text = msg.content or ""
    if msg.role == "assistant" and text.startswith(_ERROR_PREFIX):
        return None

    if msg.role == "user" and msg.attachment_kind == "image" and msg.attachment_url:
        data_url = image_to_data_url(msg.attachment_url)
        caption = text.strip() or "（用户发送了一张图片，请结合图片内容自然回复）"
        if data_url:
            return [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        return caption

    if msg.attachment_kind == "file" and msg.attachment_name:
        return f"[文件 {msg.attachment_name}] {text}".strip() or f"[文件 {msg.attachment_name}]"
    if msg.attachment_kind == "image" and not text.strip():
        return "[用户发送了一张图片]"
    return text


def content_as_plain_text(content: str | list[dict[str, Any]] | None) -> str:
    """从可能是多模态的 content 抽出纯文本（用于搜索 ori_question 等）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return " ".join(parts).strip()


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
) -> list[dict[str, Any]]:
    """
    组装 DeepSeek messages（用户图片为多模态 content）。
    """
    history = await load_recent_messages(db, contact.id)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": im_system_prompt(contact.persona, memory_block)},
    ]
    for msg in history:
        content = message_to_llm_content(msg)
        if content is None:
            continue
        messages.append({"role": msg.role, "content": content})

    if proactive:
        messages.append({"role": "user", "content": proactive_user_trigger()})
    elif user_text is not None:
        if not (
            history
            and history[-1].role == "user"
            and (history[-1].content or "").strip() == user_text.strip()
        ):
            messages.append({"role": "user", "content": user_text})
    return messages
