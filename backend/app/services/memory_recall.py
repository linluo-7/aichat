"""记忆检索打分与记忆块组装。"""
import math
from datetime import datetime, timezone

from app.models import Memory
from app.services.memory_store import char_bigrams
from app.utils.datetime_util import utc_now

CORE_CHAR_LIMIT = 1200
EVENT_MAX = 6
EVENT_SCORE_THRESHOLD = 0.3


def _recency_score(last_used_at: datetime | None, now: datetime | None = None) -> float:
    """新近度：exp(-距上次使用天数 / 30)。"""
    now = now or utc_now()
    if last_used_at is None:
        # 从未使用：按创建衰减，用一个中等值
        return 0.5
    ts = last_used_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return math.exp(-days / 30.0)


def keyword_overlap(query: str, content: str) -> float:
    """关键词重合度：二元组比例；内容中的二字片段出现在查询里则大幅加分。"""
    q = (query or "").lower()
    c = (content or "").lower()
    sq, sc = char_bigrams(q), char_bigrams(c)
    base = 0.0
    if sq and sc:
        base = len(sq & sc) / len(sq)
    # 「团子」这类专有名词：二字连续命中优先召回
    for i in range(max(0, len(c) - 1)):
        gram = c[i : i + 2].strip()
        if len(gram) >= 2 and gram in q:
            return max(base, 0.85)
    return base


def score_event(memory: Memory, query: str, now: datetime | None = None) -> float:
    """事件记忆得分：关键词优先，兼顾重要度与新近度。"""
    imp = (memory.importance or 3) / 5.0
    kw = keyword_overlap(query, memory.content or "")
    rec = _recency_score(memory.last_used_at, now)
    # 关键词权重更高，保证「提到团子」能压过无关的高重要度记忆
    return 0.3 * imp + 0.55 * kw + 0.15 * rec


def select_core_memories(memories: list[Memory], *, char_limit: int = CORE_CHAR_LIMIT) -> list[Memory]:
    """选取 profile + relationship，按置顶/重要度排序，截断到字数上限。"""
    cores = [m for m in memories if m.category in ("profile", "relationship") and m.status == "active"]
    cores.sort(key=lambda m: (not m.pinned, -(m.importance or 0), -(m.id or 0)))
    selected: list[Memory] = []
    used = 0
    for m in cores:
        line = f"- {m.content}"
        if selected and used + len(line) + 1 > char_limit:
            # 置顶的仍尽量保留
            if m.pinned and used < char_limit:
                selected.append(m)
            continue
        selected.append(m)
        used += len(line) + 1
    return selected


def select_event_memories(
    memories: list[Memory],
    query: str,
    *,
    limit: int = EVENT_MAX,
    now: datetime | None = None,
) -> list[Memory]:
    """按相关度挑选事件记忆；置顶必选。"""
    events = [m for m in memories if m.category == "event" and m.status == "active"]
    pinned = [m for m in events if m.pinned]
    rest = [m for m in events if not m.pinned]
    scored = [(score_event(m, query, now), m) for m in rest]
    scored.sort(key=lambda x: -x[0])
    picked: list[Memory] = list(pinned)
    for sc, m in scored:
        if len(picked) >= limit:
            break
        if sc > EVENT_SCORE_THRESHOLD:
            picked.append(m)
    return picked[:limit]


def format_memory_block(
    core: list[Memory],
    events: list[Memory],
) -> str:
    """格式化为注入 system 的记忆块文本。"""
    if not core and not events:
        return ""
    lines: list[str] = []
    profile = [m for m in core if m.category == "profile"]
    relationship = [m for m in core if m.category == "relationship"]
    if profile:
        lines.append("【你记得的关于对方】")
        for m in profile:
            lines.append(f"- {m.content}")
    if relationship:
        lines.append("【你们之间】")
        for m in relationship:
            lines.append(f"- {m.content}")
    if events:
        lines.append("【可能相关的往事】")
        for m in events:
            prefix = ""
            if m.occurred_at:
                prefix = f"{m.occurred_at.isoformat()} "
            lines.append(f"- {prefix}{m.content}")
    lines.append("（自然地用上这些记忆，不要逐条复述，不要说「根据记忆」）")
    return "\n".join(lines)


def assemble_memory_block(
    memories: list[Memory],
    recent_user_texts: list[str],
) -> tuple[str, list[Memory]]:
    """
    组装记忆块；返回 (文本, 被选中的记忆列表)。
    recent_user_texts：最近若干条用户消息，用于事件检索。
    """
    query = " ".join(t for t in recent_user_texts if t)[-500:]
    core = select_core_memories(memories)
    events = select_event_memories(memories, query)
    used = core + events
    return format_memory_block(core, events), used
