"""朋友圈延迟任务：入队、领取、执行。"""
from __future__ import annotations

import logging
import random
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contact,
    MomentComment,
    MomentImage,
    MomentJob,
    MomentLike,
    MomentPost,
    UserProfile,
)
from app.services import moment_ai
from app.services.deepseek import DeepSeekError
from app.utils.datetime_util import utc_now

logger = logging.getLogger("moment_jobs")


def random_delay_seconds() -> int:
    """1～3 分钟随机延迟。"""
    return random.randint(60, 180)


async def enqueue_reactions_for_user_post(
    db: AsyncSession, *, user_id: int, post_id: int
) -> int:
    """用户发帖后：为每个联系人入队「必赞+首评」延迟任务。"""
    result = await db.execute(select(Contact).where(Contact.user_id == user_id))
    contacts = list(result.scalars().all())
    now = utc_now()
    n = 0
    for c in contacts:
        job = MomentJob(
            user_id=user_id,
            post_id=post_id,
            contact_id=c.id,
            job_type="like_and_root",
            status="pending",
            run_after=now + timedelta(seconds=random_delay_seconds()),
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        n += 1
    await db.commit()
    return n


async def enqueue_reply_to_user(
    db: AsyncSession,
    *,
    user_id: int,
    post_id: int,
    contact_id: int,
    user_comment_id: int,
) -> MomentJob:
    """用户回复联系人首评后：入队联系人再回。"""
    now = utc_now()
    job = MomentJob(
        user_id=user_id,
        post_id=post_id,
        contact_id=contact_id,
        job_type="reply_user",
        target_comment_id=user_comment_id,
        status="pending",
        run_after=now + timedelta(seconds=random_delay_seconds()),
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next_moment_job(db: AsyncSession) -> MomentJob | None:
    """领取一条到期朋友圈任务。"""
    now = utc_now()
    pick = await db.execute(
        text(
            """
            SELECT id FROM moment_jobs
            WHERE status = 'pending' AND run_after <= :now
            ORDER BY run_after, id
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
            UPDATE moment_jobs
            SET status = 'running', attempts = attempts + 1, updated_at = :now
            WHERE id = :id AND status = 'pending'
            """
        ),
        {"now": now, "id": job_id},
    )
    await db.commit()
    if result.rowcount == 0:
        return None
    return await db.get(MomentJob, job_id)


async def recover_running_moment_jobs(db: AsyncSession) -> int:
    """启动时将 running 改回 pending。"""
    result = await db.execute(
        text(
            "UPDATE moment_jobs SET status = 'pending', updated_at = :now WHERE status = 'running'"
        ),
        {"now": utc_now()},
    )
    await db.commit()
    return result.rowcount or 0


async def _author_display_name(db: AsyncSession, user_id: int) -> str:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    return (profile.nickname if profile else None) or "好友"


async def execute_moment_job(db: AsyncSession, job: MomentJob) -> None:
    """执行一条朋友圈任务。"""
    post = await db.get(MomentPost, job.post_id)
    contact = await db.get(Contact, job.contact_id)
    if not post or not contact or contact.user_id != job.user_id:
        job.status = "failed"
        job.error = "动态或联系人不存在"
        job.updated_at = utc_now()
        await db.commit()
        return

    try:
        if job.job_type == "like_and_root":
            # 必赞
            exists = await db.execute(
                select(MomentLike).where(
                    MomentLike.post_id == post.id, MomentLike.contact_id == contact.id
                )
            )
            if exists.scalar_one_or_none() is None:
                db.add(MomentLike(post_id=post.id, contact_id=contact.id, created_at=utc_now()))
                await db.flush()

            # 首评仅一次
            root = await db.execute(
                select(MomentComment).where(
                    MomentComment.post_id == post.id,
                    MomentComment.contact_id == contact.id,
                    MomentComment.parent_id.is_(None),
                    MomentComment.author_type == "contact",
                )
            )
            if root.scalar_one_or_none() is None:
                imgs = await db.execute(
                    select(MomentImage)
                    .where(MomentImage.post_id == post.id)
                    .order_by(MomentImage.sort_order.asc(), MomentImage.id.asc())
                )
                urls = [i.url for i in imgs.scalars().all()]
                author = await _author_display_name(db, job.user_id)
                try:
                    text = await moment_ai.generate_root_comment(
                        db, contact, post, urls, author
                    )
                except DeepSeekError as exc:
                    logger.warning("首评生成失败 contact=%s: %s", contact.id, exc)
                    text = "哈哈"
                db.add(
                    MomentComment(
                        post_id=post.id,
                        author_type="contact",
                        contact_id=contact.id,
                        parent_id=None,
                        content=text,
                        created_at=utc_now(),
                    )
                )

            job.status = "done"
            job.error = None
            job.updated_at = utc_now()
            await db.commit()
            return

        if job.job_type == "reply_user":
            user_cmt = await db.get(MomentComment, job.target_comment_id)
            if not user_cmt or user_cmt.post_id != post.id:
                job.status = "failed"
                job.error = "目标评论不存在"
                job.updated_at = utc_now()
                await db.commit()
                return
            # 找首评
            root_id = user_cmt.parent_id or user_cmt.id
            root = await db.get(MomentComment, root_id)
            if not root:
                job.status = "failed"
                job.error = "首评不存在"
                job.updated_at = utc_now()
                await db.commit()
                return
            # 该楼下联系人是否已再回过（除首评外）
            extra = await db.execute(
                select(MomentComment).where(
                    MomentComment.post_id == post.id,
                    MomentComment.contact_id == contact.id,
                    MomentComment.author_type == "contact",
                    MomentComment.parent_id.is_not(None),
                )
            )
            if list(extra.scalars().all()):
                job.status = "done"
                job.updated_at = utc_now()
                await db.commit()
                return
            try:
                text = await moment_ai.generate_reply_to_user(
                    db, contact, post, root.content, user_cmt.content
                )
            except DeepSeekError:
                text = "嗯嗯"
            db.add(
                MomentComment(
                    post_id=post.id,
                    author_type="contact",
                    contact_id=contact.id,
                    parent_id=user_cmt.id,
                    content=text,
                    created_at=utc_now(),
                )
            )
            job.status = "done"
            job.error = None
            job.updated_at = utc_now()
            await db.commit()
            return

        job.status = "failed"
        job.error = f"未知任务类型 {job.job_type}"
        job.updated_at = utc_now()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("朋友圈任务失败 job=%s", job.id)
        job.status = "failed"
        job.error = str(exc)[:512]
        job.updated_at = utc_now()
        await db.commit()


async def schedule_contact_moment_posts(db: AsyncSession) -> int:
    """扫描到期联系人，生成自发朋友圈，并设定下次时间（6～24 小时）。"""
    now = utc_now()
    result = await db.execute(select(Contact).where(Contact.user_id.is_not(None)))
    contacts = list(result.scalars().all())
    created = 0
    for c in contacts:
        next_at = c.moment_next_at
        if next_at is None:
            # 首次：1～3 小时后才开始发，避免一上来刷屏
            c.moment_next_at = now + timedelta(seconds=random.randint(3600, 10800))
            continue
        if next_at.tzinfo is None:
            from datetime import timezone

            next_at = next_at.replace(tzinfo=timezone.utc)
        if next_at > now:
            continue
        if not (c.api_key or "").strip():
            c.moment_next_at = now + timedelta(hours=12)
            continue
        try:
            content = await moment_ai.generate_contact_post(db, c)
        except DeepSeekError as exc:
            logger.warning("联系人发动态失败 contact=%s: %s", c.id, exc)
            c.moment_next_at = now + timedelta(hours=6)
            continue
        post = MomentPost(
            user_id=c.user_id,
            author_type="contact",
            contact_id=c.id,
            content=content,
            created_at=now,
        )
        db.add(post)
        await db.flush()
        # 下次 6～24 小时
        c.moment_next_at = now + timedelta(seconds=random.randint(6 * 3600, 24 * 3600))
        created += 1
    await db.commit()
    return created
