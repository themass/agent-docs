"""The same model-output boundary must protect text and vision ingestion."""
import json

import pytest

from jc.services.profile_structurer import ProfileStructureError


def validate(data):
    from jc.services.profile_ingest_contract import validate_profile_content
    return validate_profile_content(json.dumps(data), source_file="resume.pdf")


def test_unknown_title_is_reviewable_but_ids_are_never_blank():
    profile = validate({"experiences": [
        {"company": "Company", "title": None, "start_date": "2020-01", "confidence": "confirmed"},
        {"id": "", "company": "Other", "title": "Dev", "start_date": "2021-01"},
    ]})
    assert profile.experiences[0].title == ""
    assert profile.experiences[0].confidence == "needs_review"
    assert all(e.id for e in profile.experiences)
    assert len({e.id for e in profile.experiences}) == 2


def test_null_default_collections_do_not_erase_facts_or_invent_content():
    profile = validate({"contact": {"name": "Candidate", "links": None}, "education": None,
                        "experiences": [{"company": "Company", "title": "Dev", "start_date": None,
                                         "highlights": None}], "meta": None})
    assert profile.contact.name == "Candidate"
    assert profile.education == []
    assert profile.experiences[0].start_date == ""
    assert profile.experiences[0].highlights == []
    assert profile.meta.source_file == "resume.pdf"


@pytest.mark.parametrize("data", [{}, {"experiences": [{"company": None, "title": None}]},
                                  {"skills": [{"name": ""}]}])
def test_empty_entities_are_not_source_facts(data):
    with pytest.raises(ProfileStructureError, match="empty_profile_response"):
        validate(data)


def test_wrong_types_are_not_coerced_into_fake_facts():
    with pytest.raises(ProfileStructureError, match="invalid_profile_schema"):
        validate({"experiences": [{"company": {"private": "secret"}}]})


def test_existing_facts_and_input_remain_unchanged():
    import copy
    data = {"experiences": [{"id": "stable", "company": "Company", "title": None,
                              "start_date": "2020-01", "highlights": ["25 days → 8 days", "4kw"]}]}
    original = copy.deepcopy(data)
    result = validate(data)
    assert result.experiences[0].id == "stable"
    assert result.experiences[0].highlights == original["experiences"][0]["highlights"]
    assert data == original
