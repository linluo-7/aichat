"""异步 SQLAlchemy 引擎与会话工厂。"""
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_on_connect(dbapi_conn, _connection_record) -> None:
    """SQLite 开启 WAL 与 busy_timeout，便于 Worker 与 API 并发读写。"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """为每个请求提供独立数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
