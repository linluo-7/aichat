"""朋友圈：发帖、列表、评论回复。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Contact,
    MomentComment,
    MomentImage,
    MomentLike,
    MomentPost,
    MomentUserLike,
    User,
    UserProfile,
)
from app.services.files import save_upload
from app.services.moment_jobs import enqueue_reactions_for_user_post, enqueue_reply_to_user
from app.utils.datetime_util import to_utc_iso, utc_now

router = APIRouter(prefix="/api/moments", tags=["moments"])


class MomentImageOut(BaseModel):
    id: int
    url: str
    sort_order: int


class MomentLikeOut(BaseModel):
    liker_type: str = "contact"  # user | contact
    contact_id: int | None = None
    contact_name: str
    contact_avatar: str | None = None


class MomentCommentOut(BaseModel):
    id: int
    author_type: str
    contact_id: int | None = None
    contact_name: str | None = None
    contact_avatar: str | None = None
    author_name: str | None = None
    parent_id: int | None = None
    content: str
    created_at: str


class MomentPostOut(BaseModel):
    id: int
    author_type: str
    contact_id: int | None = None
    author_name: str
    author_avatar: str | None = None
    content: str
    images: list[MomentImageOut]
    likes: list[MomentLikeOut]
    liked_by_me: bool = False
    comments: list[MomentCommentOut]
    created_at: str


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_id: int | None = None


async def _profile_name(db: AsyncSession, user_id: int) -> tuple[str, str | None]:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    p = result.scalar_one_or_none()
    if not p:
        return "我", None
    return p.nickname or "我", p.avatar_url


async def _serialize_post(db: AsyncSession, post: MomentPost, user: User) -> MomentPostOut:
    if post.author_type == "user":
        name, avatar = await _profile_name(db, post.user_id)
    else:
        c = await db.get(Contact, post.contact_id) if post.contact_id else None
        name = c.name if c else "联系人"
        avatar = c.avatar_url if c else None

    imgs = await db.execute(
        select(MomentImage)
        .where(MomentImage.post_id == post.id)
        .order_by(MomentImage.sort_order.asc(), MomentImage.id.asc())
    )
    images = [
        MomentImageOut(id=i.id, url=i.url, sort_order=i.sort_order) for i in imgs.scalars().all()
    ]

    me_name, _ = await _profile_name(db, user.id)
    likes: list[MomentLikeOut] = []
    liked_by_me = False
    my_like = await db.execute(
        select(MomentUserLike).where(
            MomentUserLike.post_id == post.id, MomentUserLike.user_id == user.id
        )
    )
    if my_like.scalar_one_or_none():
        liked_by_me = True
        likes.append(
            MomentLikeOut(
                liker_type="user",
                contact_id=None,
                contact_name=me_name,
                contact_avatar=None,
            )
        )

    like_rows = await db.execute(select(MomentLike).where(MomentLike.post_id == post.id))
    for lk in like_rows.scalars().all():
        c = await db.get(Contact, lk.contact_id)
        likes.append(
            MomentLikeOut(
                liker_type="contact",
                contact_id=lk.contact_id,
                contact_name=c.name if c else "?",
                contact_avatar=c.avatar_url if c else None,
            )
        )

    cm_rows = await db.execute(
        select(MomentComment)
        .where(MomentComment.post_id == post.id)
        .order_by(MomentComment.id.asc())
    )
    comments: list[MomentCommentOut] = []
    for cm in cm_rows.scalars().all():
        cname = None
        cavatar = None
        aname = me_name
        if cm.author_type == "contact" and cm.contact_id:
            c = await db.get(Contact, cm.contact_id)
            cname = c.name if c else "?"
            cavatar = c.avatar_url if c else None
            aname = cname
        comments.append(
            MomentCommentOut(
                id=cm.id,
                author_type=cm.author_type,
                contact_id=cm.contact_id,
                contact_name=cname,
                contact_avatar=cavatar,
                author_name=aname,
                parent_id=cm.parent_id,
                content=cm.content,
                created_at=to_utc_iso(cm.created_at) or "",
            )
        )

    return MomentPostOut(
        id=post.id,
        author_type=post.author_type,
        contact_id=post.contact_id,
        author_name=name,
        author_avatar=avatar,
        content=post.content or "",
        images=images,
        likes=likes,
        liked_by_me=liked_by_me,
        comments=comments,
        created_at=to_utc_iso(post.created_at) or "",
    )


@router.get("", response_model=list[MomentPostOut])
async def list_moments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MomentPostOut]:
    """朋友圈时间线（新在前）。"""
    result = await db.execute(
        select(MomentPost)
        .where(MomentPost.user_id == user.id)
        .order_by(MomentPost.id.desc())
        .limit(50)
    )
    posts = list(result.scalars().all())
    return [await _serialize_post(db, p, user) for p in posts]


@router.post("", response_model=MomentPostOut)
async def create_moment(
    content: str = Form(default=""),
    files: list[UploadFile] | None = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MomentPostOut:
    """用户发朋友圈（文字和/或图片）。"""
    text = (content or "").strip()
    upload_files = [f for f in (files or []) if f is not None and getattr(f, "filename", None)]
    if not text and not upload_files:
        raise HTTPException(status_code=400, detail="请填写文字或添加图片")
    if len(upload_files) > 9:
        raise HTTPException(status_code=400, detail="最多 9 张图")

    post = MomentPost(
        user_id=user.id,
        author_type="user",
        contact_id=None,
        content=text,
        created_at=utc_now(),
    )
    db.add(post)
    await db.flush()

    for idx, f in enumerate(upload_files):
        try:
            url = await save_upload(settings.upload_dir, f, f"u{user.id}/moments")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.add(MomentImage(post_id=post.id, url=url, sort_order=idx))

    await db.commit()
    await db.refresh(post)
    await enqueue_reactions_for_user_post(db, user_id=user.id, post_id=post.id)
    return await _serialize_post(db, post, user)


@router.post("/{post_id}/like")
async def toggle_like(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """用户点赞 / 取消点赞（自己的或联系人的动态均可）。"""
    post = await db.get(MomentPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="动态不存在")

    existing = (
        await db.execute(
            select(MomentUserLike).where(
                MomentUserLike.post_id == post.id, MomentUserLike.user_id == user.id
            )
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}

    db.add(MomentUserLike(post_id=post.id, user_id=user.id, created_at=utc_now()))
    await db.commit()
    return {"liked": True}


@router.post("/{post_id}/comments", response_model=MomentCommentOut)
async def create_comment(
    post_id: int,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MomentCommentOut:
    """用户评论动态，或回复联系人的评论。"""
    post = await db.get(MomentPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="动态不存在")

    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="评论不能为空")

    parent = None
    contact_id_for_reply = None
    if body.parent_id is not None:
        parent = await db.get(MomentComment, body.parent_id)
        if not parent or parent.post_id != post.id:
            raise HTTPException(status_code=400, detail="父评论不存在")
        if parent.author_type != "contact" or not parent.contact_id:
            raise HTTPException(status_code=400, detail="只能回复联系人的评论")
        contact_id_for_reply = parent.contact_id
    elif post.author_type == "contact" and post.contact_id:
        # 用户直接评论联系人动态 → 联系人稍后回复
        contact_id_for_reply = post.contact_id

    cm = MomentComment(
        post_id=post.id,
        author_type="user",
        contact_id=None,
        parent_id=body.parent_id,
        content=text,
        created_at=utc_now(),
    )
    db.add(cm)
    await db.commit()
    await db.refresh(cm)

    if contact_id_for_reply:
        await enqueue_reply_to_user(
            db,
            user_id=user.id,
            post_id=post.id,
            contact_id=contact_id_for_reply,
            user_comment_id=cm.id,
        )

    me_name, _ = await _profile_name(db, user.id)
    return MomentCommentOut(
        id=cm.id,
        author_type="user",
        contact_id=None,
        contact_name=None,
        contact_avatar=None,
        author_name=me_name,
        parent_id=cm.parent_id,
        content=cm.content,
        created_at=to_utc_iso(cm.created_at) or "",
    )


@router.delete("/{post_id}")
async def delete_moment(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除自己的动态（用户发的）。"""
    post = await db.get(MomentPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="动态不存在")
    if post.author_type != "user":
        raise HTTPException(status_code=400, detail="只能删除自己发的动态")
    await db.delete(post)
    await db.commit()
    return {"status": "ok"}
