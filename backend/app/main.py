"""FastAPI 应用入口：路由注册、静态文件、数据库初始化、后台 Worker。"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.routers import auth, contacts, memories, messages, moments, profile, sync
from app.services.migrate import ensure_v2_all
from app.services.ownership import assign_orphan_data_to_admin
from app.services.reply_worker import start_worker, stop_worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时创建数据目录、迁移表结构、bootstrap 管理员并启动回复 Worker。"""
    Path("./data").mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_v2_all)
    async with AsyncSessionLocal() as session:
        await assign_orphan_data_to_admin(session)
    await start_worker()
    yield
    await stop_worker()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(contacts.router)
app.include_router(messages.router)
app.include_router(sync.router)
app.include_router(memories.router)
app.include_router(moments.router)

app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")


@app.get("/api/health")
async def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}
