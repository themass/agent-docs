"""dev-mock 测试夹具。

根 pyproject 的 testpaths 只含 content-agent/agent,本目录的测试需要单独运行(见 ../README.md):
    uv run pytest content-agent/deploy/dev-mock/tests
根配置使用 --import-mode=importlib,不会自动把目录加入 sys.path,所以这里显式加入。
测试只用明显的假令牌,内存数据,不联网。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from fastapi.testclient import TestClient
from mock_domain_api import create_app
from mock_test_helpers import AGENT, FP, ORCH_HEADERS, STUDIO, WORK


@pytest.fixture()
def client():
    """默认 snake,与真实 Java 一致。"""
    app = create_app(agent_token=AGENT, reviewer_token=STUDIO, naming="snake")
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def camel_client():
    """模拟"有问题的宿主"(旧端点 record 键名为 camelCase),用来验证消费方的兜底规范化。"""
    app = create_app(agent_token=AGENT, reviewer_token=STUDIO, naming="camel")
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def flow(client):
    """建好任务 + 运行,返回 (client, 辅助函数)。运行的 mandate 与 agent_headers 默认值对应。"""
    r = client.post("/api/poetry/v1/agent-orchestration/tasks", headers=ORCH_HEADERS, json={
        "task_id": "task_t1", "work_id": WORK, "title": "标注草稿", "task_type": "ANNOTATION_DRAFT",
        "requested_by": "editor-li", "requested_role": "CONTENT_EDITOR",
        "instructions": "为第1行起草注释", "requested_profile": "authoring"})
    assert r.status_code == 200, r.text
    r = client.post("/api/poetry/v1/agent-orchestration/tasks/task_t1/runs", headers=ORCH_HEADERS, json={
        "run_id": "run_t1", "mandate_id": "mandate_t1", "runtime": "STUB", "profile_name": "authoring",
        "profile_fingerprint": FP, "profile_manifest": {}})
    assert r.status_code == 200, r.text
    return client
