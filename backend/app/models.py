"""ORM 模型：联系人、聊天消息、回复任务与记忆。"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProfile(Base):
    """【聊天】当前登录用户（单机版唯一一行，id 固定为 1）。"""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    nickname: Mapped[str] = mapped_column(String(64), default="我", comment="我的昵称")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="我的头像")


class Contact(Base):
    """【聊天】联系人（每个联系人对应一个 AI 会话角色）。"""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示名称")
    persona: Mapped[str] = mapped_column(Text, default="", comment="角色设定/系统提示")
    api_key: Mapped[str] = mapped_column(String(256), nullable=False, comment="DeepSeek API Key")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="头像路径")
    chat_background_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="电脑端聊天背景图路径"
    )
    chat_background_mobile_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="手机端聊天背景图路径"
    )
    auto_message_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", comment="是否定时主动发消息"
    )
    auto_message_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", comment="主动发消息间隔分钟"
    )
    auto_message_last_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="上次主动发消息时间"
    )
    model_profile: Mapped[str] = mapped_column(
        String(16), default="flash", server_default="flash", comment="模型档位 flash/chat"
    )
    auto_message_next_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="下次自动发消息时间"
    )
    auto_message_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="用户未回复期间连续自动发送条数"
    )
    memory_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", comment="是否启用记忆"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    """【聊天】单条消息记录。"""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_contact_id_id", "contact_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user / assistant / system")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="附件 URL")
    attachment_name: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="附件原名")
    attachment_kind: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="image / file"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contact: Mapped["Contact"] = relationship(back_populates="messages")


class ReplyJob(Base):
    """【聊天】回复任务表：用户发消息或自动调度时创建，后台 Worker 领取执行。"""

    __tablename__ = "reply_jobs"
    __table_args__ = (
        Index("ix_reply_jobs_status_run_after", "status", "run_after"),
        Index("ix_reply_jobs_contact_status", "contact_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    trigger: Mapped[str] = mapped_column(
        String(16), default="user", server_default="user", comment="user / auto"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/running/done/failed"
    )
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bubbles_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析后的气泡 JSON")
    emitted_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Memory(Base):
    """【记忆】记忆条目表。"""

    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_contact_status", "contact_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="profile / relationship / event"
    )
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", comment="active / retired"
    )
    source: Mapped[str] = mapped_column(
        String(16), default="ai", server_default="ai", comment="ai / user"
    )
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    superseded_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )
    from_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    seen: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MemoryState(Base):
    """【记忆】联系人记忆状态表：整理游标与总结缓存。"""

    __tablename__ = "memory_states"

    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
    )
    last_extracted_message_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_added: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_retired: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_dropped: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    runs_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    runs_today: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    digest_stale: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
