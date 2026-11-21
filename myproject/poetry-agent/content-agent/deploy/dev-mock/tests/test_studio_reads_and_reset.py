"""studio 人类写端点、来源核验门槛、新只读视图(coverage / studio-view / sources)、reset、种子保真。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mock_domain_api import create_app
from mock_test_helpers import (
    AGENT,
    ORCH_HEADERS,
    REVIEWER,
    STUDIO,
    STUDIO_HEADERS,
    VERSION,
    WORK,
    agent_headers,
    annotation_change,
    approve,
    create_proposal,
)

API = "/api/poetry/v1"
ORCH = f"{API}/agent-orchestration"
CIT = f"{API}/studio/citations"
SRC = f"{API}/studio/sources"


def set_locator(c, claim, source, locator="卷二百一十八(演示用,非真实出处)", **extra):
    return c.put(f"{CIT}/{claim}/{source}/locator", headers=STUDIO_HEADERS,
                 json={"locator": locator, **REVIEWER, **extra})


def verify(c, source, decision="VERIFY", **extra):
    return c.post(f"{SRC}/{source}/verification", headers=STUDIO_HEADERS,
                  json={"decision": decision, **REVIEWER, **extra})


# ---------------------------------------------------------------- locator
def test_set_locator_updates_citation_but_not_source_status(client):
    r = set_locator(client, "claim-anshi-time", "source-anshi-candidate", evidence_excerpt="摘录")
    assert r.status_code == 200
    assert r.json()["data"]["locator_state"] == "SET"
    assert r.json()["data"]["source_verification_status"] == "PENDING"
    src = next(s for s in client.get(f"{ORCH}/sources", headers=ORCH_HEADERS).json()["data"]["items"]
               if s["id"] == "source-anshi-candidate")
    cit = next(c for c in src["citations"] if c["claim_id"] == "claim-anshi-time")
    assert cit["locator_state"] == "SET" and cit["evidence_excerpt"] == "摘录"
    assert src["verification_status"] == "PENDING"


@pytest.mark.parametrize("locator", ["", "   ", "待核查", "待人工核对", "未核对", "TBD", "x" * 301])
def test_set_locator_rejects_empty_placeholder_and_overlong(client, locator):
    assert set_locator(client, "claim-anshi-time", "source-anshi-candidate", locator).status_code == 400


def test_set_locator_unknown_citation_is_404_and_role_is_checked(client):
    assert set_locator(client, "claim-anshi-time", "source-dufu-nianpu-candidate").status_code == 404
    r = client.put(f"{CIT}/claim-anshi-time/source-anshi-candidate/locator", headers=STUDIO_HEADERS,
                   json={"locator": "卷二", "reviewer": "陈老师", "reviewer_role": "CONTENT_EDITOR"})
    assert r.status_code == 403  # 内容编辑不能填 locator


@pytest.mark.parametrize("name", ["x", "agent-li", "DeerFlow", "mcp-bot", "AI助手", "system", "a" * 101])
def test_reviewer_signature_rules(client, name):
    r = client.put(f"{CIT}/claim-anshi-time/source-anshi-candidate/locator", headers=STUDIO_HEADERS,
                   json={"locator": "卷二", "reviewer": name, "reviewer_role": "HISTORICAL_REVIEWER"})
    assert r.status_code == 400


# ---------------------------------------------------------------- 来源核验
def test_verify_needs_every_citation_locator_set(client):
    r = verify(client, "source-dufu-zhuan-candidate")
    assert r.status_code == 409 and r.json()["status"] == "CONFLICT"
    missing = {(m["claim_id"], m["locator_state"]) for m in r.json()["data"]["missing_locators"]}
    assert missing == {("claim-dufu-time", "PLACEHOLDER"), ("claim-bg-person", "PLACEHOLDER")}
    for claim in ("claim-dufu-time", "claim-bg-person"):
        assert set_locator(client, claim, "source-dufu-zhuan-candidate").status_code == 200
    r = verify(client, "source-dufu-zhuan-candidate", note="演示")
    assert r.status_code == 200 and r.json()["data"]["verification_status"] == "VERIFIED"


def test_verify_is_blocked_by_publication_gate_when_kind_or_reliability_missing(client):
    # 种子里 source-chun-wang-candidate 没有 source_kind / reliability(V002 原样)
    set_locator(client, "claim-chun-wang-author", "source-chun-wang-candidate")
    r = verify(client, "source-chun-wang-candidate")
    assert r.status_code == 409
    assert "source_kind missing or outside vocabulary" in r.json()["data"]["blocking"]


@pytest.mark.parametrize("name", ["DEMO-reviewer", "root", "NULL"])
def test_gate_rejects_machine_or_rehearsal_names(client, name):
    set_locator(client, "claim-dufu-time", "source-dufu-zhuan-candidate")
    set_locator(client, "claim-bg-person", "source-dufu-zhuan-candidate")
    r = client.post(f"{SRC}/source-dufu-zhuan-candidate/verification", headers=STUDIO_HEADERS,
                    json={"decision": "VERIFY", "reviewer": name, "reviewer_role": "HISTORICAL_REVIEWER"})
    assert r.status_code in (400, 409)


def test_reject_decision_and_validation(client):
    r = verify(client, "source-anshi-candidate", "REJECT")
    assert r.status_code == 200 and r.json()["data"]["verification_status"] == "REJECTED"
    assert verify(client, "source-anshi-candidate", "PUBLISH").status_code == 400
    assert verify(client, "source-missing").status_code == 404


def test_verify_requires_source_review_role(client):
    r = client.post(f"{SRC}/source-anshi-candidate/verification", headers=STUDIO_HEADERS,
                    json={"decision": "VERIFY", "reviewer": "陈老师", "reviewer_role": "CONTENT_EDITOR"})
    assert r.status_code == 403


def test_every_studio_write_is_logged(client):
    set_locator(client, "claim-anshi-time", "source-anshi-candidate")
    verify(client, "source-anshi-candidate", "REJECT")
    log = client.get("/__mock/check-log").json()["items"]
    assert [row["action"] for row in log] == ["SET_LOCATOR", "REJECT"]
    assert all(row["reviewer"] == "陈老师" and row["reviewer_role"] == "HISTORICAL_REVIEWER" for row in log)


def test_gap_report_changes_after_source_is_verified(client):
    for claim in ("claim-chun-wang-author",):
        set_locator(client, claim, "source-chun-wang-candidate")
    # 候选来源缺 kind/reliability,核验被闸门挡住 => 缺口不变
    verify(client, "source-chun-wang-candidate")
    codes = [g["code"] for g in client.get(f"{API}/works/{WORK}/integrity-gap-report",
                                           headers=agent_headers()).json()["data"]["gaps"]]
    assert "TEXT_SOURCE_NOT_VERIFIED" in codes


# ---------------------------------------------------------------- 只读视图
def test_sources_list_shape_and_filter(client):
    page = client.get(f"{ORCH}/sources?verification_status=PENDING", headers=ORCH_HEADERS).json()["data"]
    assert len(page["items"]) == 4 and {"limit", "offset", "has_more"} <= set(page)
    first = page["items"][0]
    assert {"id", "title", "verification_status", "citations", "source_kind", "reliability"} <= set(first)
    assert {"claim_id", "claim_value", "claim_kind", "claim_status", "locator", "evidence_excerpt",
            "locator_state"} == set(first["citations"][0])
    assert {c["locator_state"] for s in page["items"] for c in s["citations"]} == {"PLACEHOLDER"}
    assert client.get(f"{ORCH}/sources?verification_status=VERIFIED", headers=ORCH_HEADERS).json()["data"]["items"] == []
    assert client.get(f"{ORCH}/sources?verification_status=BOGUS", headers=ORCH_HEADERS).status_code == 400


def test_coverage_shape(client):
    d = client.get(f"{ORCH}/works/{WORK}/coverage", headers=ORCH_HEADERS).json()["data"]
    assert set(d) == {"work_id", "totals", "claims_by_status", "claims_checkable", "sources_by_verification",
                      "layers", "lines", "gap_codes", "publication"}
    assert d["totals"]["lines"] == 8 and d["totals"]["versions"] == 1 and d["totals"]["backgrounds"] == 4
    assert d["totals"]["annotations"] == 0 and d["totals"]["sources"] == 4
    assert d["sources_by_verification"] == {"PENDING": 4, "VERIFIED": 0, "REJECTED": 0}
    assert d["claims_checkable"]["checkable"] == 0
    assert set(d["layers"]) == {"SCENE", "CITY", "WORLD", "PERSON"}
    assert d["layers"]["WORLD"] == {"count": 1, "linked_lines": 2}
    assert len(d["lines"]) == 8 and d["lines"][0]["layers"] == ["CITY", "SCENE"]
    assert d["lines"][4]["layers"] == ["WORLD"] and d["lines"][2]["layers"] == []
    assert d["publication"] == {"work_status": "DRAFT", "published_claims": 0, "audit_checks": 106,
                                "audit_non_zero": []}
    assert "CLAIM_VERIFIED_CITATION_MISSING" in d["gap_codes"]


def test_coverage_of_empty_work(client):
    d = client.get(f"{ORCH}/works/work-demo-empty/coverage", headers=ORCH_HEADERS).json()["data"]
    assert d["totals"]["lines"] == 0 and d["lines"] == [] and d["totals"]["versions"] == 0
    assert d["gap_codes"][:2] == ["TEXT_VERSION_MISSING", "TEXT_LINES_MISSING"]


def test_studio_view_extends_snapshot(client):
    d = client.get(f"{ORCH}/works/{WORK}/studio-view", headers=ORCH_HEADERS).json()["data"]
    assert {"work", "work_info", "versions", "lines", "claims", "citations", "backgrounds", "annotations",
            "sources", "background_lines", "claim_status_by_id", "content_status_by_id",
            "version_status_by_id", "source_verification_by_id", "coverage_rows", "gap_report"} == set(d)
    assert len(d["lines"]) == 8 and len(d["background_lines"]) == 8
    assert d["version_status_by_id"] == {VERSION: "DRAFT"}
    assert all(v == "PENDING" for v in d["source_verification_by_id"].values())
    assert d["claim_status_by_id"]["claim-bg-scene"] == "DRAFT"  # 背景 claim 在 studio-view 里可见
    assert d["gap_report"]["work_id"] == WORK


def test_snapshot_claim_scope_is_java_strict_but_studio_view_is_wider(client):
    snap = client.get(f"{API}/works/{WORK}/snapshot", headers=agent_headers()).json()["data"]
    assert sorted(c["id"] for c in snap["claims"]) == [
        "claim-chun-wang-author", "claim-chun-wang-time-757", "claim-chun-wang-time-758"]
    wide = client.get(f"{ORCH}/works/{WORK}/studio-view", headers=ORCH_HEADERS).json()["data"]
    assert len(wide["claims"]) == 7


def test_works_list(client):
    items = client.get(f"{ORCH}/works", headers=ORCH_HEADERS).json()["data"]["items"]
    assert [w["work_id"] for w in items] == ["work-chun-wang", "work-demo-empty"]
    chun = items[0]
    assert (chun["line_count"], chun["version_count"], chun["background_count"], chun["annotation_count"]) == (8, 1, 4, 0)
    assert items[1]["line_count"] == 0 and items[1]["version_count"] == 0


# ---------------------------------------------------------------- reset
def test_reset_restores_seed(flow):
    c = flow
    pid = create_proposal(c, [annotation_change(1)])
    approve(c, pid)
    c.post(f"{API}/draft/proposals/{pid}/apply", headers=agent_headers(key="ap-reset-00001"),
           json={"review_id": "review_1"})
    set_locator(c, "claim-anshi-time", "source-anshi-candidate")
    r = c.post("/__mock/reset")
    assert r.status_code == 200 and r.json()["annotations"] == 0
    assert c.get(f"{ORCH}/tasks", headers=ORCH_HEADERS).json()["data"]["items"] == []
    assert c.get(f"{ORCH}/proposals", headers=ORCH_HEADERS).json()["data"]["items"] == []
    d = c.get(f"{ORCH}/works/{WORK}/coverage", headers=ORCH_HEADERS).json()["data"]
    assert d["totals"]["annotations"] == 0
    assert c.get("/__mock/check-log").json()["items"] == []
    src = next(s for s in c.get(f"{ORCH}/sources", headers=ORCH_HEADERS).json()["data"]["items"]
               if s["id"] == "source-anshi-candidate")
    assert {x["locator_state"] for x in src["citations"]} == {"PLACEHOLDER"}


def test_reset_path_is_mock_only(client):
    assert client.post(f"{API}/__mock/reset").status_code == 404
    assert client.post(f"{ORCH}/__mock/reset").status_code == 404


def test_v004_annotations_flag_loads_real_seed_annotations():
    app = create_app(agent_token=AGENT, reviewer_token=STUDIO, v004_annotations=True)
    with TestClient(app) as c:
        d = c.get(f"{ORCH}/works/{WORK}/coverage", headers=ORCH_HEADERS).json()["data"]
        assert d["totals"]["annotations"] == 2
        ids = [a["id"] for a in c.get(f"{ORCH}/works/{WORK}/studio-view",
                                      headers=ORCH_HEADERS).json()["data"]["annotations"]]
        assert ids == ["ann-chun-wang-shanhe", "ann-chun-wang-fenghuo"]


# ---------------------------------------------------------------- 种子保真
SQL_DIR = Path("/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry")


@pytest.mark.skipif(not (SQL_DIR / "V004__chunwang_context_draft.sql").exists(), reason="Java 迁移文件不在本机")
def test_seed_text_is_verbatim_from_v002_v004():
    import seed

    # V010 是后续的「内容决定」迁移，改的是 V004 里种下的值（例如 place-chang-an 的今地名）。
    # 种子保真检查必须把后续迁移算进来，否则它会把「被后续迁移改过的值」当成漂移。
    sql = "".join((SQL_DIR / f).read_text(encoding="utf-8")
                  for f in ("V002__draft_seed.sql", "V004__chunwang_context_draft.sql",
                            "V010__content_decisions.sql", "V012__reader_text_cleanup.sql"))
    data = seed.build_seed(include_v004_annotations=True)
    mock_only = {seed.EMPTY_WORK_ID}
    missing: list[str] = []

    def walk(value, owner=""):
        if isinstance(value, str):
            if re.search("[一-鿿]", value) and value not in sql and owner not in mock_only:
                missing.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, key if key in mock_only else owner)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, owner)

    for key, row in data["contents"].items():
        if key not in mock_only:
            walk(row)
    for part in ("versions", "lines", "sources", "claims", "citations", "backgrounds", "annotations"):
        walk(data[part])
    assert missing == []
    assert [data["lines"][(seed.VERSION_ID, i)]["content"] for i in range(1, 9)] == seed.LINES
    assert all(s["verification_status"] == "PENDING" for s in data["sources"].values())
    assert all(c["locator"].startswith("待") for c in data["citations"].values())
