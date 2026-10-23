"""一次性：为指定用户的每个联系人各发一条朋友圈。

用法（容器内）：
  python -m app.scripts.seed_user_moments lxy
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Contact, MomentPost, User
from app.services import moment_ai
from app.services.deepseek import DeepSeekError
from app.utils.datetime_util import utc_now


async def seed(username: str) -> None:
    """为 username 下每个联系人创建一条 author_type=contact 的动态。"""
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if not user:
            print(f"用户不存在: {username}")
            sys.exit(1)

        contacts = list(
            (
                await db.execute(select(Contact).where(Contact.user_id == user.id))
            ).scalars().all()
        )
        if not contacts:
            print(f"{username} 没有联系人")
            return

        now = utc_now()
        ok = 0
        fail = 0
        for c in contacts:
            try:
                if (c.api_key or "").strip():
                    content = await moment_ai.generate_contact_post(db, c)
                else:
                    content = f"今天心情不错，随便记一笔。— {c.name}"
            except DeepSeekError as exc:
                print(f"  跳过 {c.name} (id={c.id}): {exc}")
                fail += 1
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"  跳过 {c.name} (id={c.id}): {exc}")
                fail += 1
                continue

            db.add(
                MomentPost(
                    user_id=user.id,
                    author_type="contact",
                    contact_id=c.id,
                    content=(content or "").strip()[:500] or "今天天气不错。",
                    created_at=now,
                )
            )
            # 避免调度器马上再发一条
            from datetime import timedelta
            import random

            c.moment_next_at = now + timedelta(seconds=random.randint(6 * 3600, 24 * 3600))
            ok += 1
            print(f"  已发: {c.name}")

        await db.commit()
        print(f"完成：成功 {ok}，失败 {fail}，共 {len(contacts)} 个联系人")


def main() -> None:
    username = (sys.argv[1] if len(sys.argv) > 1 else "lxy").strip() or "lxy"
    asyncio.run(seed(username))


if __name__ == "__main__":
    main()
