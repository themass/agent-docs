"""本地 Mock Poetry Domain API(仅开发/演示用,内存数据,不进镜像)。

在内存里复刻 vvv-poetry 的 agent 面:
- 既有:/api/poetry/v1/agent-orchestration/*、works/{id}/snapshot|integrity-gap-report、draft/proposals*
- 契约 §3 新增:agent-orchestration 的列表/覆盖/studio-view/sources 读路由,以及 /studio/* 三个人类写端点

令牌(与 Java 一致,互相独立):
- agent 令牌 POETRY_AGENT_INTERNAL_TOKEN:头 X-Poetry-Agent-Internal-Token。未配置/错误一律 403 + REJECTED。
- studio 令牌 POETRY_STUDIO_REVIEWER_TOKEN:头 X-Poetry-Studio-Reviewer-Token。未配置 503,错误 401。
  agent 令牌调 studio 一律 401;studio 令牌调 agent 面一律 403。

MOCK_JSON_NAMING=snake|camel(默认 snake)。真实 Java 的 agent 面现在对所有 JSON 键恒为 snake_case
(显式 @JsonProperty 固定),所以默认 snake 与真实行为一致。camel 只用于"模拟一个有问题的宿主"
(旧端点里 Java record 的键名变成 auditRefs/nextAction、workInfo 等),用来验证 BFF/worker 的兜底规范化。
camel 只影响旧端点的 record 形态(信封、snapshot、gap report);Map 形态的数据(任务、运行、事件、提案)
和新端点恒为 snake_case。请求体两种键名都接受(Java 用 @JsonAlias 接受两者)。

POST /__mock/reset 只属于 Mock,重置为种子数据。
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from mock_store import (
    Conflict,
    Ctx,
    Forbidden,
    Internal,
    Invalid,
    NotFound,
    Rejected,
    Store,
    as_int,
    blank,
    fld,
    text,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

API = "/api/poetry/v1"
ORCH = f"{API}/agent-orchestration"
STUDIO = f"{API}/studio"

H_AGENT = "x-poetry-agent-internal-token"
H_RUN = "x-poetry-agent-run-id"
H_MANDATE = "x-poetry-agent-mandate-id"
H_ROLE = "x-poetry-agent-role"
H_IDEM = "idempotency-key"
H_STUDIO = "x-poetry-studio-reviewer-token"

AGENT_ROLES = {"CONTENT_EDITOR", "HISTORICAL_REVIEWER"}

# mode: agent=既有 PoetryAgentController;orch=既有编排路由;orch_new=契约 §3.1 新读路由;studio=§3.2
LEGACY_MODES = {"agent", "orch"}


class Denied(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {_camel(k): camelize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camelize(v) for v in value]
    return value


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a.encode(), b.encode())  # type: ignore[union-attr]


class MockApp:
    def __init__(self, agent_token: str, reviewer_token: str, naming: str, v004_annotations: bool) -> None:
        self.agent_token = agent_token
        self.reviewer_token = reviewer_token
        self.naming = "camel" if naming == "camel" else "snake"
        self.store = Store(v004_annotations)
        self.app = FastAPI(title="mock-poetry-domain-api", docs_url=None, redoc_url=None, openapi_url=None)
        if agent_token and agent_token == reviewer_token:
            print("警告:agent 令牌与 studio 令牌相同,令牌隔离测试将无意义", file=sys.stderr)
        self._routes()

    # ------------------------------------------------------------------ 渲染
    def _render(self, mode: str, code: int, status: str, data: Any, refs: list[str], nxt: str,
                record: bool = False) -> JSONResponse:
        if self.naming == "camel" and mode in LEGACY_MODES:
            if record:
                data = camelize(data)
            body = {"status": status, "data": data, "auditRefs": refs, "nextAction": nxt}
        else:
            body = {"status": status, "data": data, "audit_refs": refs, "next_action": nxt}
        return JSONResponse(body, status_code=code)

    def _bad_body(self, mode: str) -> JSONResponse:
        if mode in LEGACY_MODES:
            return JSONResponse({"status": 400, "error": "Bad Request"}, status_code=400)
        return self._render(mode, 400, "REJECTED", {"reason": "request body is missing or malformed"}, [], "REPLAN")

    # ------------------------------------------------------------------ 鉴权
    def _auth(self, mode: str, request: Request) -> None:
        h = request.headers
        if mode == "studio":
            if not self.reviewer_token:
                raise Denied(503, "studio reviewer API disabled: configure poetry.studioReviewerToken")
            if not _same(h.get(H_STUDIO), self.reviewer_token):
                raise Denied(401, "invalid studio reviewer token")
            return
        if not self.agent_token:
            raise Denied(403, "agent domain API disabled: configure poetry.agentInternalToken")
        if not _same(h.get(H_AGENT), self.agent_token):
            raise Denied(403, "invalid internal Agent token")
        if mode != "agent":
            return
        key = h.get(H_IDEM)
        if blank(h.get(H_RUN)) or blank(h.get(H_MANDATE)) or blank(key):
            raise Denied(403, "run, mandate and Idempotency-Key headers are required")
        if len(key) > 128:  # type: ignore[arg-type]
            raise Denied(403, "Idempotency-Key may not exceed 128 characters")
        if h.get(H_ROLE) not in AGENT_ROLES:
            raise Denied(403, "unsupported agent audit role")

    @staticmethod
    def _ctx(request: Request) -> Ctx:
        h = request.headers
        return Ctx(h.get(H_RUN, ""), h.get(H_MANDATE, ""), h.get(H_IDEM, ""), h.get(H_ROLE, ""))

    # ------------------------------------------------------------------ 端点工厂
    def _endpoint(self, fn: Any, mode: str, body_required: bool, record: bool) -> Any:
        async def endpoint(request: Request) -> JSONResponse:
            body: Any = None
            if request.method in ("POST", "PUT"):
                raw = await request.body()
                if raw.strip():
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        return self._bad_body(mode)
                if body_required and not isinstance(body, dict):
                    return self._bad_body(mode)
            try:
                self._auth(mode, request)
                kind, data, refs = fn(request, body)
                if kind == "review":
                    return self._render(mode, 200, "REVIEW_REQUIRED", data, refs, "HUMAN_REVIEW", record)
                return self._render(mode, 200, "OK", data, refs, "NONE", record)
            except Denied as exc:
                return self._render(mode, exc.status_code, "REJECTED", {"reason": str(exc)}, [], "REPLAN")
            except Conflict as exc:
                return self._render(mode, 409, "CONFLICT", {"reason": str(exc), **exc.extra}, [], "REPLAN")
            except Forbidden as exc:
                return self._render(mode, 403, "REJECTED", {"reason": str(exc)}, [], "REPLAN")
            except NotFound as exc:
                return self._render(mode, 404, "REJECTED", {"reason": str(exc)}, [], "REPLAN")
            except Rejected as exc:
                return self._render(mode, 400, "REJECTED", {"reason": str(exc)}, [], "REPLAN")
            except Invalid as exc:  # PoetryAuthoringAdvice:{errno,data,error}
                return JSONResponse({"errno": 400, "data": None, "error": str(exc)}, status_code=400)
            except Internal:
                return JSONResponse({"status": 500, "error": "Internal Server Error"}, status_code=500)

        return endpoint

    def _add(self, methods: list[str], path: str, fn: Any, mode: str, *, body: bool = False,
             record: bool = False) -> None:
        self.app.add_route(path, self._endpoint(fn, mode, body, record), methods=methods)

    # ------------------------------------------------------------------ 路由表
    def _routes(self) -> None:
        s = self.store
        pp = lambda r, k: r.path_params[k]
        q = lambda r: dict(r.query_params)

        # ---- 既有:agent 面(PoetryAgentController)----
        self._add(["GET"], f"{API}/works/{{work_id}}/snapshot",
                  lambda r, b: ("ok", s.snapshot(pp(r, "work_id")), [f"snapshot:{pp(r, 'work_id')}"]),
                  "agent", record=True)
        self._add(["GET"], f"{API}/works/{{work_id}}/integrity-gap-report",
                  lambda r, b: ("ok", s.gaps(pp(r, "work_id")), [f"gap-report:{pp(r, 'work_id')}"]),
                  "agent", record=True)
        self._add(["POST"], f"{API}/draft/proposals",
                  lambda r, b: s.create_proposal(self._ctx(r), b), "agent", body=True)
        self._add(["POST"], f"{API}/draft/proposals/{{pid}}/reviews",
                  lambda r, b: s.review_proposal(self._ctx(r), pp(r, "pid"), b), "agent", body=True)
        self._add(["POST"], f"{API}/draft/proposals/{{pid}}/apply",
                  lambda r, b: s.apply(self._ctx(r), pp(r, "pid"), b), "agent", body=True)
        self._add(["POST"], f"{API}/works/{{work_id}}/compile-requests",
                  lambda r, b: s.request_compile(self._ctx(r), pp(r, "work_id"), b), "agent", body=True)

        # ---- 既有:编排(PoetryAgentOrchestrationController)----
        self._add(["POST"], f"{ORCH}/tasks",
                  lambda r, b: ("ok", s.create_task(b), [f"agent-task:{text(fld(b, 'task_id'))}"]),
                  "orch", body=True)
        self._add(["GET"], f"{ORCH}/tasks/{{task_id}}",
                  lambda r, b: ("ok", s.task(pp(r, "task_id")), [f"agent-task:{pp(r, 'task_id')}"]), "orch")
        self._add(["POST"], f"{ORCH}/tasks/{{task_id}}/runs",
                  lambda r, b: ("ok", s.create_run(pp(r, "task_id"), b), [f"agent-run:{text(fld(b, 'run_id'))}"]),
                  "orch", body=True)
        self._add(["GET"], f"{ORCH}/runs/{{run_id}}",
                  lambda r, b: ("ok", s.run(pp(r, "run_id")), [f"agent-run:{pp(r, 'run_id')}"]), "orch")
        self._add(["PUT"], f"{ORCH}/runs/{{run_id}}/admission",
                  lambda r, b: ("ok", s.admit_run(pp(r, "run_id"), b), [f"agent-run:{pp(r, 'run_id')}"]),
                  "orch", body=True)
        self._add(["PUT"], f"{ORCH}/runs/{{run_id}}/state",
                  lambda r, b: ("ok", s.change_run_state(pp(r, "run_id"), b), [f"agent-run:{pp(r, 'run_id')}"]),
                  "orch", body=True)
        self._add(["POST"], f"{ORCH}/runs/{{run_id}}/events", self._post_event, "orch", body=True)
        self._add(["GET"], f"{ORCH}/runs/{{run_id}}/events", self._get_events, "orch")
        self._add(["GET"], f"{ORCH}/proposals/{{pid}}",
                  lambda r, b: ("ok", s.proposal(pp(r, "pid")), [f"agent-proposal:{pp(r, 'pid')}"]), "orch")

        # ---- 契约 §3.1:新读路由(snake_case)----
        self._add(["GET"], f"{ORCH}/tasks", lambda r, b: ("ok", s.list_tasks(q(r)), []), "orch_new")
        self._add(["GET"], f"{ORCH}/tasks/{{task_id}}/runs",
                  lambda r, b: ("ok", s.list_runs(pp(r, "task_id")), []), "orch_new")
        self._add(["GET"], f"{ORCH}/proposals", lambda r, b: ("ok", s.list_proposals(q(r)), []), "orch_new")
        self._add(["GET"], f"{ORCH}/proposals/{{pid}}/items",
                  lambda r, b: ("ok", s.proposal_items(pp(r, "pid")), []), "orch_new")
        self._add(["GET"], f"{ORCH}/works", lambda r, b: ("ok", s.list_works(q(r)), []), "orch_new")
        self._add(["GET"], f"{ORCH}/works/{{work_id}}/coverage",
                  lambda r, b: ("ok", s.coverage(pp(r, "work_id")), []), "orch_new")
        self._add(["GET"], f"{ORCH}/works/{{work_id}}/studio-view",
                  lambda r, b: ("ok", s.studio_view(pp(r, "work_id")), []), "orch_new")
        self._add(["GET"], f"{ORCH}/sources", lambda r, b: ("ok", s.list_sources(q(r)), []), "orch_new")

        # ---- 契约 §3.2:studio 人类写(独立令牌)----
        self._add(["PUT"], f"{STUDIO}/citations/{{claim_id}}/{{source_id}}/locator",
                  lambda r, b: ("ok", s.set_locator(pp(r, "claim_id"), pp(r, "source_id"), b), []),
                  "studio", body=True)
        self._add(["POST"], f"{STUDIO}/sources/{{source_id}}/verification",
                  lambda r, b: ("ok", s.source_verification(pp(r, "source_id"), b), []), "studio", body=True)
        self._add(["PUT"], f"{STUDIO}/proposals/{{pid}}/items",
                  lambda r, b: ("ok", s.put_items(pp(r, "pid"), b), []), "studio", body=True)

        # ---- Mock 自有(不带令牌,仅 localhost 使用,不对应任何生产路径)----
        async def reset(request: Request) -> JSONResponse:
            s.reset()
            return JSONResponse({"status": "reset", **s.counts()})

        async def check_log(request: Request) -> JSONResponse:
            return JSONResponse({"items": s.check_log})

        async def health(request: Request) -> JSONResponse:
            return JSONResponse({
                "status": "ok", "service": "mock-poetry-domain-api", "naming": self.naming,
                "agent_token_configured": bool(self.agent_token),
                "reviewer_token_configured": bool(self.reviewer_token), **s.counts()})

        self.app.add_route("/__mock/reset", reset, methods=["POST"])
        self.app.add_route("/__mock/check-log", check_log, methods=["GET"])
        self.app.add_route("/__mock/health", health, methods=["GET"])
        self.app.add_route("/health/live", health, methods=["GET"])

    def _post_event(self, request: Request, body: Any) -> tuple[str, Any, list[str]]:
        run_id = request.path_params["run_id"]
        self.store.append_event(run_id, fld(body, "event_type"), body.get("payload"))
        return "ok", {"run_id": run_id, "recorded": True}, [f"agent-run:{run_id}"]

    def _get_events(self, request: Request, body: Any) -> tuple[str, Any, list[str]]:
        run_id = request.path_params["run_id"]
        after = as_int(request.query_params.get("after_event_id", "0"), -1)
        return "ok", self.store.list_events(run_id, after), [f"agent-events:{run_id}"]


def create_app(agent_token: str = "", reviewer_token: str = "", naming: str = "snake",
               v004_annotations: bool = False) -> FastAPI:
    """测试与脚本都从这里建应用,令牌显式传入,不读环境。"""
    mock = MockApp(agent_token, reviewer_token, naming, v004_annotations)
    mock.app.state.mock = mock
    return mock.app


def create_app_from_env() -> FastAPI:
    return create_app(
        agent_token=os.getenv("POETRY_AGENT_INTERNAL_TOKEN", ""),
        reviewer_token=os.getenv("POETRY_STUDIO_REVIEWER_TOKEN", ""),
        naming=os.getenv("MOCK_JSON_NAMING", "snake").strip().lower(),
        v004_annotations=os.getenv("MOCK_SEED_V004_ANNOTATIONS", "") == "1",
    )


app = create_app_from_env()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")),
                log_level="info")


if __name__ == "__main__":
    main()
