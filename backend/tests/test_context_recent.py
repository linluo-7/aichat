"""上下文取最近消息的逻辑验证（纯函数侧）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.context_builder import message_to_llm_text
from types import SimpleNamespace


def test_error_prefix_filtered():
    msg = SimpleNamespace(
        role="assistant",
        content="[错误] DeepSeek HTTP 401",
        attachment_kind=None,
        attachment_name=None,
    )
    assert message_to_llm_text(msg) is None


def test_image_placeholder():
    msg = SimpleNamespace(
        role="user",
        content="",
        attachment_kind="image",
        attachment_name=None,
    )
    assert message_to_llm_text(msg) == "[用户发送了一张图片]"
