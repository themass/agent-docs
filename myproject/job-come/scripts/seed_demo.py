#!/usr/bin/env python3
"""Seed demo user + sample profile for local QA."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentkit.common.crypto import hash_password
from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jobcome.config import settings
from jobcome.models.enums import OwnerKind, ProfileStatus, UserStatus
from jobcome.models.profile import Profile
from jobcome.models.user import User, UserMeta

DEMO_EMAIL = os.environ.get("JOB_COME_DEMO_EMAIL", "demo@jobcome.local")
DEMO_PASSWORD = os.environ.get("JOB_COME_DEMO_PASSWORD", "Demo1234!")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        from sqlalchemy import select

        existing = (
            await db.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if existing:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            return

        user = User(
            id=new_id("usr"),
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            status=UserStatus.ACTIVE,
        )
        profile = Profile(
            id=new_id("prof"),
            user_id=user.id,
            guest_session_id=None,
            owner_kind=OwnerKind.USER,
            status=ProfileStatus.DRAFT,
            version=1,
            locale="zh-CN",
            contact_name="演示候选人",
            summary_text="5 年后端开发经验，熟悉 Go / Java / 云原生。",
            payload={
                "contact": {"name": "演示候选人", "email": "demo@jobcome.local"},
                "summary": "5 年后端开发经验，熟悉 Go / Java / 云原生。",
                "experiences": [
                    {
                        "id": "exp_demo_1",
                        "company": "示例科技",
                        "title": "高级后端工程师",
                        "start_date": "2020-01",
                        "end_date": None,
                        "highlights": ["负责核心订单服务", "参与性能优化"],
                    }
                ],
                "education": [],
                "skills": [{"name": "Golang"}, {"name": "Java"}],
                "meta": {"ingest_mode": "demo_seed"},
            },
        )
        user.meta = UserMeta(
            user_id=user.id,
            display_name="演示用户",
            active_profile_id=profile.id,
        )
        db.add(user)
        db.add(profile)
        await db.commit()
        print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"Active profile: {profile.id}")


if __name__ == "__main__":
    asyncio.run(main())
