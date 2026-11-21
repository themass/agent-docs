"""dev-mock 测试的共用常量与辅助函数(fixtures 在 conftest.py)。

根 pyproject 的 testpaths 只含 content-agent/agent,本目录的测试需要单独运行(见 ../README.md):
    uv run pytest content-agent/deploy/dev-mock/tests
测试只用明显的假令牌,内存数据,不联网。
"""
from __future__ import annotations

AGENT = "test-fake-agent-token"
STUDIO = "test-fake-studio-token"
WORK = "work-chun-wang"
VERSION = "text-chun-wang-draft"
FP = "a" * 64


def agent_headers(run="run_t1", mandate="mandate_t1", key="idem-key-000001", role="CONTENT_EDITOR"):
    return {
        "X-Poetry-Agent-Internal-Token": AGENT,
        "X-Poetry-Agent-Run-Id": run,
        "X-Poetry-Agent-Mandate-Id": mandate,
        "Idempotency-Key": key,
        "X-Poetry-Agent-Role": role,
    }


ORCH_HEADERS = {"X-Poetry-Agent-Internal-Token": AGENT}
STUDIO_HEADERS = {"X-Poetry-Studio-Reviewer-Token": STUDIO}
REVIEWER = {"reviewer": "陈老师", "reviewer_role": "HISTORICAL_REVIEWER"}


def annotation_change(n: int, seq: int = 1, **overrides):
    payload = {
        "operation": "CREATE_ANNOTATION", "id": f"ann-t-{n}", "version_id": VERSION, "line_seq": seq,
        "annotation_kind": "WORD", "audience": "PRIMARY", "content": "草稿注释",
        "claim_id": f"claim-ann-t-{n}", "claim_value": "草稿", "certainty": "LIKELY",
        "source_id": None, "locator": None,
    }
    payload.update(overrides)
    return {"change_type": "ANNOTATION", "classification": "DRAFT", "body": "【草稿】x",
            "draft_payload": payload}


def gap_change():
    return {"change_type": "GAP_REPORT", "classification": "DRAFT", "body": "【缺口】g"}


def proposal_body(changes, work=WORK):
    return {"work_id": work, "proposal": {
        "schema_version": 1, "status": "DRAFT", "summary": "s",
        "human_review_question": "q?", "changes": changes}}


def create_proposal(client, changes, key="create-key-0001"):
    r = client.post("/api/poetry/v1/draft/proposals", headers=agent_headers(key=key),
                    json=proposal_body(changes))
    assert r.status_code == 200, r.text
    return r.json()["data"]["proposal_id"]


def approve(client, pid, review_id="review_1", key="review-key-0001"):
    r = client.post(f"/api/poetry/v1/draft/proposals/{pid}/reviews", headers=agent_headers(key=key),
                    json={"review_id": review_id, "reviewer_id": "陈老师", "decision": "APPROVE"})
    assert r.status_code == 200, r.text
    return review_id
