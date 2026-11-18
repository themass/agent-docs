# 剧本房推流器设计（2026-11-19）

## Intent / Why

真机语音通话受 LiveKit 卡顿与上行收音影响，端侧经常「听不到 / 收不到」，P0.5/P2 对账也因此拖住。需要一条**不依赖用户说话、不依赖 STT** 的验证路径：手机进一个剧本房间，服务端按 case 推协议 + TTS 音轨，人眼/耳确认字幕、情绪、打断停口；同一套 case 也能在 CI 里离线断言。以后换 RTC 时，只换推流适配层，case 与协议时序不变。

## Goals

1. YAML case 描述「用户意图 → 期望协议序列 → 可选 TTS 文本」；pytest 离线跑通断言。
2. 独立进程（剧本推流器）进真房间：假脑剧本 + 真/假 TTS + `SpeechPublisher` / `cue_emotion` / `control.cancel`，手机进房能听能看。
3. 支持「先真 LLM 验收 case 文本，再固化为剧本」两阶段；真 LLM 阶段产出可落成 YAML。
4. RTC 细节隔离在适配层（先 LiveKit `publish_data` + 音频轨），换框架只换适配。

## Non-goals

- 不替代线上 voice worker；不改现网 entrypoint 默认路径。
- 不做完整 AgentSession / VAD / STT 仿真。
- 不在本设计里实现新 RTC；只保证推流接口可替换。
- 不解决生产 prewarm / 记忆超时（另案）。

## Anti-goals

- 手机必须说话才能测 —— 失败。
- case 写死 LiveKit Agents API —— 失败（换 RTC 成本会回来）。
- 只有假 Bridge 断言、手机永远看不到 —— 对本需求失败（用户明确要「进剧本房」且「听到」）。

## Constraints

- 复用现有 `ProtocolBridge` / `SpeechPublisher` / `CueCompiler` / `FakeBrain` / `FakeVoiceProvider`（及生产火山 TTS）。
- 协议时序仍遵守 §13：先 `speech.seg`，再 cue / 音频；打断发 `control.cancel`。
- 生产写操作仍走既有发布流程；剧本推流器默认连测试/可配置 LiveKit，不误伤生产房间命名。
- 手机侧用现有 chat flavor 进房（同一套协议消费路径）。

## Approaches（已选）

| 方案 | 要点 | 取舍 |
|---|---|---|
| **A. 独立剧本推流器（选定）** | 单独进程按 case 进房；假脑 + TTS + 协议推流；YAML 共用 pytest | 与 voice worker 解耦，换 RTC 只换适配；多一个进程 |
| B. voice worker 剧本模式 | metadata 标 script，entrypoint 换 FakeBrain | 改动面小，但仍绑 Agents 与上行路径 |
| C. 仅离线假 Bridge | 最快绿断言 | 手机看不到/听不到，不满足本需求 |

选定 A：验收消费者是「手机进剧本房」，且要听到说话；A 是唯一同时满足解耦与听感的路径。

## How it works

### Case 格式（示意）

```yaml
id: barge_mid_sentence
goal: 她说到一半被打断，端侧应收到 cancel 并停口
steps:
  - user: "今天真累。"           # 真 LLM 阶段的输入；剧本阶段可省略
  - expect_reply:                 # 固化后的假脑输出
      - "听到了。[soft]累了就先歇会儿吧。"
  - protocol:
      - speech.seg
      - presentation.emotion      # soft → emotion
      - speech.seg                # 第二句
  - inject: barge_in              # 推流器在第二句音频中途注入（模拟端侧）
  - protocol:
      - control.cancel
audios: synthesize                # synthesize | fixture:<wav> | none
```

### 两阶段

1. **真 LLM 验收**：`tools/script_cases.py capture --case …` 调真实脑，打印 reply + 协议意图；人确认后 `--freeze` 写入 YAML 的 `expect_reply`。
2. **剧本推房**：`tools/script_room.py run --case barge_mid_sentence`（或一批）建房 → 发 agent token → 推流器进房 → 假脑吐句 → SpeechPublisher + TTS 出音 → 按 step 注入 barge → 结束打印协议时间线。手机用现有会话入口进同一房间（或推流器打印 join 二维码/deep link；**builder 可先用 token+room 手动进**）。

### 架构

```
YAML case
   │
   ├─ pytest：FakeBridge 录序 → 断言 protocol 列表
   │
   └─ ScriptRoomRunner
         ├─ Brain: FakeBrain(script) 或 DeerFlow（capture 阶段）
         ├─ SpeechPublisher(ProtocolBridge)
         ├─ CueCompiler → presentation.*
         ├─ Tts: Volcengine 或 FakeVoiceProvider（可听 vs 确定性）
         └─ RtcAdapter（接口）
               └─ LiveKitAdapter: connect / publish_data / publish_audio
```

`RtcAdapter` 最小方法：`connect(url, token)`、`publish_data(topic, bytes)`、`publish_pcm(frames, rate)`、`close()`。LiveKit 实现放在 `companion/devtools/script_room/`（或 `tools/` 旁包），**不** import 进生产 entrypoint。

### 手机怎么进

- 推流器创建房间名 `script-<case>-<shortid>`，mint 用户 token + agent token。
- **Agent token 必须带 LiveKit JWT `kind=agent`**（`AccessToken.with_kind`）。端侧 `CompanionProtocolLink` 只消费 `Participant.Kind.AGENT` 的 data；仅 identity=`agent:…` 不够——会「听得到 PCM、看不到字幕/emotion/cancel」。剧本路径要么扩展 `TokenMinter.agent_token`，要么在 script-room 包内单独 mint；**不**为剧本房弱化端侧 AGENT 门闩。
- **进房凭证（已定）**：加轻量 **script session 入口**（shim / 专用 createSession）：房间名 `script-*`，返回现有 `SessionResponse`（url / room / user token）。手机仍走 chat flavor 正常进房路径，**不改**端侧 debug UI；改动主要在 companion-agent。推流器侧 mint agent token（`kind=agent`）进同一房间推流。
- 不要求用户开口；麦可关。

### 开推门槛（builder 已定）

- 等远端参与者进房 **且** `control.hello` 握手完成（bridge 可发 speech）后再推首条 `speech.seg`；超时失败并打印时间线。避免「脚本跑完了手机才进」。

### `inject: barge_in`（builder 已定）

- 推流器**不**依赖 AgentSession / `BargeInRelay`：在第二句音频中途（默认估时一半或 N 帧 PCM，可配置）**停掉 PCM 发布循环**，并经 `SpeechPublisher.cancel`（或等价）发 `control.cancel`，让手机听到停口并看到 cancel。
- 这是「模拟端侧打断后的服务端效果」，不是端到端 `control.barge_in` 协议联调；后者仍归真机 P2。

### 听感

- 默认 `audios: synthesize`：独立进程走 `VolcengineProvider` + `RtcAdapter.publish_pcm`（与现网同音色配置；采样率按 provider 默认，不绑 Agents `tts_node` / `NewConsoleTTS`，方便换 RTC）。
- CI / 无密钥环境用 `FakeVoiceProvider` 或预录 wav fixture（听感弱，但协议仍可验）。
- 音频与 `speech.seg` 对齐：先 seg，再按段喂 TTS PCM。

## Builder 可自行决定

- YAML 字段精确 schema、目录 `server/cases/voice/*.yaml`。
- 手机 deep link 是否本迭代做（可先 CLI token）。
- 首批 case 数量（建议先 4：问候+emotion、多句 seg/end、中途 barge、超长截断）。
- pytest 放 `tests/test_script_cases.py` 还是 `tests/script_room/`。

## Success

- `pytest` 对首批 case 全绿（假 Bridge）。
- 本机/测试 LiveKit：跑 `script_room.py`，手机进房能听到至少两句，并在 barge case 听到中途停口；logcat 有对应 `speech_*` / `speech_cancel` / emotion（若 case 含）。
- 换 RTC 时无需改 YAML。
