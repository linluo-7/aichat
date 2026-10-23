"""模型参数：统一使用 DeepSeek V4 Flash。"""
from typing import Any

from app.config import settings


def resolve_model_params(_model_profile: str | None = None) -> dict[str, Any]:
    """
    返回 chat/completions 请求参数。
    忽略联系人档位，固定 deepseek-flash（V4 Flash），并关闭思考模式以降低延迟。
    """
    return {
        "model": settings.deepseek_model,
        "extra": {"thinking": {"type": "disabled"}},
    }
