#!/usr/bin/env python3
"""Her Companion Phase 0 — LiveKit 语音 + Hermes Core 记忆 + 知心姐姐 persona.

Run from hermes-dev/agents (has livekit-agents deps):

    cd hermes-dev/agents
    uv run python ../../agent-research/her-companion/companion_agent.py console

Or with dev server:

    uv run python ../../agent-research/her-companion/companion_agent.py dev
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow imports when launched as a script from hermes-dev/agents
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from livekit.agents import (  # noqa: E402
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    TurnHandlingOptions,
    cli,
    metrics,
    room_io,
    text_transforms,
)

from llm_factory import create_llm, create_stt, create_tts  # noqa: E402
from memory import build_instructions, load_hermes_core_memory  # noqa: E402
from persona import GREETING_HINT, SYSTEM_INSTRUCTIONS  # noqa: E402

logger = logging.getLogger("her-companion")

load_dotenv(_ROOT / ".env")
load_dotenv()


class CompanionAgent(Agent):
    def __init__(self) -> None:
        memory_block = load_hermes_core_memory()
        instructions = build_instructions(SYSTEM_INSTRUCTIONS, memory_block)
        super().__init__(
            instructions=instructions,
            tools=[],  # Phase 0: 无工具，保持陪伴感
        )
        if memory_block:
            logger.info("Loaded Hermes core memory (%d chars)", len(memory_block))

    async def on_enter(self) -> None:
        self.session.generate_reply(instructions=GREETING_HINT)


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=create_stt(),
        llm=create_llm(),
        tts=create_tts(),
        turn_handling=TurnHandlingOptions(
            interruption={
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.0,
            },
            preemptive_generation={"enabled": True, "max_retries": 3},
        ),
        aec_warmup_duration=3.0,
        tts_text_transforms=[
            "filter_emoji",
            "filter_markdown",
        ],
    )

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        if ev.metrics.type == "stt_metrics":
            return
        metrics.log_metrics(ev.metrics)

    await session.start(
        agent=CompanionAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(audio_input=room_io.AudioInputOptions()),
    )


if __name__ == "__main__":
    cli.run_app(server)
