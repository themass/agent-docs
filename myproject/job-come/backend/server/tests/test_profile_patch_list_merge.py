"""Id-bearing profile lists must merge by id, not wholesale-replace.

R3 prod: a confirm card whose patch was
  {"experiences": [{id: exp1, ...only the edited role...}]}
wiped experience 2 ("管理 5 人"). `_merge` treated lists as scalars.

Path-style edits (`experiences[0].highlights[0]`) already keep siblings; the
whole-array shape the model sometimes emits must keep them too. Omitting an
id is not a delete — silent truncation is what the user cannot see on the
confirm card.
"""

from __future__ import annotations

import pytest

from jc.exceptions import AppError
from jc.services.profile_patch_ops import apply_profile_patch


def _base() -> dict:
    return {
        "contact": {"name": "测三 R3"},
        "meta": {"source_locale": "zh-CN"},
        "experiences": [
            {
                "id": "exp_a1b2c3",
                "company": "探针科技",
                "title": "高级后端工程师",
                "start_date": "2020-05",
                "highlights": [
                    "订单查询 P99 从 820ms 降到 130ms",
                    "系统日均请求 3000 万",
                ],
            },
            {
                "id": "exp_team",
                "company": "探针科技",
                "title": "技术负责人",
                "start_date": "2018-01",
                "end_date": "2020-04",
                "highlights": ["管理 5 人团队"],
            },
        ],
        "projects": [
            {
                "id": "proj_x",
                "name": "结算中台",
                "highlights": ["拆分结算表"],
            },
            {
                "id": "proj_y",
                "name": "审核中台",
                "highlights": ["日均 2000 万条"],
            },
        ],
        "education": [
            {"id": "edu_1", "school": "清华"},
            {"id": "edu_2", "school": "北大"},
        ],
    }


def test_whole_experiences_array_with_one_id_keeps_the_other_experience():
    """R3 R1 reproduction: one-item experiences patch must not drop siblings."""
    patch = {
        "experiences": [
            {
                "id": "exp_a1b2c3",
                "company": "探针科技",
                "title": "高级后端工程师",
                "start_date": "2020-05",
                "highlights": [
                    "订单查询 P99 从 820ms 降到 110ms",
                    "系统日均请求 3000 万",
                    "主导缓存与慢查询治理",
                ],
            }
        ]
    }
    result = apply_profile_patch(_base(), patch)
    ids = [e.id for e in result.experiences]
    assert ids == ["exp_a1b2c3", "exp_team"]
    assert "110ms" in result.experiences[0].highlights[0]
    assert result.experiences[1].highlights == ["管理 5 人团队"]


def test_whole_projects_array_with_one_id_keeps_the_other_project():
    patch = {
        "projects": [
            {"id": "proj_x", "name": "结算中台", "highlights": ["拆分结算表并降延迟"]}
        ]
    }
    result = apply_profile_patch(_base(), patch)
    assert [p.id for p in result.projects] == ["proj_x", "proj_y"]
    assert result.projects[0].highlights == ["拆分结算表并降延迟"]
    assert result.projects[1].highlights == ["日均 2000 万条"]


def test_whole_education_array_with_one_id_keeps_the_other_school():
    patch = {"education": [{"id": "edu_1", "school": "清华大学"}]}
    result = apply_profile_patch(_base(), patch)
    assert [e.id for e in result.education] == ["edu_1", "edu_2"]
    assert result.education[0].school == "清华大学"
    assert result.education[1].school == "北大"


def test_path_style_edit_still_updates_one_field_without_touching_siblings():
    """Reject-side companion: the existing path form must keep working."""
    result = apply_profile_patch(
        _base(), {"experiences[0].highlights[0]": "订单查询 P99 从 820ms 降到 110ms"}
    )
    assert "110ms" in result.experiences[0].highlights[0]
    assert result.experiences[1].highlights == ["管理 5 人团队"]


def test_empty_experiences_array_is_refused_not_a_silent_wipe():
    """An empty list is not a documented delete API — refuse rather than truncate."""
    with pytest.raises(AppError) as exc:
        apply_profile_patch(_base(), {"experiences": []})
    assert exc.value.code == "invalid_profile_patch"


def test_list_item_without_id_is_refused():
    """Cannot align a nameless item against id-keyed siblings; refuse, don't guess."""
    with pytest.raises(AppError) as exc:
        apply_profile_patch(
            _base(),
            {
                "experiences": [
                    {
                        "company": "探针科技",
                        "title": "高级后端工程师",
                        "start_date": "2020-05",
                        "highlights": ["x"],
                    }
                ]
            },
        )
    assert exc.value.code == "invalid_profile_patch"
