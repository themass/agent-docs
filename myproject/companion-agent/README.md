# companion-agent

角色扮演（Her）的 agent 服务。独立部署，不与 job-come 共用代码或部署。

- 设计文档：`myandroidTest` 仓库 `weifu-refactor` 分支的 `docs/superpowers/specs/2026-11-06-roleplay-design.md`（唯一副本，本项目不复制）。
- 运行时：Python 3.12，LiveKit Agents（Apache-2.0）。
- 对话主脑：**DeerFlow**（嵌入式 harness，接管 LiveKit `Agent.llm_node`）。
- 账号与登录：复用 App 现有接口，本服务只校验凭证（待接入）。
- 语音：经 VoiceProvider 接口，第一版火山引擎（P2 接入）。

## 设计要点：agent 是核心

不是「一个能聊天的角色」，是每个用户自己的 her：懂这个人、有存在感、能替他做事、
始终是同一个「人」。所以对话只是 agent 的一个入口，不是中心。

```
触发层（Trigger）
   ↓
会话层（线程、上下文、回合状态）
   ↓
中间件链（顺序固定，见下）
   ↓
Agent 核心（DeerFlow：规划、多步、工具、子 agent、压缩）
   ↓
能力层（Skill 怎么做 / Tool 能做什么 / MCP 连什么）
   ↓
记忆层（事实 / 事件时间线 / 工作记忆）
   ↓
输出层（文字流 / 语音 / 主动推送 / 电话 / 形象指令）
```

## 目录

```
config/llm/routing.yaml   模型路由（场景 → 模型链），只引用环境变量名
characters/               角色卡（SillyTavern V2）
skills/public/            skill 包：方法论，由宿主组装进提示词
src/companion/
  trigger.py              触发归一化
  conversation.py         回合编排
  turn_pipeline.py        断句、情绪事件、取消
  container.py            装配，中间件顺序在这里定
  middleware/             安全 → 记忆召回 → 事件抽取 → 人设 → 授权 → 成本 → 观测
  brain/                  主脑接口与 DeerFlow 适配
  agent/                  LiveKit Agent，llm_node 接 DeerFlow
  actions/                动作：授权分级、确认、审计
  timeline/               事件时间线：抽取、存储（与事实记忆分开）
  proactive/              主动性：调度、策略、频控
  memory/                 MemoryPort、抽取器、mem0 与内存实现
  mcp/                    外部系统接入与工具白名单
  prompt/                 角色卡、skill 加载、分层提示词
  server/                 会话接口、token 签发、SSE 回合接口
  text/                   断句器与事件协议
  llm/                    场景路由解析
tests/                    单测，不调用真实外部服务
```

## 中间件顺序

安全 → 记忆召回 → 事件抽取 → 人设一致性 → 工具授权 → 成本 → 观测。

顺序是设计的一部分，在 `container.build_middleware_chain` 里定。安全必须最先，
成本最后（它要看到前面所有环节的用量）。漏一环是 bug，不是配置。

## 记忆分三层

- **事实**（mem0）：他是谁。语义检索，长期有效。
- **事件**（timeline）：他什么时候会发生什么。时间窗口查询，会过期、会重复。
- **工作记忆**：这次聊到哪。会话结束即释放。

分开是因为检索方式、生命周期、删除语义都不同。

## 主动性

独立子系统，不是对话里的分支。默认：重要事件提醒开、日常问候关、主动电话关。
约束：安静时段 23:00–08:00、每天 ≤ 2 次、每周 ≤ 6 次、可暂停、可退订。
判断都在 `proactive/policy.py`，原则是「没把握就不发」。

## 动作授权

| 级别 | 含义 | 例子 |
|---|---|---|
| `READ` | 只读 | `recall_facts`、`recall_events` |
| `CONFIRM` | 需用户同意 | `create_reminder` |
| `AUTO` | 自动执行，事后告知 | `remember_event` |

不可撤销的动作不允许是 `AUTO`（`ActionSpec` 构造时校验）。所有执行都进审计，
参数只存指纹不存原文。

## 接口

- `POST /companion/sessions` `{character_id}` → 房间名、LiveKit 入场 token、过期时间
- `POST /companion/turns` `{character_id, message, thread_id?, mode?}` → SSE 文本流，以 `data: [DONE]` 结束
- `GET /health`

`user_id` 不从请求体读，由凭证校验中间件注入。默认的 `AllowAllVerifier` 仅供开发。

## 本地运行

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env      # 填 LIVEKIT_* 与模型网关
PYTHONPATH=src pytest
```

## 约定

- 密钥只放环境变量，不写入代码、配置文件或文档。`.env` 不入库。
- 对话流式为默认；主脑中途失败时先交付已生成的句子再结束。
- 新增模型只改 `config/llm/routing.yaml`。
- 新增角色放 `characters/`；需要新方法论的建 skill 包，并在角色卡 `extensions.vvv.skill` 引用。
- 新增动作必须给 `ActionSpec` 定权限与可撤销性。

## 已知未完成

- DeerFlow harness 未真正接入：`DeerFlowBrain` 按 job-come 的 client 形状写了适配，没和真实 harness 对跑。需要 `agentkit`、`deerflow-harness`、`deerflow-extension-api` 三个 wheel。
- LiveKit worker 的 entrypoint 只做到配置校验，房间建立后的角色加载与事件通道待接。
- 主动性的推送通道与端上调度未接；调度器只产出触发，不发消息。
- 动作的确认流程端上未接（`CONFIRM` 目前只产出 `needs_confirmation`）。
- 事件抽取器需要真实模型才能跑；测试用 fake。
- Voice Gateway 与火山引擎适配器未实现。
- mem0 适配器按客户端接口形状写，未连过真实实例。
- 登录凭证校验是占位实现。
