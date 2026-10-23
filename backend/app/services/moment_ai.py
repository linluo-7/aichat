"""朋友圈文案生成：首评、再回、联系人自发动态。"""
from __future__ import annotations

import json
from typing import Any

from app.models import Contact, MomentPost
from app.services.bubbles import parse_extract_result
from app.services.context_builder import image_to_data_url
from app.services.deepseek import DeepSeekError, chat_completion
from app.services.llm_profiles import resolve_model_params
from app.services.memory_recall import assemble_memory_block
from app.services.memory_store import list_active_memories


def _params(contact: Contact) -> dict[str, Any]:
    return resolve_model_params(contact.model_profile)


async def _memory_hint(db, contact: Contact) -> str:
    if not contact.memory_enabled:
        return ""
    memories = await list_active_memories(db, contact.id)
    block, _ = assemble_memory_block(memories, [])
    return block


async def generate_root_comment(
    db,
    contact: Contact,
    post: MomentPost,
    image_urls: list[str],
    author_name: str,
) -> str:
    """生成联系人对用户动态的首评（短、口语）。"""
    memory = await _memory_hint(db, contact)
    system = (
        f"你是「{contact.name}」。正在刷朋友圈，看到好友「{author_name}」发的一条动态。"
        "用朋友圈评论语气写一句很短的评论（不超过 40 字），自然、像真人。"
        "不要说自己是 AI，不要用列表，不要引号包裹整句。"
        f"角色设定：{(contact.persona or '')[:800]}\n"
        f"{memory}"
        '\n输出 JSON：{"comment":"评论内容"}'
    )
    user_parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"动态正文：{(post.content or '').strip() or '（无文字，只有图片）'}",
        }
    ]
    for url in image_urls[:3]:
        data = image_to_data_url(url)
        if data:
            user_parts.append({"type": "image_url", "image_url": {"url": data}})

    params = _params(contact)
    raw = await chat_completion(
        contact.api_key,
        [{"role": "system", "content": system}, {"role": "user", "content": user_parts}],
        model=params["model"],
        extra=params.get("extra") or {},
        response_format={"type": "json_object"},
        timeout=60.0,
    )
    data = parse_extract_result(raw) or {}
    text = str(data.get("comment") or "").strip() or raw.strip()[:40]
    return text[:120] or "哈哈"


async def generate_reply_to_user(
    db,
    contact: Contact,
    post: MomentPost,
    root_comment: str,
    user_reply: str,
) -> str:
    """用户回复首评后，联系人再回一句。"""
    memory = await _memory_hint(db, contact)
    system = (
        f"你是「{contact.name}」。在朋友圈评论里和好友互动。"
        "对方回复了你的评论，你再回一句很短的话（不超过 40 字）。"
        "口语、自然，不要提 AI。"
        f"角色设定：{(contact.persona or '')[:800]}\n{memory}"
        '\n输出 JSON：{"comment":"回复内容"}'
    )
    user = (
        f"动态：{(post.content or '')[:200]}\n"
        f"你之前的评论：{root_comment}\n"
        f"好友回复你：{user_reply}"
    )
    params = _params(contact)
    raw = await chat_completion(
        contact.api_key,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=params["model"],
        extra=params.get("extra") or {},
        response_format={"type": "json_object"},
        timeout=60.0,
    )
    data = parse_extract_result(raw) or {}
    text = str(data.get("comment") or "").strip() or raw.strip()[:40]
    return text[:120] or "嗯嗯"


async def generate_contact_post(db, contact: Contact) -> str:
    """联系人自发一条朋友圈正文（可无图）。"""
    memory = await _memory_hint(db, contact)
    system = (
        f"你是「{contact.name}」，正在发一条朋友圈。"
        "写一段很短的生活感文字（不超过 60 字），像真人随手发的，不要标题，不要列表。"
        "不要提 AI、系统、角色设定。"
        f"角色设定：{(contact.persona or '')[:800]}\n{memory}"
        '\n输出 JSON：{"content":"朋友圈正文"}'
    )
    params = _params(contact)
    raw = await chat_completion(
        contact.api_key,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "发一条今天的朋友圈吧。"},
        ],
        model=params["model"],
        extra=params.get("extra") or {},
        response_format={"type": "json_object"},
        timeout=60.0,
    )
    data = parse_extract_result(raw) or {}
    text = str(data.get("content") or "").strip() or raw.strip()[:60]
    return text[:200] or "今天天气不错～"
