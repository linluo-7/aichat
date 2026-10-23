"""记忆整理：触发判断、提示词、结果校验与落库。"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Contact, Message, ReplyJob
from app.services.bubbles import parse_extract_result
from app.services.deepseek import DeepSeekError, chat_completion
from app.services.llm_profiles import resolve_model_params
from app.services.memory_store import (
    add_memory,
    get_or_create_state,
    list_active_memories,
)
from app.utils.datetime_util import utc_now

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _beijing_today() -> date:
    return datetime.now(SHANGHAI).date()


def _fmt_msg_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M")


async def should_extract(db: AsyncSession, contact: Contact) -> bool:
    """确定性触发条件：是否应对该联系人执行记忆整理。"""
    if not contact.memory_enabled:
        return False

    # 正在生成回复时不整理
    busy = await db.execute(
        select(ReplyJob.id)
        .where(ReplyJob.contact_id == contact.id, ReplyJob.status == "running")
        .limit(1)
    )
    if busy.scalar_one_or_none():
        return False

    state = await get_or_create_state(db, contact.id)
    today = _beijing_today()
    if state.runs_day != today:
        state.runs_day = today
        state.runs_today = 0
        await db.commit()

    if (state.fail_count or 0) >= 3 and state.runs_day == today:
        return False
    if (state.runs_today or 0) >= settings.memory_extract_daily_max:
        return False

    cursor = state.last_extracted_message_id or 0
    count_q = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(
            Message.contact_id == contact.id,
            Message.role.in_(["user", "assistant"]),
            Message.id > cursor,
        )
    )
    new_count = int(count_q.scalar_one() or 0)
    if new_count <= 0:
        return False

    if new_count >= settings.memory_extract_message_threshold:
        return True

    if new_count >= 2:
        last_q = await db.execute(
            select(Message.created_at)
            .where(Message.contact_id == contact.id, Message.role.in_(["user", "assistant"]))
            .order_by(Message.id.desc())
            .limit(1)
        )
        last_at = last_q.scalar_one_or_none()
        if last_at:
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            idle = utc_now() - last_at
            if idle >= timedelta(minutes=settings.memory_extract_idle_minutes):
                return True
    return False


def _build_extract_prompt(
    contact_name: str,
    today: date,
    existing: list,
    messages: list[Message],
) -> list[dict[str, str]]:
    """组装记忆整理提示。"""
    mem_lines = []
    for m in existing:
        mem_lines.append(f"- id={m.id} [{m.category}] {m.content}")
    msg_lines = []
    for msg in messages:
        role = "用户" if msg.role == "user" else contact_name
        msg_lines.append(f"[{_fmt_msg_time(msg.created_at)}] {role}: {msg.content[:500]}")

    system = (
        "你是记忆整理助手。从对话中抽取以后聊天用得上的事实，输出 JSON。\n"
        '格式：{"add":[{"category":"profile|relationship|event","content":"短句",'
        '"importance":1-5,"occurred_at":"YYYY-MM-DD或null","replaces":[旧id]}]}\n'
        "规则：\n"
        "- 只用第三人称短句，如「用户养了一只叫团子的猫」「我答应用户周六陪他看电影」。\n"
        "- 寒暄闲聊不记；已有记忆不重复。\n"
        "- 与已有记忆矛盾时在 replaces 填旧 id。\n"
        "- 相对时间换算成具体日期（今天是 " + today.isoformat() + "）。\n"
        "- category: profile=用户信息偏好；relationship=称呼约定承诺；event=具体往事。\n"
        "- 若无新事实，输出 {\"add\":[]}。"
    )
    user = (
        f"角色名：{contact_name}\n"
        f"现有记忆：\n" + ("\n".join(mem_lines) if mem_lines else "（无）") + "\n\n"
        f"新消息：\n" + ("\n".join(msg_lines) if msg_lines else "（无）")
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def run_extract_for_contact(db: AsyncSession, contact: Contact) -> dict:
    """对单个联系人执行一次记忆整理。"""
    state = await get_or_create_state(db, contact.id)
    cursor = state.last_extracted_message_id or 0
    result = await db.execute(
        select(Message)
        .where(
            Message.contact_id == contact.id,
            Message.role.in_(["user", "assistant"]),
            Message.id > cursor,
        )
        .order_by(Message.id.asc())
        .limit(40)
    )
    messages = list(result.scalars().all())
    if not messages:
        return {"added": 0, "retired": 0, "dropped": 0}

    existing = await list_active_memories(db, contact.id)
    today = _beijing_today()
    llm_messages = _build_extract_prompt(contact.name, today, existing, messages)
    params = resolve_model_params(contact.model_profile)

    try:
        raw = await chat_completion(
            contact.api_key,
            llm_messages,
            model=params["model"],
            extra=params.get("extra") or {},
            response_format={"type": "json_object"},
            timeout=90.0,
        )
    except DeepSeekError as exc:
        state.last_error = str(exc)[:512]
        state.fail_count = (state.fail_count or 0) + 1
        state.last_run_at = utc_now()
        await db.commit()
        raise

    data = parse_extract_result(raw) or {}
    adds = data.get("add") if isinstance(data.get("add"), list) else []
    from_id = messages[0].id
    to_id = messages[-1].id
    added = 0
    retired = 0
    dropped = 0

    for item in adds:
        if not isinstance(item, dict):
            dropped += 1
            continue
        category = item.get("category")
        content = item.get("content")
        importance = item.get("importance", 3)
        occurred_raw = item.get("occurred_at")
        replaces = item.get("replaces") or []
        if category not in ("profile", "relationship", "event"):
            dropped += 1
            continue
        if not content or not str(content).strip():
            dropped += 1
            continue
        occurred_at = None
        if occurred_raw and str(occurred_raw).lower() not in ("null", "none", ""):
            try:
                occurred_at = date.fromisoformat(str(occurred_raw)[:10])
            except ValueError:
                occurred_at = None
        if not isinstance(replaces, list):
            replaces = []
        replace_ids = [int(x) for x in replaces if str(x).isdigit() or isinstance(x, int)]

        before_ids = {m.id for m in await list_active_memories(db, contact.id)}
        mem = await add_memory(
            db,
            contact.id,
            category=category,
            content=str(content),
            importance=int(importance) if str(importance).isdigit() or isinstance(importance, int) else 3,
            source="ai",
            occurred_at=occurred_at,
            from_message_id=from_id,
            to_message_id=to_id,
            replaces=replace_ids,
        )
        if mem is None:
            dropped += 1
        else:
            added += 1
            after = await list_active_memories(db, contact.id)
            # 粗略统计退役：replaces 成功的
            for rid in replace_ids:
                if rid in before_ids and rid not in {m.id for m in after}:
                    retired += 1

    # 成功才推进游标
    state = await get_or_create_state(db, contact.id)
    state.last_extracted_message_id = to_id
    state.last_run_at = utc_now()
    state.last_added = added
    state.last_retired = retired
    state.last_dropped = dropped
    state.last_error = None
    state.fail_count = 0
    if state.runs_day != today:
        state.runs_day = today
        state.runs_today = 0
    state.runs_today = (state.runs_today or 0) + 1
    await db.commit()
    return {"added": added, "retired": retired, "dropped": dropped}
