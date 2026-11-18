# Script Room Pusher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an independent script-room pusher that drives YAML voice cases (protocol + TTS audio) into a LiveKit room so a phone can join, hear her, and see captions/emotion/cancel — without user speech or STT — while the same cases assert offline in pytest.

**Architecture:** YAML cases feed an offline runner (FakeBrain + SpeechPublisher + CueCompiler + recording bridge) and a live `ScriptRoomRunner` (same protocol path + VolcengineProvider PCM via `RtcAdapter`). Phone gets a normal `SessionResponse` from `POST /v1/voice/script-sessions` for room `script-{case}-{id}`; pusher joins the same room with an agent JWT (`kind=agent`). No AgentSession / VAD / STT.

**Tech Stack:** Python 3 / pytest / PyYAML, existing companion `SpeechPublisher` / `ProtocolBridge` / `CueCompiler` / `FakeBrain` / `FakeVoiceProvider` / `VolcengineProvider` / `TokenMinter`, LiveKit RTC SDK for the adapter only, Redis for cross-process room lease, FastAPI session shim, minimal Android `CompanionApi` glue.

**Spec:** `docs/superpowers/specs/2026-11-19-script-room-pusher-design.md`

## Global Constraints

- Do not change production voice worker entrypoint defaults; script-room code must not be imported from production agent entry.
- Room names for this feature always match `^script-` (never `companion-`).
- Protocol order stays §13: `speech.seg` before cue/audio; barge emits `control.cancel` and stops PCM.
- Agent token must set LiveKit participant kind so Android `CompanionProtocolLink` accepts data (`Participant.Kind.AGENT`).
- Do not weaken the client AGENT gate for script rooms.
- `inject: barge_in` is pusher-local (stop PCM + `SpeechPublisher.cancel`); it is not end-to-end `control.barge_in` P2 proof.

## Review Focus

- Phone joins after the script already finished waiting — runner must fail closed with a timeline, not silently no-op captions.
- Agent JWT missing `kind=agent` — phone hears PCM but drops all data events.
- Barge stops protocol cancel but PCM keeps publishing — phone keeps hearing her.
- Hello never arrives (legacy path) — decide fail vs v1 fallback; script rooms require v2 hello.
- Case YAML `expect_reply` text with `[soft]` — emotion cue must appear in recorded protocol when caps allow.

## File map

| Path | Role |
|---|---|
| `server/cases/voice/*.yaml` | First four cases |
| `server/src/companion/devtools/script_room/case_schema.py` | Load/validate YAML |
| `server/src/companion/devtools/script_room/offline_runner.py` | Drive case → FakeBridge timeline |
| `server/src/companion/devtools/script_room/rtc.py` | `RtcAdapter` Protocol + `LiveKitRtcAdapter` |
| `server/src/companion/devtools/script_room/runner.py` | Live `ScriptRoomRunner` |
| `server/src/companion/devtools/script_room/lease.py` | Redis (or memory) room lease by `case_id` |
| `server/tools/script_room.py` | CLI `run` |
| `server/tools/script_cases.py` | CLI `capture` / `freeze` (Task 7) |
| `server/src/companion/service/room/livekit_tokens.py` | `agent_token` + `kind=agent` claim |
| `server/src/companion/service/room/sessions.py` | `create_script(...)` grant helper |
| `server/src/companion/api/livekit/sessions_router.py` | `POST /v1/voice/script-sessions` |
| `server/tests/test_script_cases.py` | Offline case assertions |
| `server/tests/test_script_session_api.py` | Script session HTTP |
| `server/tests/test_token_kind.py` | Agent kind claim |
| Android `CompanionApi.kt` / `CompanionViewModel.kt` | Tiny glue to call script-sessions |

---

### Task 1: Case schema + first YAML cases + offline protocol runner

**Files:**
- Create: `server/src/companion/devtools/script_room/__init__.py`
- Create: `server/src/companion/devtools/script_room/case_schema.py`
- Create: `server/src/companion/devtools/script_room/offline_runner.py`
- Create: `server/cases/voice/greet_emotion.yaml`
- Create: `server/cases/voice/multi_seg.yaml`
- Create: `server/cases/voice/barge_mid_sentence.yaml`
- Create: `server/cases/voice/truncation.yaml`
- Test: `server/tests/test_script_cases.py`

**Interfaces:**
- Produces: `load_case(path: Path) -> ScriptCase`
- Produces: `ScriptCase(id: str, goal: str, steps: list[Step], audios: str)`
- Produces: `async def run_offline(case: ScriptCase) -> list[str]` returning event type names in order (e.g. `speech.seg`, `presentation.emotion`, `speech.seg`, `control.cancel`, `speech.end` as applicable)
- Consumes: `FakeBrain`, `SpeechPublisher`, `compile_cues`, `try_parse_fragment` / tag strip, recording bridge shaped like `_FakeBridge` in `test_speech_publisher.py` plus `cue_emotion` / `publish` recording for presentation events

- [ ] **Step 1: Write failing tests for loader + barge case timeline**

```python
def test_load_barge_case_roundtrip():
    case = load_case(CASES / "barge_mid_sentence.yaml")
    assert case.id == "barge_mid_sentence"
    assert case.audios == "synthesize"

async def test_offline_barge_case_emits_seg_emotion_seg_cancel():
    types = await run_offline(load_case(CASES / "barge_mid_sentence.yaml"))
    assert types == [
        "speech.seg",
        "presentation.emotion",
        "speech.seg",
        "control.cancel",
    ]
```

(Also assert `greet_emotion` ends with `speech.end` and includes `presentation.emotion`; `multi_seg` has ≥2 `speech.seg` then `speech.end`; `truncation` respects `MAX_SEGMENTS` and still finishes.)

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

Run: `cd server && uv run pytest tests/test_script_cases.py -v`
Expected: FAIL import / not found

- [ ] **Step 3: Implement schema, four YAMLs, offline runner**

YAML shape matches the spec example. Offline runner: for each `expect_reply` line, `SpeechPublisher.say` → parse fragment/tags → `compile_cues` → record emotion publishes → on `inject: barge_in` call `SpeechPublisher.cancel` instead of continuing audio (offline has no PCM). Map bridge calls to event type strings. Do not import LiveKit.

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd server && uv run pytest tests/test_script_cases.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/cases/voice server/src/companion/devtools/script_room server/tests/test_script_cases.py
git commit -m "feat(script-room): YAML cases + offline protocol runner"
```

---

### Task 2: Agent token `kind=agent`

**Files:**
- Modify: `server/src/companion/service/room/livekit_tokens.py` (`TokenMinter.agent_token` / `_mint`)
- Test: `server/tests/test_token_kind.py`

**Interfaces:**
- Consumes: existing `TokenMinter._mint` JWT claims
- Produces: `agent_token(...)` JWTs that include LiveKit participant kind agent (claim field per current LiveKit JWT rules — verify against installed `livekit-api` / docs; raw HS256 mint must set the same field the SFU honors so `RemoteParticipant.kind == AGENT`)

- [ ] **Step 1: Write failing test**

```python
def test_agent_token_jwt_carries_agent_kind():
    minter = TokenMinter(api_key="key", api_secret="secret", ttl_sec=60)
    tok = minter.agent_token("a1", "script-demo")
    claims = decode_jwt_unverified(tok.token)  # use existing test helper or PyJWT without verify aud
    assert claims.get("kind") == "agent"  # adjust key if LiveKit uses nested grant; assert the real field

def test_user_token_jwt_does_not_force_agent_kind():
    minter = TokenMinter(api_key="key", api_secret="secret", ttl_sec=60)
    tok = minter.user_token("u1", "script-demo")
    claims = decode_jwt_unverified(tok.token)
    assert claims.get("kind") in (None, "standard", "")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd server && uv run pytest tests/test_token_kind.py -v`

- [ ] **Step 3: Extend `_mint` / `agent_token` to set kind for agents only**

Keep hand-rolled JWT; do not require livekit-api at mint time if the project already avoids that dependency in tokens module.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add server/src/companion/service/room/livekit_tokens.py server/tests/test_token_kind.py
git commit -m "fix(tokens): agent JWT sets LiveKit kind=agent"
```

---

### Task 3: Script session grant + HTTP + room lease

**Files:**
- Modify: `server/src/companion/service/room/sessions.py` — add `SCRIPT_ROOM_PREFIX = "script-"`, `script_room_name_for(case_id, short_id)`, `SessionService.create_script(...)`
- Create: `server/src/companion/devtools/script_room/lease.py` — `ScriptRoomLease` (`async def attach(case_id) -> str` room name; Redis implementation + in-memory for tests)
- Modify: `server/src/companion/api/livekit/sessions_router.py` — `POST /v1/voice/script-sessions`
- Wire lease/redis in existing app bootstrap (same place voice router is built)
- Test: `server/tests/test_script_session_api.py`

**Interfaces:**
- Produces: `SessionService.create_script(*, user_id, character_id, case_id, chat_session_id=None) -> SessionGrant` with `room_name` starting with `script-`
- Produces: HTTP body `{character_id, case_id}` → existing `SessionResponse` shape
- Produces: `ScriptRoomLease.attach(case_id) -> room_name` (idempotent per case until TTL)
- Constraint: must **not** dispatch the production LiveKit agent job for these rooms

- [ ] **Step 1: Write failing API tests**

```python
async def test_script_session_returns_script_room_prefix(client):
    r = await client.post("/v1/voice/script-sessions", json={"character_id": "linche", "case_id": "barge_mid_sentence"})
    assert r.status_code == 200
    body = r.json()
    assert body["room_name"].startswith("script-")
    assert body["token"] and body["livekit_url"]

async def test_script_session_same_case_reuses_room(client):
    a = (await client.post(...)).json()["room_name"]
    b = (await client.post(...)).json()["room_name"]
    assert a == b
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement lease + `create_script` + route; skip agent dispatch**

Phone and CLI both call `lease.attach(case_id)` so they land in one room regardless of order.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(voice): script-sessions endpoint + script room lease"
```

---

### Task 4: `RtcAdapter` + LiveKit implementation

**Files:**
- Create: `server/src/companion/devtools/script_room/rtc.py`
- Test: `server/tests/test_script_rtc_adapter.py` (fake in-memory adapter behavior; LiveKit adapter smoke mocked)

**Interfaces:**
- Produces:

```python
class RtcAdapter(Protocol):
    async def connect(self, url: str, token: str) -> None: ...
    async def publish_data(self, topic: str, payload: bytes) -> None: ...
    async def publish_pcm(self, frame: bytes, *, sample_rate: int) -> None: ...
    async def wait_for_remote_participant(self, *, timeout: float) -> None: ...
    async def close(self) -> None: ...
```

- Produces: `LiveKitRtcAdapter` implementing the above via LiveKit room connect / local participant publish (data + audio track). Keep all livekit imports inside this module.
- Produces: `MemoryRtcAdapter` for unit tests recording `publish_data` / `publish_pcm` calls and supporting a test hook to simulate remote join.

- [ ] **Step 1: Write failing tests for MemoryRtcAdapter record/order + wait timeout**

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement Protocol + Memory + LiveKit adapters**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(script-room): RtcAdapter + LiveKit/memory implementations"
```

---

### Task 5: Live `ScriptRoomRunner` (hello gate, TTS, barge stop)

**Files:**
- Create: `server/src/companion/devtools/script_room/runner.py`
- Create: `server/src/companion/devtools/script_room/bridge_over_rtc.py` — thin `ProtocolBridge`-compatible publisher that sends via `RtcAdapter.publish_data` on ctl/cue topics (reuse encode/envelope helpers; or wrap a real `ProtocolBridge` if a room handle can be faked — prefer small bridge that only implements the methods `SpeechPublisher` + cue publish need, plus hello handling inbound)
- Test: `server/tests/test_script_room_runner.py`

**Interfaces:**
- Consumes: `ScriptCase`, `RtcAdapter`, `TokenMinter.agent_token`, TTS provider Protocol (`tts(text) -> async iter AudioChunk`), `SpeechPublisher`, cue compile path from Task 1
- Produces: `async def run_script_room(*, case, url, token, tts, wait_timeout_sec=60) -> list[str]` timeline
- Behavior:
  1. `connect` → wait remote participant → process/wait `control.hello` (fail if timeout; **no** silent v1 for script rooms)
  2. For each reply line: `say` → cues → synthesize/publish PCM (unless `audios: none`)
  3. On `inject: barge_in`: after ~half of current segment PCM (use `estimate_ms` or N frames), stop PCM loop + `SpeechPublisher.cancel`
  4. Otherwise `finish` → `speech.end`
  5. Return timeline event types

- [ ] **Step 1: Write failing tests with MemoryRtcAdapter + FakeVoiceProvider**

```python
async def test_runner_waits_for_hello_before_first_seg():
    # remote join without hello → timeout error, timeline empty / no speech.seg

async def test_runner_barge_stops_pcm_and_emits_cancel():
    # after hello, barge case → timeline includes control.cancel; pcm byte count < full utterance
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement runner + rtc-backed bridge**

Default TTS in tests: `FakeVoiceProvider`. Production CLI will pass `VolcengineProvider`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(script-room): ScriptRoomRunner with hello gate and barge stop"
```

---

### Task 6: CLI `script_room.py` + minimal Android glue

**Files:**
- Create: `server/tools/script_room.py`
- Modify (Android, minimal): `feature-companion/.../CompanionApi.kt` — `createScriptSession(characterId, caseId)` → `POST /v1/voice/script-sessions`
- Modify: `CompanionViewModel.kt` (or call site) — one entry that uses script session when `caseId` provided (build/debug flag or method overload is fine; **no** paste-token UI)
- Test: extend `HttpCompanionApiTest` for new path; server CLI smoke as documented manual step

**Interfaces:**
- CLI: `uv run python -m tools.script_room run --case barge_mid_sentence [--url ...] [--tts volcengine|fake]`
  - `lease.attach(case)` → mint agent token → `run_script_room`
  - Print room name + “phone: createScriptSession(case)” and final timeline
- Android: same `SessionResponse` → existing `connect` / protocol path

- [ ] **Step 1: Write failing Android API unit test for `/v1/voice/script-sessions`**

- [ ] **Step 2: Implement API + ViewModel/debug entry; implement CLI**

- [ ] **Step 3: Manual verify checklist (not automated)**
  - Start CLI case `multi_seg` with fake or volc TTS against test LiveKit
  - Phone createScriptSession → join → hear ≥2 sentences; logcat shows speech path
  - CLI case `barge_mid_sentence` → hear mid-stop; logcat `speech_cancel`

- [ ] **Step 4: Commit server + Android separately if repos differ**

```bash
# agent-docs / companion-agent
git commit -m "feat(script-room): CLI runner"
# myandroidTest
git commit -m "feat(companion): createScriptSession API glue"
```

---

### Task 7: Capture / freeze true-LLM case texts

**Files:**
- Create: `server/tools/script_cases.py`
- Modify: case YAMLs only when freezing
- Test: `server/tests/test_script_cases_capture.py` (fake brain only — assert freeze writes `expect_reply`)

**Interfaces:**
- `capture --case greet_emotion` runs brain once, prints reply lines + intended protocol
- `freeze --case … --from capture.json` writes `expect_reply` into YAML
- Default brain in tests: `FakeBrain`; real DeerFlow wired only when env/credentials present

- [ ] **Step 1: Failing test that freeze updates expect_reply**

- [ ] **Step 2: Implement capture/freeze**

- [ ] **Step 3: pytest PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(script-room): capture/freeze case replies"
```

---

## Self-review notes

- Spec goals 1–4 covered by Tasks 1, 3–6 (RTC adapter), 5–6 (phone hear), 7 (LLM freeze).
- Non-goal “no AgentSession” respected: runner uses SpeechPublisher + RtcAdapter only.
- Review Focus items pinned in Tasks 2, 5 tests.
- Android change is glue only (no paste-token UI), matching approved design.
