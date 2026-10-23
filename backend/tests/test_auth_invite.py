"""邀请码注册与鉴权冒烟测试。"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import InviteCode, User
from app.services.auth import generate_invite_code, hash_password
from app.services.migrate import ensure_v2_all


def test_invite_register_and_isolation(tmp_path: Path):
    """邀请码可注册一次；无 token 访问业务接口 401。"""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    invite_code_holder: dict[str, str] = {}

    async def prepare():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(ensure_v2_all)
        async with Session() as db:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                is_admin=True,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            code = generate_invite_code()
            db.add(InviteCode(code=code, created_by_user_id=admin.id))
            await db.commit()
            invite_code_holder["code"] = code

    asyncio.run(prepare())

    async def _override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    try:
        with (
            patch("app.main.start_worker", new_callable=AsyncMock),
            patch("app.main.stop_worker", new_callable=AsyncMock),
            patch("app.main.assign_orphan_data_to_admin", new_callable=AsyncMock),
            TestClient(app, raise_server_exceptions=True) as client,
        ):
            code = invite_code_holder["code"]

            assert client.get("/api/contacts").status_code == 401

            bad = client.post("/api/auth/invite/check", json={"code": "NOPE-XXXXXX"})
            assert bad.status_code == 200
            assert bad.json()["ok"] is False

            ok = client.post("/api/auth/invite/check", json={"code": code})
            assert ok.json()["ok"] is True

            reg = client.post(
                "/api/auth/register",
                json={"code": code, "username": "alice", "password": "secret12"},
            )
            assert reg.status_code == 200
            token = reg.json()["token"]

            reused = client.post(
                "/api/auth/register",
                json={"code": code, "username": "bob", "password": "secret12"},
            )
            assert reused.status_code == 400

            headers = {"Authorization": f"Bearer {token}"}
            listed = client.get("/api/contacts", headers=headers)
            assert listed.status_code == 200
            assert listed.json() == []
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
