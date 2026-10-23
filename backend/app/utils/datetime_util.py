"""API 时间序列化：库内 naive 时间视为 UTC，输出带 Z 的 ISO。"""
from datetime import datetime, timezone


def to_utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def utc_now() -> datetime:
    """写入消息时间戳（UTC 带时区）。"""
    return datetime.now(timezone.utc)
