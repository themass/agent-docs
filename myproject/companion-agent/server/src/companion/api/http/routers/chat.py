"""会话接口（D §7.1）。前缀 /v1。

本模块只做 HTTP ↔ 应用服务的转换；判定、落库、排队、重跑都在 app/chat。
不用 ``from __future__ import annotations``：FastAPI 需要运行时注解（见 turns.py）。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from companion.service.chat.lifecycle import DrainState
from companion.api.sse.stream import event_stream
from companion.service.chat.drain import DrainService
from companion.service.chat.history import HistoryBusy, HistoryService, NotEditable, NotLatest, find_reply
from companion.service.chat.submit import SubmitService
from companion.service.turn.queue import DRAIN_MAX_ATTEMPTS
from companion.db.port import MessageStore, QueueStore, SessionStore
from companion.service.turn.control import TurnControlPort

log = logging.getLogger("companion.chat_api")

PREFIX = "/v1"
REGENERATE_NOTE = "请基于上面的对话重新回答最后一条消息。"
CONTINUE_NOTE = "请接着上一条被中断的回答继续写完。"


@dataclass
class ChatApi:
    sessions: SessionStore
    messages: MessageStore
    queue: QueueStore
    control: TurnControlPort
    submit: SubmitService
    drain: DrainState
    drainer: DrainService | None = None
    # 编辑、删除、重新生成时同步改大脑的对话线程；没有时只改消息表（无状态大脑）。
    history: HistoryService | None = None
    # 直传（ADR-011）：发送带直传 upload_id 的附件时先绑定校验。没有直传配置时为 None，
    # 所有 upload_id 一律按「不是签发给你的」拒绝不了中转通道——见 send_message 的注释。
    direct: Any = None
    # 建会话时的角色存在性校验（异步，role_id/owner_id 两个 kwarg，返回 bool）。
    # 判据与回合里的 RoleProfileResolver.exists 同源：未知角色在 POST /sessions 就 400，
    # 不存进库——否则每条消息的回合都会 RoleNotFound（线上 __default__ 占位符事故）。
    # 没有装配校验器（离线/测试装配）时跳过：宁缺勿错杀。
    role_check: Any = None


def _owner_id(user_id: str) -> int:
    """数据库 owner_id 是 BIGINT；Java 的 UserPo.id 是 long，登录态验证器已保证它是正整数。"""
    from fastapi import HTTPException

    if not user_id.isdigit():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return int(user_id)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _session_json(s) -> dict[str, Any]:
    return {"id": s.id, "role_id": s.role_id, "name": s.name, "locale": s.locale,
            "updated_at": _iso(s.updated_at)}


def _message_json(m, alt_ids: list[int] | None = None) -> dict[str, Any]:
    """``alt_ids``：这条消息所在候选组的全部候选 id（升序）。多于一条才带 alt_* 字段，客户端据此显示滑动切换。
    ``alt_index`` 是这条消息在组里的位置（从 0 起）。"""
    out = {"id": m.id, "role": m.role, "kind": m.kind, "content": m.content, "turn_id": m.turn_id,
           "interrupted": m.interrupted, "created_at": _iso(m.created_at)}
    # 客户端发起时带的本地 id：客户端缓存里的富内容行（图片/语音）就用它对上这条服务端行，
    # 刷新历史时把富内容合并过来而不是当陌生消息。只对消息主人可见，不泄露跨账号信息。
    if m.client_message_id:
        out["client_message_id"] = m.client_message_id
    # 附件挂在消息的 meta 上：刷新历史后要能重新渲染图片/文件卡片
    attachments = (m.meta or {}).get("attachments")
    if attachments:
        out["attachments"] = attachments
    # 位置消息同理：kind=location 的行把结构化坐标原样带回，端上渲染坐标气泡
    location = (m.meta or {}).get("location")
    if location:
        out["location"] = location
    if alt_ids and len(alt_ids) > 1 and m.id in alt_ids:
        out.update({"alt_group": m.alt_group, "alt_index": alt_ids.index(m.id), "alt_count": len(alt_ids),
                    "alt_ids": alt_ids})
    return out


def build_router(api: ChatApi, current_user):
    from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    class Attachment(BaseModel):
        """一个已上传的文件。``upload_id`` 来自 POST /uploads，内容已经落在对象存储，
        这里只带引用，不重复传正文。"""

        upload_id: str = Field(min_length=1, max_length=64)
        kind: str = Field(default="image", max_length=16)
        name: str = Field(default="", max_length=255)

    class Location(BaseModel):
        """位置消息的坐标（P2-13）。客户端只发经纬度 + 可选精度，地名由客户端自己解决
        （MVP 不引反地理编码：服务不存第三方 key，也不替端上背 geocoding 配额）。"""

        lat: float = Field(ge=-90, le=90)
        lng: float = Field(ge=-180, le=180)
        accuracy_m: int | None = Field(default=None, ge=0, le=100_000)

    class SendBody(BaseModel):
        # 允许只发附件不带文字（发一张图不说话）：text、attachments、location 至少要有一个
        text: str = Field(default="", max_length=4000)
        client_message_id: str | None = Field(default=None, max_length=64)
        steerable: bool = True
        attachments: list[Attachment] = Field(default_factory=list)
        location: Location | None = None

    class CreateSession(BaseModel):
        role_id: str = Field(min_length=1, max_length=128)
        name: str = Field(default="新会话", max_length=64)
        locale: str = Field(default="zh-CN", max_length=16)

    class RenameSession(BaseModel):
        name: str = Field(min_length=1, max_length=64)

    class EditMessage(BaseModel):
        content: str = Field(min_length=1, max_length=4000)

    router = APIRouter(prefix=PREFIX, tags=["chat"])

    async def owned_session(user_id: str, session_id: int):
        owner = _owner_id(user_id)
        record = await api.sessions.get(owner_id=owner, session_id=session_id)
        if record is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return owner, record

    def ensure_open(draining: bool) -> None:
        if draining:
            raise HTTPException(status_code=503, detail={"code": "draining"}, headers={"Retry-After": "1"})

    # ---- 会话 ----

    @router.get("/sessions")
    async def list_sessions(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0, le=1000),
                            user_id: str = Depends(current_user)) -> dict[str, Any]:
        rows = await api.sessions.list_for_owner(owner_id=_owner_id(user_id), limit=limit, offset=offset)
        return {"items": [_session_json(s) for s in rows], "limit": limit, "offset": offset}

    @router.post("/sessions", status_code=201)
    async def create_session(body: CreateSession, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner = _owner_id(user_id)
        # 角色不存在就当场拒绝：会话一旦建了，每条消息的回合都会失败（见 ChatApi.role_check）
        if api.role_check is not None and not await api.role_check(role_id=body.role_id, owner_id=owner):
            raise HTTPException(status_code=400, detail={"code": "unknown_role", "role_id": body.role_id})
        record = await api.sessions.create(owner_id=owner, role_id=body.role_id,
                                           name=body.name, locale=body.locale)
        return _session_json(record)

    @router.patch("/sessions/{session_id}")
    async def rename_session(session_id: int, body: RenameSession, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, record = await owned_session(user_id, session_id)
        await api.sessions.rename(owner_id=owner, session_id=session_id, name=body.name)
        return _session_json(record)

    @router.delete("/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: int, user_id: str = Depends(current_user)) -> Response:
        owner, _ = await owned_session(user_id, session_id)
        await api.sessions.soft_delete(owner_id=owner, session_id=session_id)
        return Response(status_code=204)

    # ---- 发送与事件 ----

    @router.post("/sessions/{session_id}/messages", status_code=202)
    async def send_message(session_id: int, body: SendBody, user_id: str = Depends(current_user)) -> dict[str, Any]:
        # 分两段计时：HTTP 层（认证已完成、这里是会话读取）与 submit 内部。
        # 线上「发消息 → turn.started」有一段几秒的空白，不分开量就分不清是库慢、
        # 是 Redis 慢，还是事件循环被谁卡住了。
        import time as _time

        from companion.api.http.routers import chat as _chat_mod

        t0 = _time.perf_counter()
        ensure_open(api.drain.draining)
        # 三样全空（只有 client_message_id / steerable 这类控制字段）不是消息：
        # 落到 submit 会建出一条空 content、模型看不见的用户消息，还会占一个回合。
        if not (body.text.strip() or body.attachments or body.location):
            raise HTTPException(status_code=422, detail={"code": "empty_message"})
        owner, record = await owned_session(user_id, session_id)
        t_read = _time.perf_counter()
        # 直传通道（ADR-011 §6-C）：带 upload_id 的附件在落库前先绑定——归属、有效期、
        # HEAD 存在、实际大小，任一不过都在此刻答 4xx JSON，而不是等模型读图时才炸。
        # 没配直传（direct=None）时跳过：行为与纯中转通道完全一致。
        if api.direct is not None:
            from companion.service.uploads.direct import DirectRejected

            for attachment in body.attachments:
                try:
                    await api.direct.bind(owner_id=owner, upload_id=attachment.upload_id)
                except DirectRejected as exc:
                    status = {"KEY_NOT_FOUND": 404, "KEY_ALREADY_BOUND": 409, "KEY_EXPIRED": 410,
                              "KEY_NOT_PUT": 412, "SIZE_NOT_ALLOWED": 413}.get(exc.code, 400)
                    raise HTTPException(status_code=status, detail={"code": exc.code}) from exc
        # 位置消息的模型可见形态在这里定：content 自动生成一行文本（模型零改动就读得到），
        # 结构化坐标进 meta.location（客户端历史回读渲染坐标气泡）。kind=location 让
        # 端上、审核、以后可能的「附近」功能都能按类型分流，String(16) 放得下，无需迁移。
        kind = "location" if body.location is not None else "chat"
        content = body.text
        if body.location is not None and not content.strip():
            loc = body.location
            acc = f" (±{loc.accuracy_m}m)" if loc.accuracy_m is not None else ""
            content = f"[位置] {loc.lat},{loc.lng}{acc}"
        result = await api.submit.submit(
            owner_id=owner, session_id=session_id, character_id=record.role_id, text=content,
            client_message_id=body.client_message_id, steerable=body.steerable,
            attachments=[a.model_dump() for a in body.attachments],
            kind=kind,
            location=body.location.model_dump(exclude_none=True) if body.location else None)
        _chat_mod.log.info(
            "send_message timing session=%s read_session_ms=%d submit_ms=%d disposition=%s",
            session_id, int((t_read - t0) * 1000), int((_time.perf_counter() - t_read) * 1000),
            result.disposition.value if result.disposition else None)
        if result.status == "denied":
            raise HTTPException(status_code=422, detail={"code": "content_policy", "reason": result.reason})
        return {"status": result.status, "message_id": result.message_id, "turn_id": result.turn_id,
                "disposition": result.disposition.value if result.disposition else None}

    @router.get("/sessions/{session_id}/events")
    async def events(
        session_id: int,
        user_id: str = Depends(current_user),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        await owned_session(user_id, session_id)
        stream = event_stream(control=api.control, session_id=session_id, last_event_id=last_event_id,
                              draining=lambda: api.drain.draining)
        return StreamingResponse(stream, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.post("/sessions/{session_id}/cancel", status_code=202)
    async def cancel(session_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        await owned_session(user_id, session_id)
        turn = await api.control.active_turn(session_id=session_id)
        if turn is None:
            return {"status": "idle"}
        await api.control.send_cancel(turn_id=turn["turn_id"])
        return {"status": "cancelling", "turn_id": turn["turn_id"]}

    @router.get("/sessions/{session_id}/messages")
    async def history(session_id: int, before: int | None = None,
                      limit: int = Query(default=30, ge=1, le=100),
                      user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, _ = await owned_session(user_id, session_id)
        rows = await api.messages.list_before(owner_id=owner, session_id=session_id, before_id=before, limit=limit)
        groups = sorted({m.alt_group for m in rows if m.alt_group is not None})
        alts = await api.messages.alt_ids_for(owner_id=owner, session_id=session_id, groups=groups)
        return {"items": [_message_json(m, alts.get(m.alt_group)) for m in rows]}

    def _busy() -> HTTPException:
        return HTTPException(status_code=409, detail={"code": "conflict", "reason": "busy"})

    @router.patch("/messages/{message_id}")
    async def edit_message(message_id: int, body: EditMessage, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner = _owner_id(user_id)
        if api.history is not None:
            try:
                message = await api.history.edit(owner_id=owner, message_id=message_id, content=body.content)
            except NotEditable:
                # 语音转写不开放编辑：它是识别结果，改了就与实际进了记忆和线程的内容不一致。
                raise HTTPException(status_code=409, detail={"code": "not_editable", "reason": "voice"})
            except HistoryBusy:
                raise _busy()
            if message is None:
                raise HTTPException(status_code=404, detail={"code": "not_found"})
            return _message_json(message)
        if not await api.messages.edit(owner_id=owner, message_id=message_id, content=body.content):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        message = await api.messages.get(owner_id=owner, message_id=message_id)
        return _message_json(message)

    @router.post("/messages/{message_id}/select")
    async def select_alternative(message_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        """切换到这条候选回复（左右滑动）。只能在最新一轮切换；回合进行中 409。"""
        owner = _owner_id(user_id)
        try:
            if api.history is not None:
                message = await api.history.select_alternative(owner_id=owner, message_id=message_id)
            else:
                message = await api.messages.get(owner_id=owner, message_id=message_id)
                if message is not None and message.role == "assistant" and message.alt_group is not None:
                    await api.messages.select_alternative(owner_id=owner, session_id=message.session_id,
                                                          alt_group=message.alt_group, message_id=message_id)
                    message = await api.messages.get(owner_id=owner, message_id=message_id)
                else:
                    message = None
        except HistoryBusy:
            raise _busy()
        except NotLatest:
            raise HTTPException(status_code=409, detail={"code": "conflict", "reason": "not_latest"})
        if message is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        alts = await api.messages.alt_ids_for(owner_id=owner, session_id=message.session_id,
                                              groups=[message.alt_group] if message.alt_group is not None else [])
        return _message_json(message, alts.get(message.alt_group))

    @router.delete("/messages/{message_id}", status_code=204)
    async def delete_message(message_id: int, user_id: str = Depends(current_user)) -> Response:
        owner = _owner_id(user_id)
        try:
            deleted = (await api.history.delete(owner_id=owner, message_id=message_id) if api.history is not None
                       else await api.messages.soft_delete(owner_id=owner, message_id=message_id))
        except HistoryBusy:
            raise _busy()
        if not deleted:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    # ---- 队列 ----

    @router.get("/sessions/{session_id}/queue")
    async def list_queue(session_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, _ = await owned_session(user_id, session_id)
        items = await api.queue.list_queued(owner_id=owner, session_id=session_id)
        return {"items": [{"message_id": i.message_id, "text": i.text, "status": i.status} for i in items]}

    @router.delete("/sessions/{session_id}/queue/{message_id}", status_code=204)
    async def withdraw(session_id: int, message_id: int, user_id: str = Depends(current_user)) -> Response:
        owner, _ = await owned_session(user_id, session_id)
        items = await api.queue.list_queued(owner_id=owner, session_id=session_id)
        match = next((i for i in items if i.message_id == message_id), None)
        # 已被排空、合并或撤回：是状态冲突，不是找不到资源（D §7.1）。
        if match is None or not await api.queue.withdraw(owner_id=owner, item_id=match.id):
            raise HTTPException(status_code=409, detail={"code": "conflict"})
        await api.messages.soft_delete(owner_id=owner, message_id=message_id)  # D §7.1：对应用户消息一并软删
        return Response(status_code=204)

    @router.delete("/sessions/{session_id}/messages", status_code=204)
    async def clear_history(session_id: int, user_id: str = Depends(current_user)) -> Response:
        """清空这个会话的历史。只影响这一个会话；别的会话、记忆、画像都不动。

        记忆/画像是跨会话沉淀下来的「她记得的事」，不属于某一段对话，所以这里不清。
        要遗忘某条记忆走 /memory 的删除接口。
        """
        owner, _ = await owned_session(user_id, session_id)
        if api.history is not None:
            await api.history.clear(owner_id=owner, session_id=session_id)
        else:
            # 没有大脑线程时只清消息表（无状态部署）
            await api.messages.clear(owner_id=owner, session_id=session_id)
        return Response(status_code=204)

    @router.post("/sessions/{session_id}/queue/clear", status_code=202)
    async def clear_queue(session_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, _ = await owned_session(user_id, session_id)
        cleared = 0
        for item in await api.queue.list_queued(owner_id=owner, session_id=session_id):
            if await api.queue.withdraw(owner_id=owner, item_id=item.id):
                await api.messages.soft_delete(owner_id=owner, message_id=item.message_id)
                cleared += 1
        return {"cleared": cleared}

    @router.post("/sessions/{session_id}/queue/retry", status_code=202)
    async def retry_queue(session_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, _ = await owned_session(user_id, session_id)
        failed = await api.queue.list_status(owner_id=owner, session_id=session_id, status="failed")
        restored = 0
        for item in failed:
            # 人工重试重置计数：failed→queued 不计数，下次认领从 0 开始（D §6.5）。
            if await api.queue.transition(item_id=item.id, from_status="failed", to_status="queued"):
                restored += 1
        return {"restored": restored, "max_attempts": DRAIN_MAX_ATTEMPTS}

    # ---- 重跑：重新生成 / 继续 / 重试（D §6.6、§6.7）----

    async def _rerun(owner: int, session, text: str, message_ids: list[int]) -> dict[str, Any]:
        ensure_open(api.drain.draining)
        # 重新生成：新回复作为当前回复的另一个候选保存（左右滑动切换）。要在移除旧回复之前找到它。
        alt_of = (await find_reply(api.messages, owner_id=owner, session_id=session.id,
                                   user_message_id=min(message_ids)) if message_ids else None)
        if api.history is not None and message_ids:
            # 先把旧回复从对话线程里移除，模型不会看到它；消息表里的旧回复保留（可作为备选回复）。
            try:
                await api.history.forget_replies_after(owner_id=owner, session_id=session.id,
                                                       user_message_id=min(message_ids))
            except HistoryBusy:
                raise _busy()
        turn_id = await api.submit.rerun(owner_id=owner, session_id=session.id, character_id=session.role_id,
                                         text=text, message_ids=message_ids, alt_of=alt_of)
        if turn_id is None:
            raise HTTPException(status_code=409, detail={"code": "conflict", "reason": "busy"})
        return {"status": "accepted", "turn_id": turn_id}

    @router.post("/sessions/{session_id}/messages/{message_id}/regenerate", status_code=202)
    async def regenerate(session_id: int, message_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, session = await owned_session(user_id, session_id)
        message = await api.messages.get(owner_id=owner, message_id=message_id)
        if message is None or message.role != "user":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return await _rerun(owner, session, message.content, [message.id])

    @router.post("/sessions/{session_id}/messages/{message_id}/continue", status_code=202)
    async def continue_reply(session_id: int, message_id: int, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, session = await owned_session(user_id, session_id)
        message = await api.messages.get(owner_id=owner, message_id=message_id)
        if message is None or message.role != "assistant" or not message.interrupted:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return await _rerun(owner, session, CONTINUE_NOTE, [])

    @router.post("/sessions/{session_id}/turns/{turn_id}/retry", status_code=202)
    async def retry_turn(session_id: int, turn_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner, session = await owned_session(user_id, session_id)
        inputs = [m for m in await api.messages.list_by_turn(owner_id=owner, session_id=session_id, turn_id=turn_id)
                  if m.role == "user"]
        if not inputs:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return await _rerun(owner, session, "\n\n".join(m.content for m in inputs), [m.id for m in inputs])

    return router


def build_health_router(drain: DrainState):
    """探针（P §3.6）。不带前缀，不需要登录。readyz 在停机时返回 503，让负载均衡先切走流量（P §3.5）。

    ``/metrics`` 也在这里：同样是"不带前缀、不验登录态"的机器接口。**必须在 nginx 上限制来源**，
    否则任何人拿走 token 用量和各会话的调用量。
    """
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import Response

    from companion import metrics

    router = APIRouter(tags=["health"])

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz() -> dict[str, str]:
        if drain.draining:
            raise HTTPException(status_code=503, detail={"status": "draining"})
        return {"status": "ready"}

    @router.get("/metrics")
    async def prometheus() -> Response:
        # 用 bytes 而不是 str：generate_latest 返回 UTF-8 字节，按 str 传会被再编码一次。
        return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)

    @router.get("/metrics/snapshot")
    async def metrics_snapshot() -> dict[str, Any]:
        """同一份指标的 JSON 形态，给监控面板用。

        与 /metrics 读的是同一个注册表、同样的小数点——只是编码不同。所以面板上的数字
        不可能和 Prometheus 抓到的漂移。字段名沿用 agentkit 的约定，job-come 的面板
        不用改就能读。
        """
        from agentkit.observability import sharing_across_processes

        payload = metrics.snapshot()
        payload["sharing_across_processes"] = sharing_across_processes()
        return payload

    return router
