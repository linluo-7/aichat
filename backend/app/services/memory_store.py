"""记忆增删改查、去重、数量上限淘汰。"""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Memory, MemoryState
from app.utils.datetime_util import utc_now


def char_bigrams(text: str) -> set[str]:
    """中英混合字符二元组，用于近似去重与检索。"""
    s = "".join(text.lower().split())
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def bigram_similarity(a: str, b: str) -> float:
    """二元组 Jaccard 相似度。"""
    sa, sb = char_bigrams(a), char_bigrams(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


async def get_or_create_state(db: AsyncSession, contact_id: int) -> MemoryState:
    """获取或创建联系人记忆状态行。"""
    state = await db.get(MemoryState, contact_id)
    if state:
        return state
    state = MemoryState(contact_id=contact_id)
    db.add(state)
    await db.commit()
    await db.refresh(state)
    return state


async def list_active_memories(db: AsyncSession, contact_id: int) -> list[Memory]:
    """列出有效记忆。"""
    result = await db.execute(
        select(Memory)
        .where(Memory.contact_id == contact_id, Memory.status == "active")
        .order_by(Memory.pinned.desc(), Memory.importance.desc(), Memory.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_retired_memories(db: AsyncSession, contact_id: int, *, limit: int = 50) -> list[Memory]:
    """列出已退役记忆。"""
    result = await db.execute(
        select(Memory)
        .where(Memory.contact_id == contact_id, Memory.status == "retired")
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_unseen(db: AsyncSession, contact_id: int) -> int:
    """未读记忆条数。"""
    result = await db.execute(
        select(func.count())
        .select_from(Memory)
        .where(
            Memory.contact_id == contact_id,
            Memory.status == "active",
            Memory.seen.is_(False),
        )
    )
    return int(result.scalar_one() or 0)


async def mark_all_seen(db: AsyncSession, contact_id: int) -> None:
    """打开记忆页后标记已读。"""
    result = await db.execute(
        select(Memory).where(
            Memory.contact_id == contact_id,
            Memory.status == "active",
            Memory.seen.is_(False),
        )
    )
    for m in result.scalars().all():
        m.seen = True
    await db.commit()


async def mark_digest_stale(db: AsyncSession, contact_id: int) -> None:
    """记忆变化后标记总结过期。"""
    state = await get_or_create_state(db, contact_id)
    state.digest_stale = True
    await db.commit()


async def add_memory(
    db: AsyncSession,
    contact_id: int,
    *,
    category: str,
    content: str,
    importance: int = 3,
    source: str = "ai",
    pinned: bool = False,
    occurred_at: date | None = None,
    from_message_id: int | None = None,
    to_message_id: int | None = None,
    replaces: list[int] | None = None,
) -> Memory | None:
    """
    新增一条记忆；近似重复则跳过返回 None。
    replaces：可退役的旧 AI 记忆 id 列表。
    """
    content = (content or "").strip()[:120]
    if not content:
        return None
    if category not in ("profile", "relationship", "event"):
        return None
    importance = max(1, min(5, int(importance or 3)))

    actives = await list_active_memories(db, contact_id)
    for m in actives:
        if bigram_similarity(m.content, content) >= 0.8:
            return None

    mem = Memory(
        contact_id=contact_id,
        category=category,
        content=content,
        importance=importance,
        source=source,
        pinned=pinned,
        occurred_at=occurred_at,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
        seen=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(mem)
    await db.flush()

    retired = 0
    for old_id in replaces or []:
        old = await db.get(Memory, old_id)
        if not old or old.contact_id != contact_id:
            continue
        if old.source != "ai" or old.pinned or old.status != "active":
            continue
        old.status = "retired"
        old.superseded_by = mem.id
        old.updated_at = utc_now()
        retired += 1

    await db.commit()
    await db.refresh(mem)
    await enforce_active_limit(db, contact_id)
    await mark_digest_stale(db, contact_id)
    return mem


async def enforce_active_limit(db: AsyncSession, contact_id: int) -> int:
    """有效记忆超过上限时退役得分最低的非置顶事件记忆。"""
    actives = await list_active_memories(db, contact_id)
    limit = settings.memory_active_max
    if len(actives) <= limit:
        return 0
    # 优先淘汰未置顶的 event，按重要度升序、use_count 升序
    candidates = [
        m
        for m in actives
        if not m.pinned and m.category == "event" and m.source == "ai"
    ]
    candidates.sort(key=lambda m: (m.importance, m.use_count, m.id))
    need = len(actives) - limit
    retired = 0
    for m in candidates:
        if retired >= need:
            break
        m.status = "retired"
        m.updated_at = utc_now()
        retired += 1
    if retired:
        await db.commit()
        await mark_digest_stale(db, contact_id)
    return retired


async def update_memory(
    db: AsyncSession,
    memory_id: int,
    *,
    content: str | None = None,
    pinned: bool | None = None,
) -> Memory:
    """编辑记忆内容或置顶；编辑后 source=user。"""
    mem = await db.get(Memory, memory_id)
    if not mem or mem.status != "active":
        raise ValueError("记忆不存在")
    if content is not None:
        mem.content = content.strip()[:120]
        mem.source = "user"
    if pinned is not None:
        mem.pinned = pinned
    mem.updated_at = utc_now()
    await db.commit()
    await db.refresh(mem)
    await mark_digest_stale(db, mem.contact_id)
    return mem


async def delete_memory(db: AsyncSession, memory_id: int) -> int:
    """物理删除一条记忆，返回 contact_id。"""
    mem = await db.get(Memory, memory_id)
    if not mem:
        raise ValueError("记忆不存在")
    contact_id = mem.contact_id
    await db.delete(mem)
    await db.commit()
    await mark_digest_stale(db, contact_id)
    return contact_id


async def clear_memories(db: AsyncSession, contact_id: int) -> int:
    """清空联系人全部记忆。"""
    result = await db.execute(select(Memory).where(Memory.contact_id == contact_id))
    rows = list(result.scalars().all())
    for m in rows:
        await db.delete(m)
    state = await get_or_create_state(db, contact_id)
    state.digest = None
    state.digest_at = None
    state.digest_stale = True
    await db.commit()
    return len(rows)


async def touch_used(db: AsyncSession, memories: list[Memory]) -> None:
    """注入上下文后更新使用统计。"""
    now = utc_now()
    for m in memories:
        m.last_used_at = now
        m.use_count = (m.use_count or 0) + 1
    if memories:
        await db.commit()
