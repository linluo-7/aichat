"""回复任务：创建、推迟、领取、完成、失败。"""
import json
from datetime import timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ReplyJob
from app.utils.datetime_util import utc_now


async def enqueue_user_reply(db: AsyncSession, contact_id: int) -> ReplyJob:
    """
    用户发消息后创建或推迟 pending 任务（合并连发）。
    若已有 pending 且未到执行时间，则推迟 run_after。
    """
    now = utc_now()
    run_after = now + timedelta(seconds=settings.reply_merge_seconds)

    result = await db.execute(
        select(ReplyJob)
        .where(
            ReplyJob.contact_id == contact_id,
            ReplyJob.status == "pending",
            ReplyJob.trigger == "user",
        )
        .order_by(ReplyJob.id.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.run_after = run_after
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return existing

    job = ReplyJob(
        contact_id=contact_id,
        trigger="user",
        status="pending",
        run_after=run_after,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def enqueue_auto_reply(db: AsyncSession, contact_id: int) -> ReplyJob | None:
    """创建自动发消息任务；若已有 pending/running 则跳过。"""
    now = utc_now()
    result = await db.execute(
        select(ReplyJob)
        .where(
            ReplyJob.contact_id == contact_id,
            ReplyJob.status.in_(["pending", "running"]),
        )
        .limit(1)
    )
    if result.scalar_one_or_none():
        return None

    job = ReplyJob(
        contact_id=contact_id,
        trigger="auto",
        status="pending",
        run_after=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next_job(db: AsyncSession) -> ReplyJob | None:
    """原子领取一条到期任务，同联系人同时最多一个 running。"""
    now = utc_now()
    # 先选出候选 id，再条件更新，避免并发双领
    pick = await db.execute(
        text(
            """
            SELECT j.id FROM reply_jobs j
            WHERE j.status = 'pending'
              AND j.run_after <= :now
              AND NOT EXISTS (
                SELECT 1 FROM reply_jobs r
                WHERE r.contact_id = j.contact_id AND r.status = 'running'
              )
            ORDER BY j.run_after, j.id
            LIMIT 1
            """
        ),
        {"now": now},
    )
    row = pick.first()
    if not row:
        return None
    job_id = int(row[0])
    result = await db.execute(
        text(
            """
            UPDATE reply_jobs
            SET status = 'running',
                attempts = attempts + 1,
                updated_at = :now
            WHERE id = :id AND status = 'pending'
            """
        ),
        {"now": now, "id": job_id},
    )
    await db.commit()
    if result.rowcount == 0:
        return None
    return await db.get(ReplyJob, job_id)


async def save_bubbles(db: AsyncSession, job: ReplyJob, bubbles: list[str]) -> None:
    """保存解析后的气泡数组。"""
    job.bubbles_json = json.dumps(bubbles, ensure_ascii=False)
    job.updated_at = utc_now()
    await db.commit()
    await db.refresh(job)


def load_bubbles(job: ReplyJob) -> list[str]:
    """读取任务上的气泡列表。"""
    if not job.bubbles_json:
        return []
    try:
        data = json.loads(job.bubbles_json)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        return []
    return []


async def mark_emitted(db: AsyncSession, job: ReplyJob, count: int) -> None:
    """更新已发出气泡数。"""
    job.emitted_count = count
    job.updated_at = utc_now()
    await db.commit()
    await db.refresh(job)


async def mark_done(db: AsyncSession, job: ReplyJob) -> None:
    """标记任务完成。"""
    job.status = "done"
    job.error = None
    job.updated_at = utc_now()
    await db.commit()


async def mark_failed(db: AsyncSession, job: ReplyJob, error: str) -> None:
    """标记任务失败。"""
    job.status = "failed"
    job.error = (error or "未知错误")[:512]
    job.updated_at = utc_now()
    await db.commit()


async def requeue_retry(db: AsyncSession, job: ReplyJob, *, delay_seconds: int) -> None:
    """失败可重试时退回 pending。"""
    job.status = "pending"
    job.run_after = utc_now() + timedelta(seconds=delay_seconds)
    job.updated_at = utc_now()
    await db.commit()


async def recover_running_jobs(db: AsyncSession) -> int:
    """启动时将 running 任务改回 pending，便于断点续发。"""
    result = await db.execute(
        update(ReplyJob)
        .where(ReplyJob.status == "running")
        .values(status="pending", updated_at=utc_now())
    )
    await db.commit()
    return result.rowcount or 0


async def retry_failed_job(db: AsyncSession, job_id: int) -> ReplyJob:
    """将失败任务重新排队。"""
    job = await db.get(ReplyJob, job_id)
    if not job:
        raise ValueError("任务不存在")
    if job.status != "failed":
        raise ValueError("仅失败任务可重试")
    job.status = "pending"
    job.run_after = utc_now()
    job.error = None
    job.bubbles_json = None
    job.emitted_count = 0
    job.attempts = 0
    job.updated_at = utc_now()
    await db.commit()
    await db.refresh(job)
    return job


async def list_busy_contact_ids(db: AsyncSession) -> list[int]:
    """有待回复任务（pending/running）的联系人：用于前端保持快速轮询。"""
    result = await db.execute(
        select(ReplyJob.contact_id)
        .where(ReplyJob.status.in_(["pending", "running"]))
        .distinct()
    )
    return [row[0] for row in result.all()]


async def list_typing_contact_ids(db: AsyncSession) -> list[int]:
    """
    正在输入：任意 pending/running 任务。
    无流式时生成窗口短，合并等待期也显示，避免提示几乎看不见。
    """
    return await list_busy_contact_ids(db)


async def list_recent_failed_jobs(db: AsyncSession, *, hours: int = 24) -> list[ReplyJob]:
    """最近失败任务。"""
    since = utc_now() - timedelta(hours=hours)
    result = await db.execute(
        select(ReplyJob)
        .where(ReplyJob.status == "failed", ReplyJob.updated_at >= since)
        .order_by(ReplyJob.updated_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())
