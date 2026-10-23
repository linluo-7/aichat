"""生成一次性邀请码。用法：python -m app.scripts.create_invite [--count N]"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models import InviteCode, User
from app.services.auth import generate_invite_code
from app.services.migrate import ensure_v2_all
from app.services.ownership import assign_orphan_data_to_admin


async def _run(count: int) -> list[str]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_v2_all)

    async with AsyncSessionLocal() as db:
        await assign_orphan_data_to_admin(db)
        result = await db.execute(select(User).where(User.is_admin.is_(True)).limit(1))
        admin = result.scalar_one_or_none()
        if not admin:
            result = await db.execute(select(User).order_by(User.id.asc()).limit(1))
            admin = result.scalar_one_or_none()
        if not admin:
            print("错误：库中尚无用户，请先启动一次后端以 bootstrap 管理员。", file=sys.stderr)
            sys.exit(1)

        codes: list[str] = []
        for _ in range(max(1, count)):
            code = generate_invite_code()
            # 极低概率碰撞时重试
            for _retry in range(5):
                exists = await db.execute(select(InviteCode).where(InviteCode.code == code))
                if exists.scalar_one_or_none() is None:
                    break
                code = generate_invite_code()
            db.add(
                InviteCode(
                    code=code,
                    created_by_user_id=admin.id,
                )
            )
            codes.append(code)
        await db.commit()
        return codes


def main() -> None:
    """入口：打印生成的邀请码。"""
    parser = argparse.ArgumentParser(description="生成一次性邀请码")
    parser.add_argument("--count", type=int, default=1, help="生成数量，默认 1")
    args = parser.parse_args()
    codes = asyncio.run(_run(args.count))
    print("邀请码（各仅可用一次）：")
    for c in codes:
        print(c)


if __name__ == "__main__":
    main()
