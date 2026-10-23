"""SQLite 轻量迁移：为已有库补字段与索引。"""
from sqlalchemy import text
from sqlalchemy.engine import Connection


def _existing_columns(sync_conn: Connection, table: str) -> set[str]:
    rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _add_columns(sync_conn: Connection, table: str, alters: list[tuple[str, str]]) -> None:
    existing = _existing_columns(sync_conn, table)
    for col, col_type in alters:
        if col not in existing:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))


def ensure_message_attachment_columns(sync_conn: Connection) -> None:
    """messages 表增加附件字段（已有则跳过）。"""
    _add_columns(
        sync_conn,
        "messages",
        [
            ("attachment_url", "VARCHAR(512)"),
            ("attachment_name", "VARCHAR(256)"),
            ("attachment_kind", "VARCHAR(16)"),
        ],
    )


def ensure_contact_mobile_background_column(sync_conn: Connection) -> None:
    """contacts 表增加手机端聊天背景字段。"""
    _add_columns(sync_conn, "contacts", [("chat_background_mobile_url", "VARCHAR(512)")])


def ensure_contact_auto_message_columns(sync_conn: Connection) -> None:
    """contacts 表增加自动发消息相关字段。"""
    _add_columns(
        sync_conn,
        "contacts",
        [
            ("auto_message_enabled", "INTEGER DEFAULT 0"),
            ("auto_message_interval_minutes", "INTEGER DEFAULT 30"),
            ("auto_message_last_at", "DATETIME"),
        ],
    )


def ensure_v2_contact_columns(sync_conn: Connection) -> None:
    """contacts 表增加模型档位、自动调度与记忆开关。"""
    _add_columns(
        sync_conn,
        "contacts",
        [
            ("model_profile", "VARCHAR(16) DEFAULT 'flash'"),
            ("auto_message_next_at", "DATETIME"),
            ("auto_message_streak", "INTEGER DEFAULT 0"),
            ("memory_enabled", "INTEGER DEFAULT 1"),
        ],
    )


def ensure_message_contact_id_index(sync_conn: Connection) -> None:
    """messages 表按会话分页索引。"""
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_messages_contact_id_id ON messages (contact_id, id)"
        )
    )


def ensure_v3_auth_columns(sync_conn: Connection) -> None:
    """V3：contacts / user_profile 增加 user_id。"""
    _add_columns(sync_conn, "contacts", [("user_id", "INTEGER")])
    _add_columns(sync_conn, "user_profile", [("user_id", "INTEGER")])
    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts (user_id)"))


def ensure_v4_moment_columns(sync_conn: Connection) -> None:
    """V4：联系人朋友圈调度字段。"""
    _add_columns(sync_conn, "contacts", [("moment_next_at", "DATETIME")])


def ensure_v2_all(sync_conn: Connection) -> None:
    """执行全部 V2/V3/V4 轻量迁移（表由 metadata.create_all 创建）。"""
    ensure_message_attachment_columns(sync_conn)
    ensure_contact_mobile_background_column(sync_conn)
    ensure_contact_auto_message_columns(sync_conn)
    ensure_v2_contact_columns(sync_conn)
    ensure_message_contact_id_index(sync_conn)
    ensure_v3_auth_columns(sync_conn)
    ensure_v4_moment_columns(sync_conn)
