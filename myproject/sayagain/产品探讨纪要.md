# SayAgain 等产品探讨纪要

> **性质**：产品方向闲聊与决策记录（非正式 PRD）  
> **整理日期**：2026-10-12  
> **对话时段**：约 2026-08 ~ 2026-09（Cursor Agent 会话整理）  
> **正式规格**：以 [`agent-research/SAYAGAIN.md`](../../../agent-research/SAYAGAIN.md) 为准；本文件保留讨论过程与取舍理由。

---

## 1. 背景：怎么走到 SayAgain

### 1.1 从「赚钱开源 / 产品形态」出发

在 monorepo 与历史会话里梳理过多条产品线（Her Companion、英语跟读、Chrome DOM+Network Agent、Play「小而美」调研等）。结合 GitHub 上「make money」类开源项目的共性：

| 类型 | 代表方向 | 对个人开发者适配 |
|------|----------|------------------|
| 内容自动化 | 发文、剪辑 | 运营重、合规风险 |
| 交易 / Agent | 量化、自动化 | 门槛与监管 |
| B2B 自动化 | 工作流 | 销售周期长 |
| **C 端 App** | 订阅、习惯闭环 | **相对适合 solo，与 Play 小而美一致** |

**结论**：优先做 **C 端 App**，第一个落地品选 **英语跟读 + 纠错（shadowing）**。

### 1.2 产品命名与文档

- 产品名：**SayAgain**（副标题：再说一遍，就知道哪里错；Slogan：*Say it again. Know what's off.*）
- 曾用名 EchoRead，已统一为 SayAgain
- 产品说明已合并为单文件：`agent-research/SAYAGAIN.md`
- Phase 0 代码：`agent-research/english-shadowing/`（`python3 self_check.py` 可回归）

---

## 2. 对话纪要（按议题）

### 2.1 定位纠偏：目标用户应是东南亚 + 中东

**用户观点**：当前文档里「面向中文用户练英语」的定位不对；**中东、东南亚**才是更真实的目标用户。

**讨论结论**：

- 仓库内 **无独家市场调研**；采用公开数据（EF EPI 2025、Antom、Meticulous Research、竞品在当地的打法）做 **v1 定位校准**。
- **废弃**：以中国大陆用户为主、小红书获客、中英教练为默认的假设。
- **确立**：
  - 首发市场：**印尼、越南、沙特、阿联酋**（P0/P1）
  - 教练语言：**英语 + 本地语**（`coach.en` + `coach.local`），v1 优先 **id / vi / ar**
  - 定价：**$2.99–3.99/月** + Play 区域定价（对标 ELSA 在当地的「好用但贵」）
  - 课程场景：餐厅/酒店、工厂报工、客服话术等，强于「留学面试」叙事
  - 获客：TikTok/Reels、当地 FB 群、ASO 本地语关键词

**市场信号摘要**（公开来源，供回溯）：

| 信号 | 要点 |
|------|------|
| 东南亚在线语言学习 | 约 $13 亿（2023），CAGR ~20%（Antom） |
| 人口与设备 | ~7 亿人口，60%+ 未满 35 岁，手机为主 |
| 口语短板 | EF EPI 2025：印尼 #80、越南 #64、沙特 #115、泰国 #116 |
| 竞品 | ELSA 在印尼/越南重度本地化；Play 评论常见 Premium 太贵 |
| 楔子 | 更轻、更便宜、句级漏词反馈可解释，非音素实验室 |

上述结论已写回 `agent-research/SAYAGAIN.md` §1、§3、§4 等。

---

### 2.2 DeepTutor 能否作为产品底座？

**用户问题**：`DeepTutor/deeptutor` 是否适合本英语类产品？

**结论**：**不适合作为 SayAgain 主技术栈或 v1 产品底座**。

| 维度 | SayAgain | DeepTutor（HKUDS） |
|------|----------|-------------------|
| 形态 | Android + Google Play | Web / CLI / WebSocket / IM |
| 闭环 | 听 → 跟读 → ASR → 句级对齐 → 再练 | 多轮 Agent + RAG/KB + Capability |
| 语音 | ASR + 跟读是主路径 | 架构文档无 speech 主路径 |
| 用户 | SEA/MENA C 端 | 通用 AI 辅导平台 |

**可借鉴（非 fork）**：Mastery/SM-2 调度、Capability 插件思路、Prompt 外置与 i18n、Turn 可观测性。

**本仓库**：`DeepTutor/` 几乎无完整 checkout；详见 `docs/deeptutor-architecture/`。

---

### 2.3 GitHub 上有没有合适的开源「产品底座」？

**用户问题**：是否有开源项目可直接当 SayAgain 底座？

**结论**：**没有**可 fork 即上架 Play、且贴合 SEA/MENA 跟读纠错的成品；只有 **零件** 可组合。

**分层归纳**：

| 层级 | 代表 | 许可 | 能否当底座 |
|------|------|------|------------|
| Android 跟读壳 | [rougo](https://github.com/1Selxo/rougo)、[EchoTalk](https://github.com/alisolphp/EchoTalk) | GPL / MIT | 仅 UX 参考；rougo 为媒体跟读，GPL 对商业不友好 |
| 桌面练口语循环 | [Mimora](https://github.com/vikonix/Mimora)、[EchoLoop](https://github.com/vikonix/EchoLoop) | MIT | 产品循环可参考，非移动端 |
| 发音评分库 | [OpenPronounce](https://github.com/Halleck45/OpenPronounce) | MIT | **v2 服务端评分** 候选 |
| 研究向 | GOPT、pronunciation-teacher | 各异 | 运维重，适合研究非 v1 |
| 理念参考 | [ShadowCoach](https://github.com/Marvelousp4/ShadowCoach) | — | macOS/iOS，非 Android |
| 商业竞品 | ELSA、Speak、Pingo | 闭源 | 无开源替代 |

**推荐组合（非单 repo）**：

```text
v1：自建 Android Compose + 薄 FastAPI + agent-research/english-shadowing/
v2：可选接入 OpenPronounce（音素级）；ASR 需在印尼/越南口音英语上验收
```

---

## 3. 当前冻结的产品与技术决策（摘要）

摘自会话与 `SAYAGAIN.md`（若与规格书冲突以规格书为准）：

| 项 | 决定 |
|----|------|
| 产品名 | SayAgain |
| 首发渠道 | Google Play 海外；国内商店 v1 不做 |
| 目标市场 | 东南亚 + 中东（非中国区为主） |
| 教练语言 | en + local（id/vi/ar）；开发期曾用 zh 占位 |
| ASR | 开发默认 DashScope Paraformer；上线前验收 SEA 口音；备选云 ASR |
| 及格线 | `excellent` / `pass` / `retry`（`pass_rules.py`） |
| 核心 API（规划） | `POST /v1/shadow/evaluate`：reference + transcript/audio → score、issues、coach、grade |
| 北极星 | 周活用户的有效练习句数 |
| 差异化 | 轻、便宜、句级可解释；对标 ELSA 贵、Speak 重、纯聊天无标准句 |

**v1 明确不做**：通用聊天、无限 AI 生成课、UGC 广场、音素实验室（可 v2）。

---

## 4. 代码与文档索引

| 资源 | 路径 |
|------|------|
| 产品规格（SSOT） | [`agent-research/SAYAGAIN.md`](../../../agent-research/SAYAGAIN.md) |
| Phase 0 管道 | [`agent-research/english-shadowing/`](../../../agent-research/english-shadowing/) |
| Play 小而美调研 | [`docs/GOOGLE_PLAY_SMALL_BEAUTIFUL_APPS_2025_2026.md`](../../GOOGLE_PLAY_SMALL_BEAUTIFUL_APPS_2025_2026.md) |
| DeepTutor 架构（对照用） | [`docs/deeptutor-architecture/README.md`](../../deeptutor-architecture/README.md) |
| Agent 研究索引 | [`agent-research/README.md`](../../../agent-research/README.md) |

---

## 5. 待办与未决项（讨论中提出）

1. **首发国二选一深潜**：印尼 vs 越南（ASO 词表、第一课场景、教练文案语言）
2. **ASR 验收**：20 条当地口音英语样本，对比 DashScope vs 备选引擎
3. **Phase 1**：FastAPI + DashScope ASR 上传音频；Android Home + 练习页
4. **OpenPronounce spike**：是否在 v1.5 增加音素提示，与现有句级对齐并存

---

## 6. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-10-12 | 初版：合并 2026-08~09 产品闲聊（定位、DeepTutor、开源底座） |
