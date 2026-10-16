"""Object storage naming contract tests."""

from __future__ import annotations

import pytest

from jc.storage_keys import storage_environment, storage_key


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


@pytest.mark.parametrize("segment", ["", "/", "../secret", "folder\\file"])
def test_storage_key_rejects_unsafe_path_segments(segment: str) -> None:
    with pytest.raises(ValueError):
        storage_key("profiles", segment)
