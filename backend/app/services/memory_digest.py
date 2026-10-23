"""「Ta 眼中的你」总结生成与缓存。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact
from app.services.bubbles import parse_extract_result
from app.services.deepseek import DeepSeekError, chat_completion
from app.services.llm_profiles import resolve_model_params
from app.services.memory_store import get_or_create_state, list_active_memories
from app.utils.datetime_util import utc_now


async def generate_digest(db: AsyncSession, contact: Contact, *, force: bool = False) -> str:
    """
    生成或返回缓存的「Ta 眼中的你」总结。
    只根据有效记忆条目，不读原始聊天。
    """
    state = await get_or_create_state(db, contact.id)
    if not force and not state.digest_stale and state.digest:
        return state.digest

    memories = await list_active_memories(db, contact.id)
    if not memories:
        text = "还没有记住关于你的事。"
        state.digest = text
        state.digest_at = utc_now()
        state.digest_stale = False
        await db.commit()
        return text

    lines = []
    for m in memories[:80]:
        lines.append(f"[{m.category}] {m.content}")

    system = (
        f"你是角色「{contact.name}」。根据下列记忆，用第一人称写一段不超过 200 字的总结，"
        "像在跟对方介绍「我眼中的你」。口语化，不要列表，不要提「记忆」「系统」。"
        '输出 JSON：{"digest":"总结正文"}'
    )
    user = "记忆列表：\n" + "\n".join(lines)
    params = resolve_model_params(contact.model_profile)

    try:
        raw = await chat_completion(
            contact.api_key,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=params["model"],
            extra=params.get("extra") or {},
            response_format={"type": "json_object"},
            timeout=60.0,
        )
        data = parse_extract_result(raw) or {}
        text = str(data.get("digest") or "").strip()
        if not text:
            text = raw.strip()[:200]
    except DeepSeekError as exc:
        # 失败时若有旧总结则保留，否则返回可读错误提示
        if state.digest:
            return state.digest
        return f"（总结生成失败：{exc}）"

    text = text[:200]
    state.digest = text
    state.digest_at = utc_now()
    state.digest_stale = False
    await db.commit()
    return text
