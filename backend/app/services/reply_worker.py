"""后台 Worker：领取回复任务、自动发消息调度、记忆整理。"""
import asyncio
import logging
from datetime import timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Contact, Message, ReplyJob
from app.services import reply_jobs as jobs_svc
from app.services.bubbles import split_bubbles, typing_delay_ms
from app.services.context_builder import build_llm_messages
from app.services.deepseek import DeepSeekError, chat_completion, chat_completion_with_web
from app.services.llm_profiles import resolve_model_params
from app.services.memory_extract import run_extract_for_contact, should_extract
from app.services.memory_recall import assemble_memory_block
from app.services.memory_store import list_active_memories, touch_used
from app.utils.datetime_util import utc_now

logger = logging.getLogger("reply_worker")

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_semaphore: asyncio.Semaphore | None = None
_auto_tick = 0
_memory_tick = 0


async def _execute_job(job_id: int) -> None:
    """执行已领取（status=running）的回复任务。"""
    assert _semaphore is not None
    async with _semaphore:
        async with AsyncSessionLocal() as db:
            job = await db.get(ReplyJob, job_id)
            if not job or job.status != "running":
                return
            contact = await db.get(Contact, job.contact_id)
            if not contact:
                await jobs_svc.mark_failed(db, job, "联系人不存在")
                return

            try:
                bubbles = jobs_svc.load_bubbles(job)
                if not bubbles:
                    # 领取后先停顿，让「正在输入」至少被前端轮询看到一轮
                    if settings.reply_typing_enabled:
                        await asyncio.sleep(1.2)
                    memory_block = ""
                    used_memories: list = []
                    if contact.memory_enabled:
                        memories = await list_active_memories(db, contact.id)
                        recent_users = await db.execute(
                            select(Message)
                            .where(Message.contact_id == contact.id, Message.role == "user")
                            .order_by(Message.id.desc())
                            .limit(3)
                        )
                        texts = [
                            m.content or ""
                            for m in reversed(list(recent_users.scalars().all()))
                        ]
                        memory_block, used_memories = assemble_memory_block(memories, texts)

                    llm_messages = await build_llm_messages(
                        db,
                        contact,
                        proactive=(job.trigger == "auto"),
                        memory_block=memory_block,
                    )
                    params = resolve_model_params(contact.model_profile)
                    # 取最近一条用户话，作为搜索的 ori_question
                    ori_q = None
                    for m in reversed(llm_messages):
                        if m.get("role") == "user" and (m.get("content") or "").strip():
                            ori_q = str(m["content"]).strip()[:128]
                            break

                    if settings.web_tools_enabled:
                        raw = await chat_completion_with_web(
                            contact.api_key,
                            llm_messages,
                            model=params["model"],
                            extra=params.get("extra") or {},
                            ori_question=ori_q,
                        )
                    else:
                        raw = await chat_completion(
                            contact.api_key,
                            llm_messages,
                            model=params["model"],
                            extra=params.get("extra") or {},
                            response_format={"type": "json_object"},
                        )
                    bubbles = split_bubbles(raw)
                    if not bubbles:
                        raw2 = await chat_completion(
                            contact.api_key,
                            llm_messages,
                            model=params["model"],
                            extra=params.get("extra") or {},
                            response_format={"type": "json_object"},
                        )
                        bubbles = split_bubbles(raw2)
                    if not bubbles:
                        await jobs_svc.mark_failed(db, job, "模型返回空回复")
                        return
                    await jobs_svc.save_bubbles(db, job, bubbles)
                    if used_memories:
                        await touch_used(db, used_memories)

                bubbles = jobs_svc.load_bubbles(job)
                emitted = job.emitted_count or 0
                base_ts = utc_now()
                while emitted < len(bubbles):
                    content = bubbles[emitted]
                    if settings.reply_typing_enabled:
                        # 第一条也要有最短停顿，避免模型返回后瞬间出泡、提示一闪而过
                        delay = typing_delay_ms(content) / 1000.0
                        if emitted == 0:
                            delay = max(delay, 1.0)
                        await asyncio.sleep(delay)
                    await db.refresh(job)
                    if job.status != "running":
                        return
                    row = Message(
                        contact_id=contact.id,
                        role="assistant",
                        content=content,
                        created_at=base_ts + timedelta(milliseconds=emitted),
                    )
                    db.add(row)
                    await db.commit()
                    emitted += 1
                    await jobs_svc.mark_emitted(db, job, emitted)

                await jobs_svc.mark_done(db, job)

                now = utc_now()
                contact.auto_message_last_at = now
                interval = max(1, contact.auto_message_interval_minutes or 30)
                contact.auto_message_next_at = now + timedelta(minutes=interval)
                if job.trigger == "auto":
                    contact.auto_message_streak = (contact.auto_message_streak or 0) + 1
                await db.commit()

            except DeepSeekError as exc:
                job = await db.get(ReplyJob, job_id)
                if not job:
                    return
                if exc.retryable and (job.attempts or 0) < 2:
                    await jobs_svc.requeue_retry(
                        db, job, delay_seconds=5 * max(1, job.attempts or 1)
                    )
                else:
                    await jobs_svc.mark_failed(db, job, str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception("执行任务 %s 失败", job_id)
                job = await db.get(ReplyJob, job_id)
                if job:
                    await jobs_svc.mark_failed(db, job, str(exc)[:512])


async def _process_one_claimed() -> bool:
    """领取并执行一条任务；有任务返回 True。"""
    async with AsyncSessionLocal() as db:
        job = await jobs_svc.claim_next_job(db)
        if not job:
            return False
        job_id = job.id
    await _execute_job(job_id)
    return True


async def _schedule_auto_messages() -> None:
    """扫描到期的自动发消息联系人并入队。"""
    async with AsyncSessionLocal() as db:
        now = utc_now()
        result = await db.execute(
            select(Contact).where(Contact.auto_message_enabled.is_(True))
        )
        contacts = list(result.scalars().all())
        for contact in contacts:
            next_at = contact.auto_message_next_at
            interval = max(1, contact.auto_message_interval_minutes or 30)
            if next_at is None:
                contact.auto_message_next_at = now + timedelta(minutes=interval)
                await db.commit()
                continue
            if next_at.tzinfo is None:
                next_at = next_at.replace(tzinfo=timezone.utc)
            if next_at > now:
                continue
            if (contact.auto_message_streak or 0) >= settings.auto_message_streak_max:
                contact.auto_message_next_at = now + timedelta(minutes=interval)
                await db.commit()
                continue
            job = await jobs_svc.enqueue_auto_reply(db, contact.id)
            contact.auto_message_next_at = now + timedelta(minutes=interval)
            await db.commit()
            if job:
                logger.info("自动消息入队 contact=%s job=%s", contact.id, job.id)


async def _run_memory_pass() -> None:
    """扫描需要整理记忆的联系人。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Contact).where(Contact.memory_enabled.is_(True)))
        contact_ids = [c.id for c in result.scalars().all()]
    for cid in contact_ids:
        try:
            async with AsyncSessionLocal() as db:
                c = await db.get(Contact, cid)
                if not c or not await should_extract(db, c):
                    continue
                await run_extract_for_contact(db, c)
                logger.info("记忆整理完成 contact=%s", c.id)
        except DeepSeekError as exc:
            logger.warning("记忆整理失败 contact=%s: %s", cid, exc)
        except Exception:  # noqa: BLE001
            logger.exception("记忆整理异常 contact=%s", cid)


async def _worker_loop() -> None:
    """主循环：每秒领取任务；每 30 秒自动消息；每 60 秒记忆整理。"""
    global _auto_tick, _memory_tick
    assert _stop_event is not None
    logger.info("reply_worker 已启动")
    while not _stop_event.is_set():
        try:
            worked = await _process_one_claimed()
            _auto_tick += 1
            _memory_tick += 1
            if _auto_tick >= 30:
                _auto_tick = 0
                await _schedule_auto_messages()
            if _memory_tick >= 60:
                _memory_tick = 0
                await _run_memory_pass()
            if not worked:
                try:
                    await asyncio.wait_for(_stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        except Exception:  # noqa: BLE001
            logger.exception("worker 循环异常")
            await asyncio.sleep(2)
    logger.info("reply_worker 已停止")


async def start_worker() -> None:
    """应用启动时调用：恢复 running 任务并启动循环。"""
    global _worker_task, _stop_event, _semaphore, _auto_tick, _memory_tick
    _auto_tick = 0
    _memory_tick = 0
    async with AsyncSessionLocal() as db:
        n = await jobs_svc.recover_running_jobs(db)
        if n:
            logger.info("恢复 running 任务 %s 条", n)
    _stop_event = asyncio.Event()
    _semaphore = asyncio.Semaphore(2)
    _worker_task = asyncio.create_task(_worker_loop(), name="reply_worker")


async def stop_worker() -> None:
    """应用关闭时停止 Worker。"""
    global _worker_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _worker_task.cancel()
        _worker_task = None
