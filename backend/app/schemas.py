"""Pydantic 请求/响应模型。"""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_serializer

from app.utils.datetime_util import to_utc_iso

# 角色设定允许的最大字符数
PERSONA_MAX_LENGTH = 32_000


class ProfileOut(BaseModel):
    nickname: str
    avatar_url: str | None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)


class ContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    persona: str = Field(default="", max_length=PERSONA_MAX_LENGTH)
    api_key: str = Field(..., min_length=8, max_length=256)


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    persona: str | None = Field(default=None, max_length=PERSONA_MAX_LENGTH)
    api_key: str | None = Field(default=None, min_length=8, max_length=256)
    auto_message_enabled: bool | None = None
    auto_message_interval_minutes: int | None = Field(default=None, ge=1, le=10_080)
    memory_enabled: bool | None = None


class ContactOut(BaseModel):
    id: int
    name: str
    persona: str
    avatar_url: str | None
    chat_background_url: str | None
    chat_background_mobile_url: str | None = None
    auto_message_enabled: bool = False
    auto_message_interval_minutes: int = 30
    auto_message_last_at: datetime | None = None
    memory_enabled: bool = True
    memory_unseen: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, v: datetime) -> str:
        return to_utc_iso(v) or ""

    @field_serializer("auto_message_last_at")
    def _ser_auto_last(self, v: datetime | None) -> str | None:
        return to_utc_iso(v)


class ContactListItem(ContactOut):
    """列表项：含最近一条消息摘要。"""

    last_message_preview: str | None = None
    last_message_at: datetime | None = None

    @field_serializer("last_message_at")
    def _ser_last_at(self, v: datetime | None) -> str | None:
        return to_utc_iso(v)


class MessageOut(BaseModel):
    id: int
    contact_id: int
    role: str
    content: str
    attachment_url: str | None = None
    attachment_name: str | None = None
    attachment_kind: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created(self, v: datetime) -> str:
        return to_utc_iso(v) or ""


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=32000)


class MessagesPageOut(BaseModel):
    messages: list[MessageOut]
    has_more: bool = False


class FailedJobOut(BaseModel):
    id: int
    contact_id: int
    error: str | None = None


class SyncOut(BaseModel):
    messages: list[MessageOut]
    has_more: bool = False
    typing_contact_ids: list[int] = []
    busy_contact_ids: list[int] = []
    contacts: list[ContactListItem] = []
    failed_jobs: list[FailedJobOut] = []
    server_time: str


class MemoryOut(BaseModel):
    id: int
    contact_id: int
    category: str
    content: str
    importance: int
    status: str
    source: str
    pinned: bool
    superseded_by: int | None = None
    occurred_at: date | None = None
    seen: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, v: datetime) -> str:
        return to_utc_iso(v) or ""

    @field_serializer("occurred_at")
    def _ser_date(self, v: date | None) -> str | None:
        return v.isoformat() if v else None


class MemoryCreate(BaseModel):
    category: str = Field(..., pattern="^(profile|relationship|event)$")
    content: str = Field(..., min_length=1, max_length=120)
    importance: int = Field(default=3, ge=1, le=5)
    pinned: bool = False
    occurred_at: date | None = None


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None


class MemoryStateOut(BaseModel):
    last_run_at: datetime | None = None
    last_error: str | None = None
    last_added: int = 0
    last_retired: int = 0
    last_dropped: int = 0

    @field_serializer("last_run_at")
    def _ser_run(self, v: datetime | None) -> str | None:
        return to_utc_iso(v)


class MemoriesPageOut(BaseModel):
    digest: str | None = None
    digest_at: datetime | None = None
    digest_stale: bool = True
    profile: list[MemoryOut] = []
    relationship: list[MemoryOut] = []
    event: list[MemoryOut] = []
    retired: list[MemoryOut] = []
    state: MemoryStateOut

    @field_serializer("digest_at")
    def _ser_digest_at(self, v: datetime | None) -> str | None:
        return to_utc_iso(v)
