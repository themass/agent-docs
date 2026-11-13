"""账号注销：跨存储删除（chat-agent-ops-design.md §3）。

入口 ``request``（API 进程，``DELETE /api/agent/v1/me``）：立刻关闭该用户的全部会话（新消息被拒，
进行中的回合写不进回复），再入队 ``account.purge``，返回 202。
任务 ``run``（worker 进程）按顺序删除，每一步都可重复执行；任一步失败，任务整体重试：

1. 关系库：再关一次会话（请求与任务之间可能新建了会话）
2. 控制面：取消进行中的回合，删锁、回合状态、事件流
3. 对话线程：删除每个会话的 checkpoint
4. 记忆：每个聊过的角色的记忆空间，以及用户级空间
5. 时间线
6. 对象存储：上传的文件
7. 关系库：物理删除全部行，包括还没执行的、带该用户数据的后台任务
8. 记一笔完成，只存用户 id 的哈希

关系库最后删：前面几步要靠它查出会话、角色与文件。
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from companion.memory.subject import role_subject
from companion.account.port import AccountDataStore, SessionEventsEraser, ThreadEraser

log = logging.getLogger("companion.account")

PURGE_JOB = "account.purge"


def user_hash(owner_id: int) -> str:
    return hashlib.sha256(f"companion-user:{owner_id}".encode()).hexdigest()


def _naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


@dataclass(frozen=True)
class PurgeReport:
    sessions: int
    roles: int
    memories: int
    events: int
    objects: int
    rows: int


class AccountPurgeService:
    def __init__(self, *, store: AccountDataStore, jobs: Any, control: SessionEventsEraser | None,
                 threads: ThreadEraser | None, memory: Any, timeline: Any = None, objects: Any = None,
                 system_roles: Callable[[], Iterable[str]] = tuple,
                 clock: Callable[[], datetime] = _naive_utc) -> None:
        """``system_roles``：系统角色 id（目录角色、陪伴角色卡）。记忆接口可以按任意角色写入，
        注销时除了聊过的角色，也把这些角色的记忆空间一起清掉，不靠「聊过」来推断。"""
        self._store = store
        self._jobs = jobs
        self._control = control
        self._threads = threads
        self._memory = memory
        self._timeline = timeline
        self._objects = objects
        self._clock = clock
        self._system_roles = system_roles

    async def request(self, *, owner_id: int) -> None:
        """同步部分只做关闭会话与入队；重复请求只入队一次。"""
        await self._store.close_sessions(owner_id=owner_id)
        now = self._clock()
        await self._jobs.enqueue(kind=PURGE_JOB, payload={"owner_id": owner_id, "requested_at": now.isoformat()},
                                 run_after=now, dedupe_key=f"{PURGE_JOB}:{user_hash(owner_id)[:32]}",
                                 max_attempts=20)

    async def run(self, *, owner_id: int, requested_at: datetime | None = None) -> PurgeReport:
        await self._store.close_sessions(owner_id=owner_id)
        footprint = await self._store.footprint(owner_id=owner_id)

        if self._control is not None:
            for sid in footprint.session_ids:
                await self._control.purge_session(session_id=sid)
        if self._threads is not None and footprint.session_ids:
            await self._threads.delete_threads(session_ids=footprint.session_ids)

        memories = 0
        roles = sorted(set(footprint.role_ids) | set(self._system_roles()))
        for subject in [role_subject(owner_id, r) for r in roles] + [str(owner_id)]:
            memories += await self._memory.delete_user(subject)

        events = await self._timeline.delete_user(owner_id=str(owner_id)) if self._timeline is not None else 0

        objects = 0
        if self._objects is not None:
            for key in footprint.object_keys:
                await self._objects.delete(key=key)
                objects += 1

        rows = await self._store.purge(owner_id=owner_id)
        await self._store.log_purge(user_hash=user_hash(owner_id), requested_at=requested_at or self._clock(),
                                    finished_at=self._clock())
        report = PurgeReport(sessions=len(footprint.session_ids), roles=len(roles),
                             memories=memories, events=events, objects=objects, rows=rows)
        # 日志不带原 id（O §4.1）
        log.info("account purged", extra={"user_hash": user_hash(owner_id)[:16], **report.__dict__})
        return report
