"""记忆 CRUD、总结与立即整理。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Contact
from app.schemas import (
    MemoriesPageOut,
    MemoryCreate,
    MemoryOut,
    MemoryStateOut,
    MemoryUpdate,
)
from app.services.memory_digest import generate_digest
from app.services.memory_extract import run_extract_for_contact, should_extract
from app.services.memory_store import (
    add_memory,
    clear_memories,
    delete_memory,
    get_or_create_state,
    list_active_memories,
    list_retired_memories,
    mark_all_seen,
    update_memory,
)

router = APIRouter(prefix="/api", tags=["memories"])


@router.get("/contacts/{contact_id}/memories", response_model=MemoriesPageOut)
async def get_memories(contact_id: int, db: AsyncSession = Depends(get_db)) -> MemoriesPageOut:
    """获取「Ta 记得的事」：总结 + 分组列表；标记已读。"""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")

    state = await get_or_create_state(db, contact_id)
    digest = state.digest
    # 过期时先返回旧总结，后台可再请求 digest；此处同步刷新一次（用户打开页面）
    if state.digest_stale:
        try:
            digest = await generate_digest(db, contact, force=True)
            await db.refresh(state)
        except Exception:  # noqa: BLE001
            digest = state.digest

    actives = await list_active_memories(db, contact_id)
    retired = await list_retired_memories(db, contact_id)
    await mark_all_seen(db, contact_id)

    return MemoriesPageOut(
        digest=digest,
        digest_at=state.digest_at,
        digest_stale=state.digest_stale,
        profile=[m for m in actives if m.category == "profile"],
        relationship=[m for m in actives if m.category == "relationship"],
        event=[m for m in actives if m.category == "event"],
        retired=retired,
        state=MemoryStateOut(
            last_run_at=state.last_run_at,
            last_error=state.last_error,
            last_added=state.last_added or 0,
            last_retired=state.last_retired or 0,
            last_dropped=state.last_dropped or 0,
        ),
    )


@router.post("/contacts/{contact_id}/memories", response_model=MemoryOut, status_code=201)
async def create_memory(
    contact_id: int, body: MemoryCreate, db: AsyncSession = Depends(get_db)
) -> MemoryOut:
    """手动添加记忆。"""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    mem = await add_memory(
        db,
        contact_id,
        category=body.category,
        content=body.content,
        importance=body.importance,
        source="user",
        pinned=body.pinned,
        occurred_at=body.occurred_at,
    )
    if mem is None:
        raise HTTPException(status_code=400, detail="记忆无效或与已有记忆重复")
    return mem


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
async def patch_memory(
    memory_id: int, body: MemoryUpdate, db: AsyncSession = Depends(get_db)
) -> MemoryOut:
    """编辑内容或置顶。"""
    try:
        return await update_memory(
            db, memory_id, content=body.content, pinned=body.pinned
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/memories/{memory_id}")
async def remove_memory(memory_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """删除一条记忆。"""
    try:
        await delete_memory(db, memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.delete("/contacts/{contact_id}/memories")
async def clear_contact_memories(
    contact_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    """清空该联系人全部记忆。"""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    n = await clear_memories(db, contact_id)
    return {"status": "ok", "deleted": n}


@router.post("/contacts/{contact_id}/memories/digest")
async def refresh_digest(contact_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """重新生成「Ta 眼中的你」。"""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    text = await generate_digest(db, contact, force=True)
    return {"digest": text}


@router.post("/contacts/{contact_id}/memories/consolidate")
async def consolidate_now(contact_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """立即整理记忆（仍受每日上限约束）。"""
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    if not contact.memory_enabled:
        raise HTTPException(status_code=400, detail="记忆已关闭")
    # 强制：临时绕过消息条数门槛，但仍检查每日上限与失败次数
    ok = await should_extract(db, contact)
    if not ok:
        # 仍允许用户强制：直接尝试，若每日上限则报错
        state = await get_or_create_state(db, contact_id)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if state.runs_day == today and (state.runs_today or 0) >= 24:
            raise HTTPException(status_code=429, detail="今日整理次数已达上限")
        if (state.fail_count or 0) >= 3 and state.runs_day == today:
            raise HTTPException(status_code=429, detail="连续失败过多，请明日再试")

    try:
        stats = await run_extract_for_contact(db, contact)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:300]) from exc
    return {"status": "ok", **stats}
