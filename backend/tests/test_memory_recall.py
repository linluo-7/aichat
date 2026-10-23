"""记忆检索打分行为测试。"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.memory_recall import (
    assemble_memory_block,
    keyword_overlap,
    score_event,
    select_core_memories,
    select_event_memories,
)


def _mem(**kwargs):
    defaults = dict(
        id=1,
        category="event",
        content="",
        importance=3,
        status="active",
        pinned=False,
        last_used_at=None,
        occurred_at=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_keyword_overlap_tuanzi():
    assert keyword_overlap("团子今天又拆家了", "用户养了一只叫团子的猫") > 0.1


def test_event_ranking_prefers_keyword():
    a = _mem(id=1, content="用户养了一只叫团子的猫", importance=3)
    b = _mem(id=2, content="用户喜欢喝咖啡", importance=5)
    query = "团子今天又拆家了"
    assert score_event(a, query) > score_event(b, query)
    picked = select_event_memories([a, b], query)
    assert picked[0].id == 1


def test_core_truncation_keeps_pinned():
    pinned = _mem(id=1, category="profile", content="P" * 800, pinned=True, importance=1)
    low = _mem(id=2, category="profile", content="L" * 800, pinned=False, importance=5)
    selected = select_core_memories([pinned, low], char_limit=900)
    assert any(m.id == 1 for m in selected)


def test_assemble_empty():
    text, used = assemble_memory_block([], [])
    assert text == ""
    assert used == []


def test_assemble_with_profile():
    m = _mem(id=1, category="profile", content="用户叫小林")
    text, used = assemble_memory_block([m], ["你好"])
    assert "【你记得的关于对方】" in text
    assert "小林" in text
    assert used
