"""DeepSeek Search / Fetch 工具 API（与 flash 搭配使用）。"""
from typing import Any

import httpx

from app.config import settings
from app.services.deepseek import DeepSeekError, _classify_http_error


async def web_search(
    api_key: str,
    query: str,
    *,
    count: int = 5,
    ori_question: str | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """调用 /v1/tools/search，返回精简结果列表供模型阅读。"""
    q = (query or "").strip()[:128]
    if not q:
        return []
    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/tools/search"
    payload: dict[str, Any] = {
        "query": q,
        "count": max(1, min(10, count)),
        "need_content": False,
    }
    if ori_question and ori_question.strip():
        payload["ori_question"] = ori_question.strip()[:128]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise _classify_http_error(response.status_code, response.text)
            data = response.json()
    except httpx.TimeoutException as exc:
        raise DeepSeekError(f"网页搜索超时: {exc}", retryable=True) from exc
    except httpx.TransportError as exc:
        raise DeepSeekError(f"网页搜索网络错误: {exc}", retryable=True) from exc

    out: list[dict[str, Any]] = []
    for item in data.get("results") or []:
        out.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "summary": (item.get("summary") or item.get("snippet") or "")[:800],
                "date": item.get("date"),
            }
        )
    return out


async def web_fetch(api_key: str, page_url: str, *, timeout: float = 45.0) -> dict[str, str]:
    """调用 /v1/tools/fetch，返回标题与 Markdown 正文（截断）。"""
    page_url = (page_url or "").strip()[:8192]
    if not page_url.startswith(("http://", "https://")):
        return {"title": "", "content": "无效链接"}

    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/tools/fetch"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json={"url": page_url}, headers=headers)
            if response.status_code >= 400:
                raise _classify_http_error(response.status_code, response.text)
            data = response.json()
    except httpx.TimeoutException as exc:
        raise DeepSeekError(f"网页抓取超时: {exc}", retryable=True) from exc
    except httpx.TransportError as exc:
        raise DeepSeekError(f"网页抓取网络错误: {exc}", retryable=True) from exc

    content = str(data.get("content") or "")
    if len(content) > 6000:
        content = content[:6000] + "\n…(已截断)"
    return {"title": str(data.get("title") or ""), "content": content}
