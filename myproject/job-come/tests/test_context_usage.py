"""Context token buckets from real prompt usage."""

from jobcome.agent.context_usage import allocate_buckets, build_context_usage_event


def test_allocate_scales_overhead_on_short_prompt() -> None:
    buckets = allocate_buckets(prompt_tokens=1_000)
    used = sum(b["tokens"] for b in buckets if b["id"] != "conversation")
    conversation = next(b["tokens"] for b in buckets if b["id"] == "conversation")
    assert conversation == 0
    assert used == 1_000


def test_allocate_conversation_is_remainder() -> None:
    buckets = allocate_buckets(prompt_tokens=20_000)
    conversation = next(b["tokens"] for b in buckets if b["id"] == "conversation")
    assert conversation == 20_000 - (800 + 4_500 + 2_200 + 900)
    assert sum(b["tokens"] for b in buckets) == 20_000


def test_context_usage_event_not_estimated_when_prompt_present() -> None:
    event = build_context_usage_event(
        prompt_tokens=8_000,
        completion_tokens=200,
        total_tokens=8_200,
        limit_tokens=200_000,
    )
    assert event["type"] == "context_usage"
    assert event["estimated"] is False
    assert event["limit_tokens"] == 200_000
    assert event["actual"]["prompt_tokens"] == 8_000
    assert 0 < event["percent"] < 10
