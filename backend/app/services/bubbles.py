"""多气泡解析：主用 JSON，§ / 空行 / 整段兜底。"""
import json
import re
from typing import Any

MAX_BUBBLES = 4
BUBBLE_SPLIT_MARKER = "\n§\n"


def im_system_prompt(persona: str, memory_block: str = "") -> str:
    """微信式多气泡聊天的 system 提示（含可选记忆块）。"""
    lines = [
        "你正在微信式即时聊天中，要像真人一样自然。",
        "重要：每次回复拆成 1～4 条独立短消息，必须用 JSON 输出。",
        '输出格式（仅输出 JSON，不要其它文字）：{"messages":["第一条","第二条"]}',
        "规则：",
        "- 每条消息简短、口语化，适合单独发送；避免 Markdown、编号列表和长篇大段。",
        "- 若只需一句，messages 里只放一条。",
        "- 不要提及系统、规则或「根据记忆」等字样。",
        "- 需要天气、新闻、时事、实时数据或不确定的事实时，可调用 web_search；用户发了链接需要看内容时用 web_fetch。",
        "- 用搜到的信息自然回答即可，不要特意说来源、网站名、链接，也不要说「我搜了一下」。",
        "- 闲聊、情绪、回忆类话题不必搜索。",
    ]
    if persona.strip():
        lines.append(f"角色设定：{persona.strip()}")
    if memory_block.strip():
        lines.append(memory_block.strip())
    return "\n".join(lines)


def proactive_user_trigger() -> str:
    """主动消息触发语（不落库）。"""
    return (
        "（你已经有一段时间没发消息了，请像微信聊天一样自然主动说点什么。"
        "可结合上文跟进或开新话题，不要提及系统、规则或「主动消息」字样。）"
    )


def _strip_code_fence(text: str) -> str:
    """去掉 ```json ... ``` 代码围栏。"""
    stripped = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return stripped


def _normalize_bubbles(parts: list[str]) -> list[str]:
    """去空白、去空条；超过 4 条时把第 4 条及之后合并。"""
    cleaned = [p.strip() for p in parts if p and p.strip()]
    if not cleaned:
        return []
    if len(cleaned) <= MAX_BUBBLES:
        return cleaned
    head = cleaned[: MAX_BUBBLES - 1]
    tail = "\n".join(cleaned[MAX_BUBBLES - 1 :])
    return head + [tail]


def _try_parse_json_messages(text: str) -> list[str] | None:
    """尝试解析 JSON {"messages": [...]}。"""
    candidate = _strip_code_fence(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # 尝试截取第一个 { ... }
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    msgs = data.get("messages")
    if not isinstance(msgs, list):
        return None
    parts = [str(m) for m in msgs if m is not None and str(m).strip()]
    return _normalize_bubbles(parts) or None


def split_bubbles(text: str) -> list[str]:
    """
    气泡解析兜底链：JSON → § → 空行 → 整段。
    全空则返回 []。
    """
    if not text or not text.strip():
        return []

    parsed = _try_parse_json_messages(text)
    if parsed is not None:
        return parsed

    # 单独一行的 §
    if "\n§\n" in text or text.strip().count("\n§\n") >= 0:
        parts = [p.strip() for p in text.split(BUBBLE_SPLIT_MARKER) if p.strip()]
        # 也处理「单独一行只有 §」的变体
        if len(parts) <= 1 and "\n§" in text:
            parts = [p.strip() for p in re.split(r"\n\s*§\s*\n", text) if p.strip()]
        if len(parts) > 1:
            return _normalize_bubbles(parts)

    # 空行分段
    blank_parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(blank_parts) > 1:
        return _normalize_bubbles(blank_parts)

    return _normalize_bubbles([text.strip()])


def typing_delay_ms(content: str) -> int:
    """模拟打字停顿：clamp(400 + 字数×60, 800, 4000)。"""
    n = len(content or "")
    return max(800, min(4000, 400 + n * 60))


def parse_extract_result(raw: str) -> dict[str, Any] | None:
    """解析记忆整理 JSON（供 memory_extract 复用围栏剥离）。"""
    candidate = _strip_code_fence(raw)
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(candidate[start : end + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                return None
    return None
