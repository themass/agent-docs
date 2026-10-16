"""API startup must survive non-critical stale-job recovery failures."""

from fastapi.testclient import TestClient


def test_health_starts_when_stale_profile_recovery_is_unavailable(monkeypatch) -> None:
    import jc.tasks

    async def unavailable() -> None:
        raise OSError("database DNS unavailable")

    monkeypatch.setattr(jc.tasks, "recover_stale_profile_parses", unavailable)
    # Import after patching so the lifespan imports the patched task implementation.
    from jc.main import app

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
