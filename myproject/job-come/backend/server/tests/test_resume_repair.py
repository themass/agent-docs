"""The evaluate → repair loop, tested as flows rather than per-function.

Five of these cover the whole feature: when it stays out of the way, when it improves a
draft, when it refuses one, what it may not touch, and what happens when it breaks.
No real model calls.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_elevator import ResumeElevator
from jc.services.resume_repair import (
    PLACEHOLDERS,
    accept_repair,
    merge_repaired_blocks,
    plan_repair,
)

WEAK = "参与相关工作"
DROPPED = "支撑 8 大基地、5000+ 审核人员的内容安全审核"
STRONG = "主导订单链路微服务化，日均 1200 万单，P99 从 800ms 降到 120ms"

SOURCE = {
    "contact": {"name": "测试"},
    "meta": {"source_locale": "zh-CN"},
    "experiences": [{
        "id": "e1", "company": "快手", "title": "服务端 leader",
        "start_date": "2021-07", "scope": "带 10 人团队",
        "highlights": [WEAK, DROPPED],
    }],
}


def profile(**over) -> ProfilePayload:
    return ProfilePayload.model_validate({**copy.deepcopy(SOURCE), **over})


def draft(bullets=None, **over) -> dict:
    return {
        "locale": "zh-CN", "role_family": "backend", "summary": "", **over,
        "experience_blocks": [{
            "id": "e1", "company": "快手", "title": "服务端 leader",
            "scope_line": "带 10 人团队", "bullets": bullets or [WEAK],
        }],
    }


def router_for(responses: list[dict]) -> tuple[SimpleNamespace, list[str]]:
    """A writer that answers each call with a fresh copy of the next response.

    Fresh copies matter: the elevator's guards mutate the dict they are handed, so a
    shared fixture would be altered before a later call reads it.
    """
    calls: list[str] = []

    async def acompletion(*_args, **kwargs):
        calls.append(getattr(kwargs.get("log_context"), "caller", ""))
        index = min(len(calls) - 1, len(responses) - 1)
        return copy.deepcopy(responses[index])

    return SimpleNamespace(acompletion=acompletion,
                           chain_for=lambda _: [object()] * 3), calls


def test_repair_stays_out_of_the_way_unless_it_is_both_needed_and_verifiable():
    """The three cases that cost nothing, and the two defects that are not repairable.

    A repair is skipped when there is no profile to verify against (every honesty gate
    needs the source; `audit_additions` passes vacuously without one), when the writer
    never ran (retrying a failed pipeline is what `profile_ingest_service` forbids), and
    when nothing is measurably wrong — the common case, and why this is affordable.
    """
    good = profile(experiences=[{**SOURCE["experiences"][0], "highlights": [STRONG]}])
    strong = draft(bullets=[STRONG],
                   summary="十年服务端，带 10 人团队，主导订单链路微服务化，日均 1200 万单")
    assert plan_repair(strong, good, role_family="backend") is None
    assert plan_repair(draft(), None, role_family="backend") is None
    assert plan_repair(
        draft(generation={"mode": "source_layout"}), profile(), role_family="backend"
    ) is None
    # A writer that did run but had paragraph boundaries restored is still repairable.
    assert plan_repair(
        draft(generation={"mode": "structure_guarded"}), profile(), role_family="backend"
    ) is not None

    # A missing scope line is never a repair reason: `scope` is user-supplied by
    # contract, so a model asked to fill it must invent a team size — into the one line
    # the writer skill calls the worst place for a false fact. It would also fire on
    # every English draft, where `scope_line` is structurally always None.
    no_scope = draft(bullets=[STRONG], summary="十年服务端，主导订单链路微服务化，日均 1200 万单")
    no_scope["experience_blocks"][0]["scope_line"] = None
    assert plan_repair(
        no_scope,
        profile(experiences=[{**SOURCE["experiences"][0], "scope": None,
                              "highlights": [STRONG]}]),
        role_family="backend",
    ) is None


@pytest.mark.asyncio
async def test_a_repair_that_restores_a_dropped_fact_reaches_the_document(monkeypatch):
    """The end-to-end win: the writer drops a source highlight, the repair puts it back.

    Exactly two model calls — write, then repair. Never a loop.
    """
    from jc.services import resume_elevator as mod

    p = profile(experiences=[{
        **SOURCE["experiences"][0],
        "highlights": ["负责审核系统，服务 8 大基地、5000+ 审核人员"],
    }])
    first = {"header": {"name": "测试"}, "summary": "", "experience_blocks": [
        {"id": "e1", "company": "快手", "title": "服务端 leader",
         "scope_line": "带 10 人团队", "bullets": [WEAK]}]}
    repair = {"summary": "十年服务端，带 10 人团队，负责审核系统",
              "experience_blocks": [{"id": "e1", "bullets": [
                  "负责审核系统，服务 8 大基地、5000+ 审核人员", WEAK]}]}
    router, calls = router_for([first, repair])
    monkeypatch.setattr(mod, "get_llm_router", lambda: router)
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)

    sections, _ = await ResumeElevator().build_sections(p, elevation_level="standard")
    assert calls == ["resume_elevator", "resume_repair"]
    assert sections["generation"]["repair"]["accepted"] is True, \
        sections["generation"]["repair"]
    assert "5000+ 审核人员" in sections["experience_blocks"][0]["bullets"][0]


def test_a_repair_is_refused_unless_it_is_honest_lossless_and_better():
    """The three gates, each on its own candidate.

    Honesty is the one that makes a second model call defensible at all: the fabrication
    set is compared as a set, keyed on `(kind, field_path, detail)`, so "fixed one,
    invented another" is caught rather than netting out.
    """
    base = draft()
    p = profile()
    invented = accept_repair(base, draft(bullets=["审核准确率提升至 99.7%"]), p,
                             role_family="backend")
    assert (invented.accepted, invented.reason) == (False, "introduced_unsupported_claim")

    lossy = accept_repair(draft(bullets=[WEAK, DROPPED]), draft(bullets=[WEAK]), p,
                          role_family="backend")
    assert (lossy.accepted, lossy.reason) == (False, "dropped_source_facts")

    # Without a strict-improvement gate, a second call just trades one sample for
    # another at double the cost.
    same = accept_repair(base, copy.deepcopy(base), p, role_family="backend")
    assert (same.accepted, same.reason) == (False, "not_an_improvement")

    # And no profile means nothing can be verified, so nothing is accepted.
    assert accept_repair(base, draft(bullets=[STRONG]), None).accepted is False


def test_a_repair_may_rewrite_accomplishments_and_nothing_else():
    """Identity fields, unrequested blocks and paragraph counts are all off limits.

    Identity is the sharp one: a rewrite was asked for the wording of accomplishments,
    and letting it restate the employer is how a confirmed title silently reverts.
    Paragraph count follows `_preserve_source_units` — one source paragraph stays one —
    except for a dropped highlight the repair was explicitly asked to restore.
    """
    base = draft()
    before = copy.deepcopy(base)
    plan = plan_repair(base, profile(), role_family="backend")
    merged = merge_repaired_blocks(base, {
        "experience_blocks": [
            {"id": "not-in-plan", "bullets": ["x", "y"]},
            {"id": "e1", "company": "字节跳动", "title": "CTO",
             "bullets": [DROPPED, WEAK]},
        ],
    }, plan)
    blocks = merged["experience_blocks"]
    assert len(blocks) == 1
    assert (blocks[0]["company"], blocks[0]["title"]) == ("快手", "服务端 leader")
    assert blocks[0]["bullets"] == [DROPPED, WEAK]
    assert base == before, "merge must not mutate the draft it was given"

    # No drop to restore here, so a changed paragraph count is refused outright.
    intact = draft(bullets=[WEAK, DROPPED])
    intact_plan = plan_repair(intact, profile(), role_family="backend")
    assert intact_plan is not None and not intact_plan.blocks[0].dropped
    kept = merge_repaired_blocks(
        intact, {"experience_blocks": [{"id": "e1", "bullets": ["a", "b", "c"]}]},
        intact_plan,
    )
    assert kept["experience_blocks"][0]["bullets"] == [WEAK, DROPPED]


@pytest.mark.asyncio
async def test_a_broken_repair_never_breaks_the_preview(monkeypatch):
    """A repair is an upside. It must never be why a user sees an error or a worse draft.

    Also covers the kill switch: with the flag off there is exactly one model call and no
    repair record, so the feature can be disabled without a deploy.
    """
    from jc.services import resume_elevator as mod

    first = {"header": {"name": "测试"}, "experience_blocks": [
        {"id": "e1", "company": "快手", "title": "服务端 leader",
         "bullets": [WEAK, DROPPED]}]}
    calls: list[str] = []

    async def flaky(*_args, **kwargs):
        calls.append(getattr(kwargs.get("log_context"), "caller", ""))
        if len(calls) == 1:
            return copy.deepcopy(first)
        raise RuntimeError("gateway down")

    monkeypatch.setattr(mod, "get_llm_router", lambda: SimpleNamespace(
        acompletion=flaky, chain_for=lambda _: [object()] * 3))
    monkeypatch.setattr(mod.settings, "jc_llm_enabled", True)
    sections, _ = await ResumeElevator().build_sections(profile(), elevation_level="standard")
    assert sections["experience_blocks"][0]["bullets"] == [WEAK, DROPPED]
    assert sections["generation"]["repair"]["accepted"] is False
    assert sections["generation"]["repair"]["reason"].startswith("error:")

    router, off_calls = router_for([first])
    monkeypatch.setattr(mod, "get_llm_router", lambda: router)
    monkeypatch.setattr(mod.settings, "jc_preview_repair_enabled", False)
    off, _ = await ResumeElevator().build_sections(profile(), elevation_level="standard")
    assert off_calls == ["resume_elevator"]
    assert "repair" not in (off.get("generation") or {})


def test_placeholder_list_matches_the_service_that_writes_them():
    """`（待补充经历要点）` scores like weak prose, so counting it would make any rewrite
    look like an improvement. Two copies of the list would drift; this is cheaper than an
    import cycle."""
    from jc.services.resume_service import ResumeService

    assert set(PLACEHOLDERS) == set(ResumeService._PENDING_PLACEHOLDERS)
