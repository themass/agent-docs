"""紧凑记忆索引接口（P6）。前缀挂在既有 /v1/memory 下（新文件、不动 memory_v1）。

``GET /v1/memory/index`` 只读：返回「下一回合会被注入什么」——active 角色卡的渲染行在前，
策略选过的记忆条目在后，顺序与 build_context 一致。增删改仍走 /v1/memory/facts；
「可忘」也是那个接口的 DELETE。这里不写任何东西，客户端因此能把它当预览用。
"""

from companion.agent.memory.subject import role_subject
from companion.service.card.model import render_card_lines
from companion.service.memory.policy import DEFAULT_MAX_CHARS, DEFAULT_MAX_ENTRIES, select_index

PREFIX = "/v1"

FETCH_LIMIT = 200  # 参与选取的最近条目窗口；比 list_for_user 上限大，够策略挑


def _uid(user_id: str) -> int:
    from fastapi import HTTPException

    if not user_id.isdigit():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return int(user_id)


def build_router(*, memory, cards, current_user):
    from fastapi import APIRouter, Depends, Query

    router = APIRouter(prefix=f"{PREFIX}/memory", tags=["memory"])

    @router.get("/index")
    async def memory_index(role_id: str | None = Query(default=None, min_length=1, max_length=128),
                           max_entries: int = Query(default=DEFAULT_MAX_ENTRIES, ge=1, le=50),
                           max_chars: int = Query(default=DEFAULT_MAX_CHARS, ge=100, le=4000),
                           user_id: str = Depends(current_user)) -> dict:
        eff = await cards.effective(owner_id=_uid(user_id), role_id=role_id or "")
        card_lines = render_card_lines(eff.fields) if eff else []
        used = sum(len(line) + 1 for line in card_lines)
        items = await memory.list_for_user(role_subject(user_id, role_id), limit=FETCH_LIMIT)
        chosen = select_index(items, max_entries=max_entries, max_chars=max(0, max_chars - used))
        lines = card_lines + [f"- {i.content.strip()}" for i in chosen]
        return {"lines": lines, "memory_entries": len(chosen),
                "card_version": eff.version if eff else 0}

    return router
