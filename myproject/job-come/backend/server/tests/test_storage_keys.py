"""Object storage naming contract tests."""

from __future__ import annotations

import pytest

from jc.storage_keys import profile_id_and_kind_from_key, storage_environment, storage_key


def test_storage_key_uses_jc_prefix_and_canonical_development_environment(monkeypatch) -> None:
    from jc import storage_keys

    monkeypatch.setattr(storage_keys.settings, "jc_env", "development")
    assert storage_environment() == "dev"
    assert (
        storage_key("profiles", "prof_test", "source", "psrc_test.pdf")
        == "jc/dev/profiles/prof_test/source/psrc_test.pdf"
    )


def test_storage_key_uses_production_environment(monkeypatch) -> None:
    from jc import storage_keys

    monkeypatch.setattr(storage_keys.settings, "jc_env", "production")
    assert storage_key("profiles", "prof_test", "export", "exp_test.docx") == (
        "jc/prod/profiles/prof_test/export/exp_test.docx"
    )


@pytest.mark.parametrize("segment", ["../escape", "..", ""])
def test_storage_key_rejects_unsafe_path_segments(segment: str) -> None:
    with pytest.raises(ValueError):
        storage_key("profiles", segment)


def test_profile_id_and_kind_from_export_key() -> None:
    key = "jc/dev/profiles/prof_abc/export/expj_1.pdf"
    assert profile_id_and_kind_from_key(key) == ("prof_abc", "export")


def test_profile_id_and_kind_from_singular_photo_key() -> None:
    key = "jc/dev/profile/prof_abc/photo/headshot.jpg"
    assert profile_id_and_kind_from_key(key) == ("prof_abc", "photo")


def test_profile_id_and_kind_rejects_source_uploads() -> None:
    key = "jc/dev/profiles/prof_abc/source/psrc_1.pdf"
    assert profile_id_and_kind_from_key(key) is None


def test_profile_id_and_kind_rejects_traversal() -> None:
    assert profile_id_and_kind_from_key("jc/dev/profiles/../admin/secret") is None
