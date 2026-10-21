"""A usable 200 is not the same as a successful call.

JC's notion of failure is wider than HTTP's: a gateway that returns 200 carrying
text the caller cannot parse has not answered the question. The response
validator exists so that verdict is reached *inside* litellm's call stack, where
it can move the chain to the next endpoint. A validator applied after the call
returned cannot fail over at all - it can only raise at the caller.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import fake_gateway, install_routing


@pytest.mark.asyncio
async def test_response_validator_triggers_scenario_failover(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    router = install_routing(
        monkeypatch, tmp_path, "ingest", ["openai/first", "openai/second"]
    )

    def parse(response: object) -> dict[str, bool]:
        content = router.content_from_response(response)
        if not content:
            raise ValueError("empty_model_response")
        return json.loads(content)

    with fake_gateway({"first": "", "second": '{"ok": true}'}) as called:
        result = await router.acompletion(
            "ingest", messages=[], response_validator=parse
        )

    assert result == {"ok": True}
    assert called == ["openai/first", "openai/second"]


@pytest.mark.asyncio
async def test_the_validators_result_is_returned_without_parsing_twice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A caller's parse is not required to be idempotent, so it runs once.

    The validator may consume a stream, pop a key, or count something. Running it
    again on the way out would make a second call with different results, which
    is exactly the kind of bug that only shows up under failover.
    """
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/only"])
    runs: list[str] = []

    def parse(response: object) -> dict[str, int]:
        runs.append(router.content_from_response(response))
        return {"calls": len(runs)}

    with fake_gateway({"only": '{"ok": true}'}):
        result = await router.acompletion(
            "ingest", messages=[], response_validator=parse
        )

    assert result == {"calls": 1}
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_an_unrecognised_response_shape_still_honours_the_validator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The contract is "the validator's value, or its exception" - unconditionally.

    litellm applies post-call rules only to responses it recognises, so a shape
    it skips leaves the validator unrun. Returning the unvalidated response then
    looked like a parsed result and failed at the caller's first subscript, far
    from the cause.
    """
    router = install_routing(monkeypatch, tmp_path, "ingest", ["openai/only"])

    class Unrecognised:
        """Not a ModelResponse, so litellm's post-call rules skip it."""

        choices = ()

    async def acompletion(**_: object) -> object:
        return Unrecognised()

    from jc.llm.transport import router_for

    monkeypatch.setattr(router_for("ingest").router, "acompletion", acompletion)

    with pytest.raises(ValueError, match="empty_model_response"):
        await router.acompletion(
            "ingest",
            messages=[],
            response_validator=lambda response: _reject_empty(router, response),
        )


def _reject_empty(router: object, response: object) -> dict[str, bool]:
    if not router.content_from_response(response):  # type: ignore[attr-defined]
        raise ValueError("empty_model_response")
    return {"ok": True}


def test_content_from_response_handles_missing_and_block_content(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from jc.llm.router import LLMRouter

    config = tmp_path / "routing.yaml"
    config.write_text("scenarios: {}\n", encoding="utf-8")
    router = LLMRouter(config)
    assert router.content_from_response(SimpleNamespace(choices=[])) == ""
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=[{"text": "{"}, {"text": "}"}]))]
    )
    assert router.content_from_response(response) == "{}"


@pytest.mark.asyncio
async def test_request_timeout_override_reaches_each_fallback_without_changing_shared_config(
    monkeypatch, tmp_path,
):
    import litellm

    from conftest import gateway_error
    from jc.llm.transport import router_for

    router = install_routing(monkeypatch, tmp_path, "flash", ["openai/first", "openai/second"])
    seen = []
    with fake_gateway({"first": gateway_error("timeout"), "second": "ok"}):
        gateway = litellm.acompletion

        async def capture(**kwargs):
            seen.append(kwargs.get("timeout"))
            return await gateway(**kwargs)

        # Restore the wrapper before fake_gateway restores the SDK. Otherwise
        # fixture teardown reinstalls this closed fake into the next test.
        with monkeypatch.context() as local:
            local.setattr(litellm, "acompletion", capture)
            await router.acompletion("flash", messages=[], timeout_seconds=7)
    assert len(seen) >= 2
    assert all(timeout == 7 for timeout in seen)
    assert all(
        model["litellm_params"]["timeout"] != 7
        for model in router_for("flash").router.model_list
    )
