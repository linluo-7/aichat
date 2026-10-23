"""多气泡解析行为测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.bubbles import split_bubbles


def test_json_messages():
    raw = '{"messages":["你好呀","晚上有空吗"]}'
    assert split_bubbles(raw) == ["你好呀", "晚上有空吗"]


def test_json_fence():
    raw = '```json\n{"messages":["a","b","c"]}\n```'
    assert split_bubbles(raw) == ["a", "b", "c"]


def test_section_marker():
    raw = "第一条\n§\n第二条"
    assert split_bubbles(raw) == ["第一条", "第二条"]


def test_blank_lines():
    raw = "一段\n\n二段"
    assert split_bubbles(raw) == ["一段", "二段"]


def test_plain_single():
    assert split_bubbles("就一句") == ["就一句"]


def test_empty_fails():
    assert split_bubbles("") == []
    assert split_bubbles("   ") == []


def test_merge_over_four():
    raw = '{"messages":["1","2","3","4","5","6"]}'
    out = split_bubbles(raw)
    assert len(out) == 4
    assert out[3] == "4\n5\n6"
