"""DeepSeek Chat Completions 调用（OpenAI 兼容接口，含联网工具循环）。"""
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

WEB_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "搜索互联网获取最新信息。天气、新闻、时事、比分、价格、政策等"
                "需要实时或你不确定的事实时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，简短明确",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "抓取指定网页正文。用户发了链接或需要某页详细内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "http(s) 完整链接",
                    }
                },
                "required": ["url"],
            },
        },
    },
]


class DeepSeekError(Exception):
    """DeepSeek API 调用失败。"""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _classify_http_error(status_code: int, body: str) -> DeepSeekError:
    """将 HTTP 错误分为可重试 / 不可重试。"""
    snippet = body[:500]
    msg = f"DeepSeek HTTP {status_code}: {snippet}"
    if status_code in (429, 500, 502, 503, 504):
        return DeepSeekError(msg, status_code=status_code, retryable=True)
    return DeepSeekError(msg, status_code=status_code, retryable=False)


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _post_chat(
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    """发起一次 chat/completions，返回完整 JSON。"""
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=_headers(api_key))
            body_text = response.text
            if response.status_code >= 400:
                raise _classify_http_error(response.status_code, body_text)
            return response.json()
    except httpx.TimeoutException as exc:
        raise DeepSeekError(f"DeepSeek 超时: {exc}", retryable=True) from exc
    except httpx.TransportError as exc:
        raise DeepSeekError(f"DeepSeek 网络错误: {exc}", retryable=True) from exc


def _message_content(msg: dict[str, Any]) -> str:
    """从 assistant message 取出文本 content。"""
    content = msg.get("content")
    if content is None:
        return ""
    return str(content)


async def _run_tool(api_key: str, name: str, arguments: str, *, ori_question: str | None) -> str:
    """执行 web_search / web_fetch，返回给模型的 JSON 字符串。"""
    from app.services.deepseek_web import web_fetch, web_search

    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}

    try:
        if name == "web_search":
            query = str(args.get("query") or "").strip()
            results = await web_search(
                api_key, query, count=5, ori_question=ori_question
            )
            return json.dumps({"results": results}, ensure_ascii=False)
        if name == "web_fetch":
            page = await web_fetch(api_key, str(args.get("url") or ""))
            return json.dumps(page, ensure_ascii=False)
        return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
    except DeepSeekError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


async def chat_completion(
    api_key: str,
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
    response_format: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> str:
    """
    非流式对话，返回完整 assistant content 文本。
    extra 可传入 thinking 等扩展字段。
    """
    payload: dict[str, Any] = {
        "model": model or settings.deepseek_model,
        "messages": messages,
        "stream": False,
    }
    if response_format:
        payload["response_format"] = response_format
    if extra:
        payload.update(extra)

    data = await _post_chat(api_key, payload, timeout=timeout)
    choices = data.get("choices") or []
    if not choices:
        raise DeepSeekError("DeepSeek 返回空 choices", retryable=True)
    return _message_content(choices[0].get("message") or {})


async def chat_completion_with_web(
    api_key: str,
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
    ori_question: str | None = None,
    max_tool_rounds: int = 3,
    timeout: float = 180.0,
) -> str:
    """
    带网页搜索/抓取的对话：模型可按需调用工具，最终返回助手文本。
    flash 不支持内置 web_search，故用 Search/Fetch API + function calling。
    """
    working: list[dict[str, Any]] = [dict(m) for m in messages]
    model_name = model or settings.deepseek_model
    base_extra = dict(extra or {})

    for _ in range(max_tool_rounds):
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": working,
            "stream": False,
            "tools": WEB_TOOLS,
            "tool_choice": "auto",
        }
        payload.update(base_extra)
        data = await _post_chat(api_key, payload, timeout=timeout)
        choices = data.get("choices") or []
        if not choices:
            raise DeepSeekError("DeepSeek 返回空 choices", retryable=True)

        msg = choices[0].get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = _message_content(msg)
            if content.strip():
                return content
            break

        # 把带 tool_calls 的 assistant 消息原样追加
        working.append(msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            arguments = str(fn.get("arguments") or "{}")
            call_id = str(call.get("id") or "")
            result = await _run_tool(api_key, name, arguments, ori_question=ori_question)
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )

    # 收尾：强制 JSON 多气泡，不再给工具
    final = await chat_completion(
        api_key,
        working
        + [
            {
                "role": "user",
                "content": (
                    "请根据上文直接用微信口语回复用户。"
                    '只输出 JSON：{"messages":["…"]}，不要提搜索、链接或来源。'
                ),
            }
        ],
        model=model_name,
        extra=base_extra,
        response_format={"type": "json_object"},
        timeout=timeout,
    )
    return final


async def stream_chat_completion(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
) -> AsyncIterator[str]:
    """向 DeepSeek 发起流式对话，逐块 yield 文本 delta（兼容旧接口，新流水线不用）。"""
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model or settings.deepseek_model,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise _classify_http_error(
                    response.status_code, body.decode(errors="replace")
                )
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    import json

                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        yield text
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
