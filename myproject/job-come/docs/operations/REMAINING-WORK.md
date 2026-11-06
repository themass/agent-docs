# REMAINING-WORK：遗留事项总表

- **核对日期**：2026-11-06（每项都对照过代码、远端分支、文档和本机环境，不是凭记忆）
- **范围**：舟卡（job-come）模拟面试，以及 naviforge 的广告接入。
- **怎么用**：状态只有四种：**已完成（提交号）**、**未完成**、**未确认**（需要外部信息才能判断）、**需你决定**。完成后改状态，不删行。

## 〇、已修复：`main` 的测试套件坏了（我的失误）

| 项 | 内容 |
|---|---|
| 原因 | 合并 `111111`（`936c967`）时，带入了 71 个 `main` 上没有的文件：52 个测试、19 个脚本。这些测试依赖的实现不在 `main` 上。 |
| 现象 | 收集错误 4 个（`test_evaluate_writing_script`、`test_export_html`、`test_standing_block_injection`、`test_tool_name_contract`）；另有约 40 个测试在 `test_skill_packages`、`test_system_prompt_capture`、`test_paths`、`test_resume_*` 等文件中失败。 |
| 之前为什么没发现 | 之前的"801 通过"是在旧分支上跑的，没有在干净的 `main` 上跑。 |
| 修法 | 从 `main` 撤回这 71 个文件，在干净的 `main` 上确认回到合并前的基线。 |
| 状态 | **已完成（`4cf4c6a`，已推送）**。撤回后 `main` 的后端测试为 805 通过、1 失败（第二节第 11 项）。全部 19 个脚本也一并撤回，哪些要留见第一节第 8 项。 |

## 一、需要真实环境或外部人员

| # | 事项 | 状态（核对结果） | 完成标准 |
|---|---|---|---|
| 1 | 真模型下跑一场模拟面试（五个岗位族，含弱答、跑题、拒答、夹带指令） | **未完成**。仓库里没有任何真实运行的记录。 | 按 [QA-MOCK-INTERVIEW-ACCEPTANCE](QA-MOCK-INTERVIEW-ACCEPTANCE.md) 跑完，记录发给开发者 |
| 2 | 面试官与评审在真实模型下的表现（SPEC-V2 §7.2 的 G、J、K） | **未完成**，依赖第 1 项 | 人工读记录，过验收手册 §5 的清单 |
| 3 | 15 个岗位族的追问方向审校 | **未完成**。[REVIEW-ROLE-FAMILIES](REVIEW-ROLE-FAMILIES.md) 已生成，60 个意见格全部为空。 | 各族意见回填，并同步改代码 |
| 4 | MySQL 5.6 验证（迁移 023、024） | **未完成**。Docker 守护进程当前没有运行，本地只有 `mysql:8.4`，没有 5.6。 | 5.6 上升级、降级、再升级通过，回填正确 |
| 5 | 轮换火山引擎 Access Key | **未确认**。这个 Key 在 `3fb17a2` 的 `test/prom.txt` 中出现。它不在 `main` 上（修复已在 `936c967` 中去掉），但仍在本地历史和两个本地分支里。是否已在火山引擎后台轮换，仓库里无法判断。 | 后台已轮换 |
| 6 | 删除残留分支 | **已完成**：`claude/nifty-chebyshev-ea3307`、`claude/youthful-lewin-1695b5` 已删除，它们都只含 `3fb17a2`（即第 5 项的 Key 所在提交）。为此移除了干净的 worktree `friendly-lehmann-b3e4be`。远端没有这两个分支。 | |
| 6a | 本地 reflog 仍保留含 Key 的 `3fb17a2` | **需你决定**。要彻底清除，需要 `git reflog expire --expire=now --all` 加 `git gc --prune=now`，这会影响整个本地仓库，也不能撤销。 | 你同意后执行 |
| 7 | naviforge 广告上线 | **未完成**，见第五节 | 见第五节 |
| 8 | 保留哪些脚本 | **需你决定**。第〇节撤回了全部 19 个脚本，`scripts/test-local.sh` 不再依赖它们。要留的请给出文件名。 | 你给出名单后我加回 |

## 二、开发任务

| # | 事项 | 状态（核对结果） | 说明 |
|---|---|---|---|
| 8 | 校准集（SPEC-V2 §5.3） | **未完成**。代码与数据都没有。 | 需要人工打分的样例，我只能建结构 |
| 9 | 分数漂移复核（差距超过 2 分标为待复核） | **未完成**。只在规格里，代码中没有 `待复核` 的实现。 | |
| 10 | 重试按钮的前端测试 | **未完成**。`agent-message-id.test.cjs` 只测请求体带不带 id，没测重试沿用同一 id。 | 需要把重试逻辑抽成可测的纯函数 |
| 11 | `test_preview_execution.py` 整套运行失败 | **未完成**。单独跑 9 个全部通过；在整套运行中失败（见第〇节的失败列表）。 | 疑似日志捕获被前面的测试污染 |
| 12 | 24 小时空闲超时（记录回答时不应用） | **未完成**，记为"无害"，优先级低 | |

## 三、已完成（本轮之前列为遗留的）

| 事项 | 提交 |
|---|---|
| 迁移 024 不写中文、可重跑（latin1 上的 1366 缺陷） | `a48221d` |
| 验收手册（真模型验收） | `363a9fb` |
| 录制工具 `jc.coach.recording` 与 CLI | `ea87ec0` |
| 上线前检查写入部署文档 | `99027d0` |
| 同一条消息重发不重复记录回答（后端 `client_message_id`，前端请求体） | `609fb75` |
| 岗位族审校表生成器与漂移测试 | `73c55bb` |

## 四、搁置（按你的决定，不在本轮做）

| 事项 | 状态 | 接口 / 位置 |
|---|---|---|
| 题库包（`question_bank/<岗位族>-<级别>.yaml`） | **未完成**（搁置） | `jc.coach.sources`（已有 10 个函数的扩展点） |
| 题单蓝图（SPEC-V2 §4.2） | **未完成**（搁置） | `jc.coach.sources` |
| 种子题库（SPEC-V2 §4.1） | **未完成**（搁置） | `jc.coach.sources` |
| 档案库 | **未完成**（搁置） | `jc.coach.sources` |
| 手机布局 | 你决定不做 | — |

## 五、naviforge 广告接入（AdSense）

**现状**：代码就绪，**没有广告显示**。

| # | 事项 | 状态（核对结果） | 谁 |
|---|---|---|---|
| A1 | AdSense 账号开通并通过站点审核 | **未确认**，仓库里无法判断 | 你 |
| A2 | 发布商页 HTTPS，允许扩展 iframe 嵌入（不设 `X-Frame-Options: DENY`） | **未完成**（服务器侧） | 你 |
| A3 | 为 NVF-ADS-03、04、05 建互不相同的展示广告单元 | **未完成**（5 个 HTML 中 `data-ad-slot` 仍是 `PASTE_SLOT_NVF-ADS-0x`） | 你 |
| A4 | 把 `ca-pub` 与 slot 填入 `docs/store-assets/ads/*.html` | **未完成**（5 个文件的 `data-ad-client` 仍是 `ca-pub-XXXXXXXXXXXXXXXX`） | 等 A1、A3 的 ID，我可以做 |
| A5 | 5 个 HTML 上传到公网 `…/file/ads/` | **未完成** | 你 |
| A6 | 设置 `AD_EMBED_BASE_URL` | **未完成**（`ads-config.ts` 中仍为 `''`；`AD_ENABLED_SURFACES` 为 `options`、`ocr`、`screenshot`，符合要求） | 我可以做，等 A5 |
| A7 | 线上 `privacy_navi.html` 加广告段落；同步商店 Data safety 与"可能展示广告" | **未完成** | 我可以起草，你上传 |
| A8 | `npm run check` → `npm run zip` → 上传新版扩展 | **未完成** | 你 |
| A9 | 自测：设置页、Toolkit、截图工作室有 iframe；Agent 对话与 Thinking 条下没有 | **未完成** | 你 |
| A10 | 第二波把 `agentFeed` 加入 `AD_ENABLED_SURFACES`（只在空状态） | **未完成**，`agentThinking` 不建议开 | 你决定 |

**注意**：不要在 content script、popup、登录回调、`apps/host` 里加广告；扩展包内不要加载 `adsbygoogle.js`。

## 六、naviforge 其他未审计的遗留

下列文档里有"缺口"或"待办"的描述，本次没有逐条核对，**状态未知**：

- `BEST_PRACTICES_REVIEW.md`（如跨 iframe 定位符的缺口）
- `SCRAPER_AGENT_RELIABILITY_PLAN.md`
- `GENERAL_BROWSER_AGENT_REFACTOR_PHASE_1.md`
- `ARCHITECTURE_OPTIMIZATION.md`（§2.5A 的 store 端口类型"待收敛"）

## 七、已知的限制（不是待办，但上线前要知道）

- **级别的年限区间和准备度阈值**是折中值，不是阿里官方标准（SPEC-V2 §3.5、§8）。需要你们确认。
- **面试条与按钮只做了桌面版**（手机不在范围内）。
- **录制工具**的结果格式是按代码推断的，没在真实运行中见过（见验收手册 §3）。
- **MySQL 锁行为**没有在 5.6 上验证（第一节第 4 项）。
- **没有 `client_message_id` 的请求**仍会记两次回答；带 id 的已去重。

## 八、本地环境（不是仓库内容，但需要清理）

| 项 | 状态 |
|---|---|
| worktree `friendly-lehmann-b3e4be` 和两个残留分支 | **已完成**：已移除并删除（见第一节第 6 项） |
| worktree `mystifying-shirley-395a1c` 检出的分支停在旧基线（`73c55bb` 之上），不能用来跑测试 | 未完成；这个分支的内容要合进 `main` 后再同步，见第九节第 4 项 |
| 本地 reflog 里仍有含 Key 的 `3fb17a2` | 见第一节第 6a 项 |
| `myproject/job-come/.claude/` 未被忽略，每次 `git status` 都显示 | 你决定是否加入 `.gitignore` |
| 配置报错时曾把本地 `.env` 的凭据打印到命令输出中（S3、LLM、SMTP、数据库），这些值不在 git 中 | 未确认；如果会话记录会被分享，建议轮换 |

## 九、建议的顺序

1. 第一节第 6a 项（reflog 是否清理）和第 8 项（保留哪些脚本）需要你的决定。
2. 确认第一节第 5 项（Key 是否已轮换）。
3. 第二节第 10、11 项我可以接着做；第 8、9 项需要你先定要不要做。
4. 分支 `claude/mystifying-tesla-88a6fa` 上的这个文档（`ee82be4`）还没有合进 `main`。要合的话，我把它 cherry-pick 到 `main`。
5. 第一节第 1、2、3、4 项需要真实环境或外部人员。
6. 广告（第五节）等 A1、A3 的 ID。
