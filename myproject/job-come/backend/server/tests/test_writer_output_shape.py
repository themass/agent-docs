"""Writer output that arrives the wrong shape must not reach the renderer.

The writer is a model call. Every guard upstream of the template assumes a list of dicts
with a string `id` and a list of string `bullets`, and a model that returns anything else
used to be rendered as an empty block: a job silently disappeared from the document with
no error, which is indistinguishable from the user never having written it.

The invariant these tests pin is not "coerce everything". It is: **either the block is
usable, or it is dropped where the coverage check can see the loss.** Coercing a string id
into a dict key would invent an identity; keeping a non-dict would crash the renderer.
"""

from __future__ import annotations

from jc.services.resume_elevator import ResumeElevator

_normalize = ResumeElevator._normalize_sections


def test_a_string_bullet_becomes_a_one_element_list():
    """A model that answers `bullets: "主导了订单重构"` means one bullet. Iterating the
    string would split it into characters and render a column of single glyphs."""
    out = _normalize({"experience_blocks": [{"id": "e1", "bullets": "主导了订单重构"}]})
    assert out["experience_blocks"][0]["bullets"] == ["主导了订单重构"]


def test_entries_that_are_not_dicts_are_dropped_not_rendered():
    out = _normalize(
        {
            "experience_blocks": [
                {"id": "e1", "bullets": ["ok"]},
                "主导了订单重构",  # a bare sentence where a block was expected
                None,
                42,
            ]
        }
    )
    assert [b["id"] for b in out["experience_blocks"]] == ["e1"]


def test_a_block_without_a_usable_id_is_dropped():
    """The id is the diff key: without it the block cannot be attributed to a source
    entity, so keeping it would ship an unattributable job."""
    out = _normalize(
        {
            "experience_blocks": [
                {"company": "某公司", "bullets": ["没有 id"]},
                {"id": "", "bullets": ["空 id"]},
                {"id": 7, "bullets": ["数字 id"]},
                {"id": "e1", "bullets": ["正常"]},
            ]
        }
    )
    assert [b["id"] for b in out["experience_blocks"]] == ["e1"]


def test_missing_or_null_collections_become_empty_lists():
    """The renderer iterates these directly; `None` there is a TypeError, and an absent
    key is a KeyError depending on the template."""
    out = _normalize({"experience_blocks": None, "project_blocks": {"id": "p1"}})
    assert out["experience_blocks"] == []
    assert out["project_blocks"] == []


def test_non_list_bullets_do_not_crash_and_do_not_invent_content():
    out = _normalize(
        {
            "experience_blocks": [
                {"id": "e1", "bullets": None},
                {"id": "e2", "bullets": 3},
            ]
        }
    )
    assert out["experience_blocks"][0]["bullets"] == []
    assert out["experience_blocks"][1]["bullets"] == []


def test_the_well_formed_path_is_untouched():
    """The normalizer must not be a lossy filter on correct input — this is the case that
    would break every existing draft if the helper were too eager.

    Compares the fields that carry content. `scope_line` is normalised separately (and
    legitimately set to None when absent), so comparing whole dicts here would pin an
    unrelated behaviour and fail the day scope-line handling changes for its own reasons.
    """
    out = _normalize(
        {
            "experience_blocks": [
                {"id": "e1", "company": "A", "bullets": ["要点一", "要点二"]},
                {"id": "e2", "company": "B", "bullets": []},
            ]
        }
    )
    assert [(b["id"], b["company"], b["bullets"]) for b in out["experience_blocks"]] == [
        ("e1", "A", ["要点一", "要点二"]),
        ("e2", "B", []),
    ]
