"""编排状态机、提案创建/评审/应用、幂等收据、D7 逐项语义。"""
from __future__ import annotations

from mock_test_helpers import (
    FP,
    ORCH_HEADERS,
    REVIEWER,
    STUDIO_HEADERS,
    WORK,
    agent_headers,
    annotation_change,
    approve,
    create_proposal,
    gap_change,
)

API = "/api/poetry/v1"
ORCH = f"{API}/agent-orchestration"


def run_body(run="run_x", mandate="mandate_x", **kw):
    body = {"run_id": run, "mandate_id": mandate, "runtime": "STUB", "profile_name": "authoring",
            "profile_fingerprint": FP, "profile_manifest": {}}
    body.update(kw)
    return body


# ---------------------------------------------------------------- 状态机
def test_task_run_event_lifecycle(flow):
    c = flow
    assert c.get(f"{ORCH}/tasks/task_t1", headers=ORCH_HEADERS).json()["data"]["status"] == "RUNNING"
    run = c.get(f"{ORCH}/runs/run_t1", headers=ORCH_HEADERS).json()["data"]
    assert run["status"] == "WAITING_FOR_RUNTIME" and run["work_id"] == WORK
    r = c.put(f"{ORCH}/runs/run_t1/state", headers=ORCH_HEADERS, json={"status": "AWAITING_REVIEW", "reason": "ok"})
    assert r.json()["data"]["status"] == "AWAITING_REVIEW"
    assert c.get(f"{ORCH}/tasks/task_t1", headers=ORCH_HEADERS).json()["data"]["status"] == "AWAITING_REVIEW"
    assert c.put(f"{ORCH}/runs/run_t1/state", headers=ORCH_HEADERS, json={"status": "CANCELLED"}).status_code == 400
    c.post(f"{ORCH}/runs/run_t1/events", headers=ORCH_HEADERS, json={"event_type": "STEP", "payload": {"a": 1}})
    events = c.get(f"{ORCH}/runs/run_t1/events?after_event_id=0", headers=ORCH_HEADERS).json()["data"]
    assert [e["event_type"] for e in events] == ["RUN_CREATED", "RUN_STATE_CHANGED", "STEP"]
    assert events[2]["payload_json"] == '{"a": 1}'
    later = c.get(f"{ORCH}/runs/run_t1/events?after_event_id={events[1]['event_id']}", headers=ORCH_HEADERS)
    assert [e["event_type"] for e in later.json()["data"]] == ["STEP"]


def test_run_creation_validation(flow):
    c = flow
    assert c.post(f"{ORCH}/tasks/task_t1/runs", headers=ORCH_HEADERS, json=run_body(run="run_t1")).status_code == 409
    assert c.post(f"{ORCH}/tasks/task_t1/runs", headers=ORCH_HEADERS, json=run_body(runtime="X")).status_code == 400
    bad_fp = run_body(profile_fingerprint="abc")
    assert c.post(f"{ORCH}/tasks/task_t1/runs", headers=ORCH_HEADERS, json=bad_fp).status_code == 400
    assert c.post(f"{ORCH}/tasks/nope/runs", headers=ORCH_HEADERS, json=run_body()).status_code == 400


def test_task_creation_validation(client):
    base = {"task_id": "task_a", "work_id": WORK, "title": "t", "task_type": "GAP_ANALYSIS",
            "requested_by": "x", "requested_role": "CONTENT_EDITOR", "instructions": "i",
            "requested_profile": "authoring"}
    assert client.post(f"{ORCH}/tasks", headers=ORCH_HEADERS, json=base).status_code == 200
    assert client.post(f"{ORCH}/tasks", headers=ORCH_HEADERS, json=base).status_code == 409
    for patch in ({"task_id": "bad"}, {"task_type": "PUBLISH"}, {"requested_role": "ROOT"},
                  {"work_id": "no-such-work"}, {"title": ""}):
        assert client.post(f"{ORCH}/tasks", headers=ORCH_HEADERS,
                           json={**base, "task_id": "task_b", **patch}).status_code == 400


def test_camelcase_request_fields_are_accepted(client):
    r = client.post(f"{ORCH}/tasks", headers=ORCH_HEADERS, json={
        "taskId": "task_c", "workId": WORK, "title": "t", "taskType": "GAP_ANALYSIS",
        "requestedBy": "x", "requestedRole": "CONTENT_EDITOR", "instructions": "i",
        "requestedProfile": "authoring"})
    assert r.status_code == 200


def test_new_list_routes_paginate_and_filter(flow):
    c = flow
    page = c.get(f"{ORCH}/tasks?work_id={WORK}&status=RUNNING&limit=1", headers=ORCH_HEADERS).json()["data"]
    assert page["limit"] == 1 and page["offset"] == 0 and len(page["items"]) == 1 and page["has_more"] is False
    assert c.get(f"{ORCH}/tasks?status=COMPLETED", headers=ORCH_HEADERS).json()["data"]["items"] == []
    assert c.get(f"{ORCH}/works?limit=500", headers=ORCH_HEADERS).json()["data"]["limit"] == 200
    assert c.get(f"{ORCH}/works?limit=0", headers=ORCH_HEADERS).status_code == 400
    assert c.get(f"{ORCH}/works?offset=-1", headers=ORCH_HEADERS).status_code == 400
    runs = c.get(f"{ORCH}/tasks/task_t1/runs", headers=ORCH_HEADERS).json()["data"]["items"]
    assert [r["run_id"] for r in runs] == ["run_t1"]


# ---------------------------------------------------------------- 提案
def test_proposal_validation(flow):
    c = flow
    h = agent_headers()
    bad = [
        {"work_id": WORK, "proposal": {"schema_version": 2, "status": "DRAFT"}},
        {"work_id": WORK, "proposal": {"schema_version": 1, "status": "APPROVED", "summary": "s",
                                       "human_review_question": "q", "changes": [gap_change()]}},
        {"work_id": WORK, "proposal": {"schema_version": 1, "status": "DRAFT", "summary": "s",
                                       "human_review_question": "q", "changes": []}},
        {"work_id": "no-such", "proposal": {}},
    ]
    for i, body in enumerate(bad):
        assert c.post(f"{API}/draft/proposals", headers=agent_headers(key=f"bad-key-{i:06d}"), json=body).status_code == 400
    wrong_op = gap_change() | {"draft_payload": {"operation": "PUBLISH"}}
    r = c.post(f"{API}/draft/proposals", headers=h, json={"work_id": WORK, "proposal": {
        "schema_version": 1, "status": "DRAFT", "summary": "s", "human_review_question": "q",
        "changes": [wrong_op]}})
    assert r.status_code == 400
    bad_class = gap_change() | {"classification": "FACT"}
    r = c.post(f"{API}/draft/proposals", headers=agent_headers(key="bad-key-class01"), json={
        "work_id": WORK, "proposal": {"schema_version": 1, "status": "DRAFT", "summary": "s",
                                      "human_review_question": "q", "changes": [bad_class]}})
    assert r.status_code == 400


def test_create_proposal_is_idempotent(flow):
    c = flow
    body = {"work_id": WORK, "proposal": {"schema_version": 1, "status": "DRAFT", "summary": "s",
                                          "human_review_question": "q", "changes": [gap_change()]}}
    first = c.post(f"{API}/draft/proposals", headers=agent_headers(key="same-key-00001"), json=body).json()
    assert first["status"] == "REVIEW_REQUIRED" and first["next_action"] == "HUMAN_REVIEW"
    again = c.post(f"{API}/draft/proposals", headers=agent_headers(key="same-key-00001"), json=body).json()
    assert again["data"] == {"proposal_id": first["data"]["proposal_id"], "idempotent": True}
    pid = first["data"]["proposal_id"]
    assert c.get(f"{ORCH}/proposals/{pid}", headers=ORCH_HEADERS).json()["data"]["review_status"] == "PENDING"


def test_review_state_machine(flow):
    c = flow
    pid = create_proposal(c, [gap_change()])
    path = f"{API}/draft/proposals/{pid}/reviews"
    body = {"review_id": "review_1", "reviewer_id": "陈老师", "decision": "APPROVE"}
    assert c.post(path, headers=agent_headers(key="rv-bad-000001"), json={**body, "decision": "MAYBE"}).status_code == 400
    assert c.post(path, headers=agent_headers(key="rv-bad-000002"), json={**body, "review_id": ""}).status_code == 400
    # mandate 不匹配
    assert c.post(path, headers=agent_headers(mandate="mandate_other", key="rv-bad-000003"), json=body).status_code == 400
    ok = c.post(path, headers=agent_headers(key="rv-ok-0000001"), json=body)
    assert ok.json()["data"]["review_status"] == "APPROVED"
    replay = c.post(path, headers=agent_headers(key="rv-ok-0000001"), json=body)
    assert replay.json()["data"]["idempotent"] is True
    second = c.post(path, headers=agent_headers(key="rv-ok-0000002"), json={**body, "review_id": "review_2"})
    assert second.status_code == 409 and second.json()["status"] == "CONFLICT"


# ---------------------------------------------------------------- apply
def apply(c, pid, review_id, key):
    return c.post(f"{API}/draft/proposals/{pid}/apply", headers=agent_headers(key=key),
                  json={"review_id": review_id})


def test_apply_requires_approved_review_and_matching_review_id(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1)])
    assert apply(c, pid, "review_1", "ap-0000000001").status_code == 409  # 尚未评审
    approve(c, pid)
    assert apply(c, pid, "review_other", "ap-0000000002").status_code == 400
    assert apply(c, pid, "", "ap-0000000003").status_code == 400


def test_apply_creates_draft_annotation_and_is_idempotent(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1), gap_change()])
    approve(c, pid)
    r = apply(c, pid, "review_1", "ap-ok-00000001")
    data = r.json()["data"]
    assert data["content_state"] == "DRAFT_ONLY"
    assert data["applied_operations"] == ["CREATE_ANNOTATION:ann-t-1"]
    assert data["retained_editorial_changes"] == ["GAP_REPORT"]
    assert apply(c, pid, "review_1", "ap-ok-00000001").json()["data"]["idempotent"] is True
    snap = c.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers(key="snap-key-00001")).json()["data"]
    assert [a["id"] for a in snap["annotations"]] == ["ann-t-1"]
    claim = next(x for x in snap["claims"] if x["id"] == "claim-ann-t-1")
    assert claim["claim_kind"] == "INTERPRETATION" and claim["status"] == "DRAFT"
    assert claim["property_key"] == "annotation.WORD"
    # 已 APPLIED 的提案换幂等键再应用:claim 已存在,Java 先于状态转换检查它
    again = apply(c, pid, "review_1", "ap-ok-00000002")
    assert again.status_code == 400 and again.json()["error"].startswith("claim id already exists")


def test_apply_vocabulary_and_existence_checks_use_java_words(flow):
    c = flow
    cases = {
        "audience": annotation_change(1, audience="MIDDLE"),       # 旧 schema 的词,Java 不认
        "certainty": annotation_change(2, certainty="HIGH"),        # 旧 schema 的词,Java 不认
        "kind": annotation_change(3, annotation_kind="SYMBOL"),
        "line": annotation_change(4, seq=99),
        "version": annotation_change(5, version_id="text-missing"),
        "source": annotation_change(6, source_id="source-missing", locator="x"),
        "locator": annotation_change(7, source_id="source-anshi-candidate", locator=None),
    }
    for i, (name, change) in enumerate(cases.items()):
        pid = create_proposal(c, [change], key=f"cr-{name}-000001"[:24])
        approve(c, pid, review_id=f"review_{i}", key=f"rv-{name}-000001"[:24])
        r = apply(c, pid, f"review_{i}", f"ap-{name}-000001"[:24])
        assert r.status_code == 400, (name, r.text)
        assert r.json()["errno"] == 400 and r.json()["data"] is None
    snap = c.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers(key="snap-key-00002")).json()["data"]
    assert snap["annotations"] == []  # 失败的应用不留半截数据


def test_apply_is_atomic_when_a_later_change_fails(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1), annotation_change(2, audience="MIDDLE")])
    approve(c, pid)
    assert apply(c, pid, "review_1", "ap-atomic-00001").status_code == 400
    snap = c.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers(key="snap-key-00003")).json()["data"]
    assert snap["annotations"] == [] and all(x["id"] != "claim-ann-t-1" for x in snap["claims"])


def test_apply_accepts_lowercase_vocabulary_like_java_upper(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1, audience="primary", annotation_kind="word")])
    approve(c, pid)
    assert apply(c, pid, "review_1", "ap-lower-00001").status_code == 200


# ---------------------------------------------------------------- D7 逐项语义
def put_items(c, pid, decisions, headers=STUDIO_HEADERS, reviewer=None):
    return c.put(f"{API}/studio/proposals/{pid}/items", headers=headers,
                 json={**(reviewer or REVIEWER), "decisions": decisions})


def test_d7_without_item_records_applies_everything(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1), annotation_change(2, seq=2)])
    approve(c, pid)
    ops = apply(c, pid, "review_1", "ap-d7a-0000001").json()["data"]["applied_operations"]
    assert ops == ["CREATE_ANNOTATION:ann-t-1", "CREATE_ANNOTATION:ann-t-2"]


def test_d7_only_explicitly_approved_executable_items_run(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1), annotation_change(2, seq=2),
                              annotation_change(3, seq=3), gap_change()])
    assert put_items(c, pid, [{"item_index": 0, "decision": "APPROVE"},
                              {"item_index": 1, "decision": "REJECT", "comment": "措辞待核"}]).status_code == 200
    approve(c, pid)
    data = apply(c, pid, "review_1", "ap-d7b-0000001").json()["data"]
    assert data["applied_operations"] == ["CREATE_ANNOTATION:ann-t-1"]  # 1 被驳回,2 没有记录 => 都不执行
    assert data["retained_editorial_changes"] == ["GAP_REPORT"]


def test_d7_all_rejected_applies_nothing_but_still_succeeds(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1)])
    put_items(c, pid, [{"item_index": 0, "decision": "REJECT"}])
    approve(c, pid)
    r = apply(c, pid, "review_1", "ap-d7c-0000001")
    assert r.status_code == 200 and r.json()["data"]["applied_operations"] == []


def test_d7_items_overwrite_and_listing(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1), gap_change()])
    put_items(c, pid, [{"item_index": 0, "decision": "REJECT"}])
    put_items(c, pid, [{"item_index": 0, "decision": "APPROVE"}, {"item_index": 1, "decision": "APPROVE"}])
    items = c.get(f"{ORCH}/proposals/{pid}/items", headers=ORCH_HEADERS).json()["data"]["items"]
    assert [(i["item_index"], i["decision"], i["reviewer"]) for i in items] == [
        (0, "APPROVE", "陈老师"), (1, "APPROVE", "陈老师")]  # 非可执行项也记录,但不影响应用


def test_d7_items_validation(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1)])
    assert put_items(c, pid, [{"item_index": 5, "decision": "APPROVE"}]).status_code == 400
    assert put_items(c, pid, [{"item_index": 0, "decision": "MAYBE"}]).status_code == 400
    dup = [{"item_index": 0, "decision": "APPROVE"}, {"item_index": 0, "decision": "REJECT"}]
    assert put_items(c, pid, dup).status_code == 400
    assert put_items(c, pid, []).status_code == 400
    assert put_items(c, "proposal_nope", [{"item_index": 0, "decision": "APPROVE"}]).status_code == 404
    approve(c, pid)
    assert put_items(c, pid, [{"item_index": 0, "decision": "APPROVE"}]).status_code == 409  # 已不在 PENDING


def test_compile_request_reports_blocked_while_gaps_exist(flow):
    c = flow
    r = c.post(f"{API}/works/{WORK}/compile-requests", headers=agent_headers(key="cmp-key-000001"),
               json={"script_version": "0.1.0"})
    assert r.json()["status"] == "REVIEW_REQUIRED" and r.json()["data"]["state"] == "BLOCKED"
    assert c.post(f"{API}/works/{WORK}/compile-requests", headers=agent_headers(key="cmp-key-000002"),
                  json={"script_version": ""}).status_code == 400
