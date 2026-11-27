# Hermes her 生产产线详细设计（可执行）

日期：2026-11-28｜状态：详细设计提案；不改变任何已定决定，不表示已实现。本文把
《Hermes 驱动的 Live2D 角色资源生产工作台》
（Android 仓库 `docs/superpowers/specs/2026-11-27-hermes-live2d-production-design.md`，
下称**可行性 spec**）的方案 B 从可行性展开成可开工的详细设计：产线全景、tool 契约、
skill 划分、质量门、用户自定义边界、分阶段 demo。所有落地位置以本仓库
`myproject/companion-agent/`（下称 server 仓库）与 Android 仓库 `myandroidTest`
（worktree `.claude/worktrees/focused-mclean-1bfa86`，基于 `weifu-refactor` 线）的
现状文件为准；引用处给出真实路径。

标注约定（沿用执行手册纪律，`myandroidTest/docs/design/2026-11-27-her-execution-playbook.md` 第 5–6 条）：

- **【已定】**：先前文档已决定的事，本文只展开不推翻，附来源。
- **【事实】**：已在代码里核实的东西，附文件路径。
- **【建议】**：本文新提的方案，可被否，编号 N1…N15。
- **【待决】**：需要用户/立项拍板的事，不假装已定。

---

## 0. 前提台账

### 0.1 引用的已定决定

| 编号 | 决定 | 来源 |
|---|---|---|
| D-B | 产线采用「自有控制面编排 + Hermes 受控执行器」（方案 B），Hermes 不是事实源、权限源或发布状态源 | 可行性 spec §4；persona/her 分层 `myandroidTest/docs/design/2026-11-28-persona-her-split-architecture.md` §6.1 确认 |
| D-SM | 产线状态机 `DRAFT → BRIEF_REVIEW → … → RELEASED`，任一阶段可 `BLOCKED`/`FAILED_RETRYABLE`，失败从最近检查点重试、不覆盖已验收版本 | 可行性 spec §7 |
| D-OUT | **产线最终产物 = 一个 `HerPack` 版本 + 一个 persona 包版本**；`publish_release` 落地 = 播种 `ca_her_pack`（+ `ca_character_pack`）+ 默认绑定 + CDN 分发；发布永远 CONFIRM + 非发起人复核 | persona/her 分层 §6.1 |
| D-USER | 用户自定义 her **不做「上传任意模型」**；自由度落在参数化模板槽；**用户线 renderer 限定非 Live2D**（自家分层 2D / Rive / VRM），直到 Expandable Application 书面许可落定 | persona/her 分层 §6.3 |
| D-LIC | Live2D「可扩展应用（Expandable Application）」条款是 renderer 中立的法务前提；官方示例模型不可作主形象；书面结论是发布前法务项 | persona/her 分层 §6.4 |
| D-HID | `her_id = <renderer>-<asset>`（asset 缺失用 role_id）；renderer 长在 her 包上，不长在角色上 | persona/her 分层 §3；已实现，见 F-SEED |
| D-DEP | 全程禁止 Docker；生产按原生 systemd 进程形态 | 可行性 spec §10；执行手册第 5 条；项目纪律 |
| D-PLAY | 产线任务族 = 执行手册 P2-01（控制面）、P2-02（Hermes 受控 worker）、P2-03（授权资产全流程）、P2-04（版本审批灰度撤权）、P2-05（第三方治理） | `myandroidTest/docs/design/2026-11-27-her-execution-playbook.md` §5 |

### 0.2 已核实事实（本文设计的承重墙）

| 编号 | 事实 | 位置 |
|---|---|---|
| F-HER-TBL | `ca_her_pack(her_id unique, renderer, pack_version, payload JSON, status∈draft/published/retired, source)`；`ca_character_her(role_id, her_id, is_default)` | server 仓库 `myproject/companion-agent/server/src/companion/db/schema.py:490-513`；迁移 `server/migrations/versions/0005_her_pack.py` |
| F-UPSERT | `SqlHerPackStore.upsert` 幂等：payload/renderer/status 任一变化才 `pack_version+1`，内容不变不写；payload 只做结构校验（映射；`model_ref` 若存在是映射；`effects/stickers/touch_zones` 若是则为 list）；`source` 注释枚举 `card | hermes | manual` | `server/src/companion/service/roles/hers.py:36-47,137-169`；`db/schema.py:498` |
| F-SEED | `seed_from_cards`：卡内映射形 `model_ref` → her 包（`her_id=<renderer>-<asset>`，`source="card"`）+ 默认绑定；播种脚本 `server/tools/seed_her_packs.py` | `service/roles/hers.py:220-253` |
| F-API | `/v1/hers`、`/v1/hers/{her_id}`：列表给卡片字段（renderer 徽标、effect/sticker 计数、voice_ref 只出 provider+voice_id），详情给 `model_ref/effects/stickers/touch_zones`；`HerCatalog` 进程级缓存，播种后 `invalidate()` | `server/src/companion/api/http/routers/hers.py` |
| F-PACK-CONTRACT | 端上资产包契约：`schema_version==1`；`pack_id` 匹配 `[a-z0-9][a-z0-9_-]{0,63}`；`version>0`；`files` 1–200 项、每项 path+sha256、路径分量受限；`entry_point ∈ files`；安装 = 暂存目录逐文件 hash 校验 → 原子 rename；单包 ≤100MB；版本装后不可变 | Android 仓库 `feature-companion/src/main/java/com/openapi/ks/myapp/avatar/CharacterAssetPack.kt`（commit `5c951543`） |
| F-ENGINE-ENUM | 端上引擎枚举现为 `LAYERED, LIVE2D, RIVE, DUIX, TAO`——**无 VRM**；`/v1/hers` 的 renderer 注释口径是 `simple|live2d|vrm|rive|…`，两侧映射有缺口 | 同上；`routers/hers.py:38-39` |
| F-TOOLCHAIN | 确定性工序脚本已在仓库：`check_delivery_ready.py`（分层交付自检）、`wardrobe_layout.py`（Layout 生成）、`gen-expressions.py`（从 `wardrobe-spec.json` 生成 exp3+model3 注册表）、`wardrobe-spec.json`（单一事实源，变体带 `verifiedFrom`） | Android 仓库 `scripts/dh-lab/live2d-lab-assets/`，流程见该目录 `UNDERWEAR-PIPELINE.md` |
| F-AVGEN | 服务端图像生成骨架已在：`POST /v1/avatars/generate` 同步出图、`ALLOWED_STYLES` 白名单（风格直连检查点与提示词，不开自由文本）、provider 是协议（fake 默认可跑、真实挂载点唯一 `settings.avatar_gen_provider`）、失败统一收敛不外泄原始错误、429 QUOTA 日配额 | `server/src/companion/service/avatar_gen/{port,providers,service,sql}.py`；契约文档 Android 仓库 `docs/design/2026-11-24-anime-avatar-mvp.md` |
| F-DEPLOY | 生产 104 已有 systemd 形态：`companion-api.service`、`companion-voice.service`；api 监听 8081（经 nginx 反代，不得绑回环）；迁移经 alembic，生产 head 已到 0004、0005 在仓 | `myproject/companion-agent/deploy/systemd/`；`docs/RUNBOOK.md` |
| F-HERMES-REF | Hermes profile 的先例形态已在 server 仓库：`SOUL.md + profile.yaml + skills/<name>/SKILL.md + scripts/` 四件套，运行时数据不入库 | `hermes/content-studio-agent/HERMES_HOME_GUIDE.md`、`hermes/content-studio-agent/bundle/` |
| F-VOICE | 音色探测工具已有雏形 `server/tools/probe_voices.py`；voice_ref 对外口径 `{provider, voice_id}`（params 不公开） | `service/roles/hers.py:73-82` |

### 0.3 本文不做什么

- 不推翻 D-B…D-PLAY 任何一条；与可行性 spec 冲突处以可行性 spec 为准并在此登记。
- 不改代码、不建迁移（本文是文档；迁移与代码归 P2-01 起的实施任务）。
- 不规定 Android 第二刀（引擎自动选择改读 her 摘要）的实现——只钉产线产物必须满足 F-PACK-CONTRACT。
- 数值门槛（纹理、面数、帧预算）不虚构：结构固定、数值留 P0-03 基线实测回填（执行手册第 6 条）。

---

## 1. 产线全景

### 1.1 一句话

**输入是「她长什么样」的意图（一句话 / 参考图 / 已有角色卡），产物是「一个可安装的
asset pack + 一行 `ca_her_pack`（`source=hermes`）+ 一个 persona 包版本 + 默认绑定」；
中间全部状态在自有控制面，Hermes worker 只在任务信封内调白名单工具，发布由非发起人
人工复核触发。**（D-B、D-OUT）

### 1.2 三种输入，一条管线

| 输入形态 | 含义 | 入口工序差异 |
|---|---|---|
| 一句话 brief | 文字描述性格/外观/风格边界 | 从 `brief-intake` 起：Agent 整理成结构化 Brief，人确认后才生成 |
| 参考图 | 用户提供图片+权利声明 | Brief 增加 `source_refs`（作者/许可类型/用途声明，可行性 spec §7.1.2）；生成图标记 provider/model/version/prompt 版本 |
| 已有角色卡（persona 包） | 「linche/sudai 这类现有角色换形象」 | 跳过 persona 生成，persona 包版本直接沿用（`ca_character_pack` 已有行不动）；产线只产 her 半 |

### 1.3 拓扑（可行性 spec §5 的落地化）

```text
发起（Web 工作台 / CLI / 角色卡对账任务）
      │  项目、Brief、上传（签名 URL）、确认
      ▼
控制面 API（并入 companion API 进程或独立进程，见 §7.3 N13）
  ├─ 表：ca_prod_project / ca_prod_run / ca_prod_task / ca_prod_artifact
  │      / ca_prod_approval / ca_prod_release            ← 新迁移 0006（N3）
  ├─ 队列：Postgres 任务表 + worker 租约（N4，不新增组件）
  └─ Artifact 存储：私有目录 + 短期签名 URL（复用 uploads 链路，N5）
      │  task envelope：task_id/project_id/input_version/allowed_actions/超时/取消令牌
      ▼
Hermes worker（systemd 单元、独立系统账户 hermes-prod；版本固定）
  ├─ her-production profile（SOUL + skills，见 §4；形态同 F-HERMES-REF）
  └─ 只能经 MCP 调白名单工具（§3 清单）；无发布权、无凭据、无任意 shell
      ├─ 图像 provider adapter（复用 F-AVGEN 挂载点；provider 凭据只在服务端）
      ├─ 确定性工具（wrap F-TOOLCHAIN 脚本 + 新建校验/打包工具，§3）
      └─ Cubism/psd2live 执行器（独立进程经 MCP；GPL 纪律：不链接不分发其代码，
         persona/her 分层 §6.2；不可远程时该步转人工任务）
      ▼
质量门 G-A…G-D（§5）→ 不可变 release candidate → 非发起人复核（CONFIRM）
      ▼
publish_release（唯一写入口）：
  pack 上传 CDN（私有签名） → upsert ca_her_pack(her_id=<renderer>-<asset>,
  source="hermes", status 见 N6) → bind(role_id, her_id, is_default) →
  persona 侧 upsert ca_character_pack（若 persona 半也是新产物） →
  HerCatalog.invalidate() → 端上对账可见
```

**发布写入点只有一个**：所有对 `ca_her_pack` 的产线写入都经 `publish_release` 包
`SqlHerPackStore.upsert`（F-UPSERT）。幂等由 upsert 内建：产线重跑同一内容**不会**顶
`pack_version`——这就是「对账」语义：`/v1/hers` 里的版本号只认真实内容变更。
【已定 D-OUT】+【事实 F-UPSERT】

### 1.4 状态映射：产线状态机 vs `ca_her_pack.status`

产线状态机（D-SM 十三阶段）活在控制面 `ca_prod_run.status`；`ca_her_pack.status`
只有 `draft/published/retired`（F-HER-TBL），是服务端对「注册表可见性」的投影。

- 【建议 N6】映射规则：`publish_release` 成功 → `published`；下架/撤权 → `retired`；
  产线中途（含 candidate 阶段）**不写 `ca_her_pack`**——避免半成品行污染
  `/v1/hers`（该路由无文件兜底链，库里即事实源，`routers/hers.py` 文件头）。
  `draft` 保留给「手工先占位、后补内容」的非产线用法（`source="manual"`）。
- 【已定】状态变更同样算内容变更，对账会顶 `pack_version`（F-UPSERT docstring：
  「status 变算内容变（上线/撤回要对账得到）」）。

### 1.5 产线产物规格（最终交付的四件东西）

1. **asset pack**（zip）：满足 F-PACK-CONTRACT 的 manifest + 文件树。`pack_id` =
   her 的 asset 名（`[a-z0-9][a-z0-9_-]{0,63}` 因此 asset 名也受此约束）。
   单包 ≤100MB 是端上硬线（F-PACK-CONTRACT `MAX_BYTES`）——Live2D 两张 2048 页贴图
   加 moc3 在预算内，超限在 G-A 门就拒，不让端上安装失败兜底。
2. **`ca_her_pack` payload**（JSON，契约字段即路由已出去的口径）：
   ```json
   {
     "name": "…", "tagline": "…",
     "model_ref": {"asset": "<pack_id>", "version": 3, "hash": "<sha256-of-pack>"},
     "effects":   [{"id": "fx_pat_head", "asset": "<pack内路径或资产id>", "hash": "…", "anchor": "head"}],
     "stickers":  [...],
     "voice_ref": {"provider": "volcengine", "voice_id": "…", "params": {}},
     "thumbnail": "…",
     "touch_zones": [ ... ]
   }
   ```
   【事实】服务端只结构校验细节不解析（F-UPSERT）；【建议 N7】产线在 G-A 门用服务端
   版镜像校验（§3 T-08）把「端上必拒的包」挡在发布前——现在结构校验挡不住
   `files>200`、hash 非 hex、`entry_point` 不在 files 这类端上契约错误。
   注：现有 `seed_from_cards` 生成的 `model_ref` 是 `{renderer, asset}` 形态
   （F-SEED），产线新包按 persona/her 分层 §3 的 `{asset, version, hash}` 收敛；
   两形态并存期端上以 `asset` 为准（兼容说明归端上第二刀）。
3. **persona 包版本**（仅当 persona 半是新产物时）：`ca_character_pack` upsert
   （`service/roles/packs.py:91`，幂等规则同 her 侧）。
4. **证据包**：QA 记录、审批记录、权利台账、（性能门后）perf evidence——全部是
   `ca_prod_artifact` 行，发布时以 hash 挂到 `ca_prod_release`。

---

## 2. 控制面数据模型（可行性 spec §8 落到本库）

【建议 N3】新迁移 `0006_production_control`，表用 `ca_prod_` 前缀放 companion 同库
（PG JSONB/timestamptz、MySQL MEDIUMTEXT/datetime 方言分支沿用 0004/0005 模式，
`db/schema.py`），**不新建独立服务数据库**——理由：发布写入点要和 `ca_her_pack`
同库同事务边界；组件不增（D-DEP 精神）。

实体（对应可行性 spec §8 名称）：

| 表 | 关键列 | 备注 |
|---|---|---|
| `ca_prod_project` | project_id（opaque）、owner/team、状态、保留策略 | 首版单组织，不开放公众（可行性 spec §4 试点假设） |
| `ca_prod_run` | run_id、project_id、input_version、状态（D-SM 十三态）、发起人 | run = 一次端到端；重试新建 task 不新建 run |
| `ca_prod_task` | task_id、run_id、stage、executor、allowed_actions（JSON）、idempotency_key、租约（lease_owner/expires_at）、取消令牌、错误码、attempt | 队列即表：`SKIP LOCKED` 领取（同 POI 提醒任务的既有模式，`service/proactive` 调度先例）【N4】 |
| `ca_prod_artifact` | artifact_id、run_id、type（brief/source/layout/cmo3/moc3/pack/evidence/perf…）、object_key、sha256、size、parent_artifact_id、工具版本、许可记录 | 不存大二进制在行里（可行性 spec §8） |
| `ca_prod_approval` | approval_id、run_id、gate（§5 的门名）、请求快照 hash、决定人、决定、幂等键 | 非发起人复核在此钉：`decided_by != initiated_by` 约束在服务层 |
| `ca_prod_release` | release_id、her_id、pack artifact、persona artifact、status（candidate/approved/published/revoked）、审批引用、`ca_her_pack.pack_version` 快照 | 发布指针与回滚目标；P2-04 灰度字段后补 |

幂等纪律（可行性 spec §9 末段）：一切工具参数带 schema 校验、大小/时长/费用限额、
幂等键；**外部副作用失败不伪报成功**；危险权限（任意 shell/路径/URL、直写生产表、
自动花费、删已发布包）默认关闭且不进白名单。

---

## 3. tool 清单

命名 snake_case，对齐可行性 spec §9（已定框架）；「现成」= 代码已在仓、包一层 MCP
即可；「新建」= P2-01/P2-02 要实现的。**权限口径沿用可行性 spec §9：READ / AUTO /
CONFIRM**。所有工具的 `project_id/task_id` 由 worker 上下文注入，模型不能传身份字段
（可行性 spec §5【已定】）。

### 3.1 现成（包装即可用）

| # | 工具 | 输入 → 输出 | 幂等 / 失败语义 | 权限 | 依据 |
|---|---|---|---|---|---|
| T-01 | `validate_layer_delivery` | source artifact id → `{issues[], pass}` | 纯读，天然幂等；输出结构化问题清单，脚本异常→`FAILED_RETRYABLE` 带 stderr 摘要 | READ/受控执行 | `scripts/dh-lab/live2d-lab-assets/check_delivery_ready.py`【F-TOOLCHAIN】 |
| T-02 | `generate_wardrobe_layout` | source artifact id, out_version → 新 layout artifact | 同输入+幂等键 → 同产物；不覆盖旧文件（写新版本目录后原子登记） | AUTO | `wardrobe_layout.py` |
| T-03 | `generate_expressions` | wardrobe-spec artifact + 资产清单 → exp3 集 + model3 注册表 artifact | 纯函数：spec hash+资产 hash 定输出；`status != active` 槽不生成 | AUTO | `gen-expressions.py`；spec 单一事实源纪律见 `myandroidTest/docs/design/2026-11-23-换装抽象与特效层设计.md` |
| T-04 | `upsert_her_pack_row` | `{her_id, renderer, payload, status, source}` → `{pack_version}` | 现成 `SqlHerPackStore.upsert`：内容不变不写不顶版本；`HerPayloadError`/未知 status 拒绝 | CONFIRM（只挂 publish 链路） | `service/roles/hers.py`【F-UPSERT】 |
| T-05 | `bind_character_her` | `{role_id, her_id, is_default}` | 现成 `bind`：重复绑定不写 | CONFIRM | 同上 :173-189 |
| T-06 | `list_hers / get_her` | 对账读 `/v1/hers` | 只读；产线完成后用它核对 `pack_version` 未漂移 | READ | `routers/hers.py`【F-API】 |
| T-07 | `request_image_generation` | Brief version + provider preset（非自由提示词） → `{job_id}` | 现成骨架：同步出图（MVP 语义），日配额 429；失败 `provider_failed` 统一收敛，不外泄原始错误；风格白名单 `ALLOWED_STYLES` 先扩到产线需要的风格并过许可审查 | **CONFIRM**（外部费用+发素材） | `service/avatar_gen/`【F-AVGEN】；可行性 spec §9 |
| T-08 | `probe_voice` | 候选 voice_id 列表 → 可用性/样音 artifact | 现成雏形 `server/tools/probe_voices.py`；只读外部探测，可重试 | READ | 【F-VOICE】 |

### 3.2 新建（按优先级）

| # | 工具 | 输入 → 输出 | 幂等 / 失败语义 | 权限 |
|---|---|---|---|---|
| T-10 | `validate_asset_pack` | pack artifact → `{violations[]}` | 纯校验，Python 镜像 F-PACK-CONTRACT：schema_version==1、pack_id/版本/files≤200/路径分量/`entry_point ∈ files`/sha256 hex、总大小 ≤100MB。**G-A 硬门**。任何一条违反即不可发布，错误码逐条对应端上 `CharacterAssetPolicy` 的拒点 | READ |
| T-11 | `build_asset_pack` | 模型导出 artifact 集（moc3/model3/贴图/exp3/thumbnail/wardrobe-spec 引用）+ pack_id/version → pack artifact + manifest | 确定性：同一输入集+version → 同一 sha256（manifest 排序、文件顺序固定）；已发布过的 (pack_id, version) 拒写（版本不可变，镜像端上「Version already installed」）；产物写新对象不改源 | AUTO |
| T-12 | `build_her_payload` | Brief + pack artifact（hash/version）+ 特效/贴纸目录 + voice_ref + 触摸区声明 → payload JSON + T-10 报告 | 确定性装配；`model_ref={asset,version,hash}`（N7）；产物不过 T-10 就不出 payload | AUTO |
| T-13 | `inspect_model_export` | 导出 artifact → `{missing_refs[], param_ids[], file_hashes{}, sizes{}}` | model3.json 引用完整性、moc3/cdi3/exp3/物理文件存在、逐文件 SHA-256 清单；结构检查**不设** `runtime_verified=true`（可行性 spec §7.2.8【已定】） | READ |
| T-14 | `validate_model_specs` | pack artifact + G-B 门配置（§5.2） → `{metrics{}, violations[]}` | 模型规格门：纹理/面数/锚点预算（数值来自门配置，不写死在工具里）；纯读 | READ |
| T-15 | `request_cubism_rig` | layout artifact + 目标 → rig 任务（psd2live MCP 独立进程，或人工 Editor 工单） | 远程不可用时降级为人工任务并收回工程+导出+证据（可行性 spec §7.2.7【已定】）；psd2live **独立进程经 MCP、不链接不分发其代码**（persona/her 分层 §6.2【已定】）；产物带工具版本 | **CONFIRM** |
| T-16 | `request_runtime_qa` / `submit_perf_evidence` | pack version + 测试清单 → QA 任务；回传证据（截图/录屏/帧时间/PSS） | 设备执行由协调会话独占（`her-execution-playbook.md` 第 4 条【已定】）；证据 artifact 必带设备型号、系统、构建 commit、包 hash；缺证据 = G-C 门 FAIL，不接收 agent 文字结论 | **CONFIRM** |
| T-17 | `upload_artifact / fetch_artifact` | 字节流（签名 URL 短时有效） → artifact 行 + sha256 | 上传幂等按 sha256 去重；存储端禁用公共读；日志只写 artifact id/hash 不写签名 URL（可行性 spec §8【已定】）。落地优先复用 uploads 链路（`service/uploads/`）【建议 N5】 | READ（写经 worker 上下文） |
| T-18 | `publish_release` | `release_candidate_id + 审批凭证` | **唯一发布入口**：服务端校验 `ca_prod_approval`（非发起人【已定 D-OUT】）→ T-11 产物签名上 CDN → T-04 upsert（source=`"hermes"`）→ T-05 bind → `HerCatalog.invalidate()`；任一步失败整个 release 停在 candidate，不半写。幂等：同一 candidate 重复调用不产生第二个发布指针 | **CONFIRM + 审核者角色限定** |

失败语义统一约定：每个工具返回结构化 `{ok, error_code, evidence_artifact_ids[]}`；
错误码三族——`INPUT_*`（不重试，退回上一阶段）、`TRANSIENT_*`（退避重试，带 attempt
上限）、`POLICY_*`（权限/配额/审批缺失，进 `BLOCKED` 等责任人）。Hermes 的自然语言
输出永远不是状态（可行性 spec §5【已定】）。

---

## 4. skill 清单（Hermes profile 形态）

profile 形态沿用本仓先例【F-HERMES-REF】：`SOUL.md + profile.yaml +
skills/her-production/<name>/SKILL.md + scripts/`，开发镜像入 git、运行时数据
（state.db/sessions/home）不入库。skill 是**工序 SOP**：把「这一步做什么、调哪个
工具、产物登记到哪、失败找谁」写成可复用文档+薄脚本；**校验与发布逻辑不放进 skill
的散文里**（审批由服务端检查，不靠提示词——可行性 spec §5【已定】）。

| skill | 内容 | 复用什么 | agent 自由部分 |
|---|---|---|---|
| `brief-intake` | 一句话/参考图 → 结构化 Brief（性格、外观边界、成年设定、目标设备、用途）+ 权利声明 + 澄清问题清单 | Brief JSON schema（`ca_prod_project` 附件） | 提问措辞、风险提醒、把散乱输入整理成字段——纯语言工作 |
| `layered-delivery` | 分层素材交付 SOP：跑 T-01、解释 issues、给出美术返工单 | T-01、UNDERWEAR-PIPELINE 约定 | 问题归因、返工说明 |
| `wardrobe-bind` | 槽位/变体/绑定纪律：只引用模型已有 ArtMesh（`ParamWear_*` 惯例）、`verifiedFrom` 必填、pending 槽不进命名空间 | T-03 + `wardrobe-spec.json` 单一事实源【已定，2026-11-23 文档】 | spec 草案建议；**最终绑定值必须来自人工验证记录** |
| `effects-catalog` | 特效/贴纸目录条目：id+资源 hash+锚点声明；与 `cmp.cue` 白名单对齐（白名单属策略不属包——persona/her 分层 §5） | T-17；现有四特效盘点（`her-pack-camera-effects.md` 素材表） | 特效创意建议 |
| `voice-bind` | 音色挑选：候选池 → T-08 探测 → voice_ref 建议（含回退链） | T-08；voice_ref 对外口径【F-UPSERT】 | 音色与人格匹配建议 |
| `pack-qa` | 打包+质检汇总：T-11→T-10→T-13→T-14，汇总证据包，列出缺项 | T-10~T-14 | 证据解读、缺项说明 |
| `release-prep` | 发布包组装：payload+审批单+回滚目标；**不执行发布**（发布=人经 T-18） | T-12、`ca_prod_approval` | 发布说明、变更摘要 |

**不做成 skill 的（agent 自由编排）**：任务分解顺序、失败后的下一步建议、跨阶段
沟通措辞。MVP 用**单协调 Agent**（不拆多岗位），拆岗条件按可行性 spec §6/§12 P3
【已定】：输入输出接口稳定且有基线数据后才拆。

---

## 5. 质量门

四道门，全部**确定性检查优先**；agent 只能汇总解释，不能以文字判断覆盖检查结果
（可行性 spec §6/§7【已定】）。门名进 `ca_prod_approval.gate`。

### G-A 契约门（自动、硬）

`validate_asset_pack`（T-10）+ `validate_payload`（服务端现成【F-UPSERT】）。
目标：**端上 `CharacterAssetPackStore.install` 必然成功的包才允许发布**。这是
hermes 产线与播种链共同的最低线——发布后客户端装不上 = 产线事故。

### G-B 模型规格门（自动、数值待定）【建议 N8】

`validate_model_specs`（T-14）产 metrics，门配置（yaml，随检查器版本固定）判定：

| 指标 | 口径 | 数值 |
|---|---|---|
| 纹理页尺寸/页数 | 逐贴图 `width×height`、总像素 | 待定：以 ATRI（现役已验收）与首个原创角色实测盘点定带，P0-03 回填；先设绝对硬顶：单页 ≤2048×2048（Cubism 常见上限）、总像素不超已验收基线 2 倍 |
| 包体积 | pack 总字节 | 硬顶 = 端上 `MAX_BYTES`（100MB，F-PACK-CONTRACT）；软顶按 renderer 分档（P0-03） |
| ArtMesh/参数数量 | model3 解析计数 | 待定（盘点值 + 余量） |
| 面数（VRM/simple 3D 线） | mesh 三角面 | 待定；VRM 线 Tripo 产物 decimation 是必经工序（persona/her 分层 §6.2） |
| 锚点有效性 | `touch_zones`/effects 声明的锚点在模型声明范围内、坐标归一化 | 规则固定：锚点 id 必须在模型 manifest 声明的分区集合内——现在特效锚点是固定视口坐标（`her-pack-camera-effects.md` 盘点【事实】），产线包**不得声称骨骼跟随**除非该模型过了锚点验收（P1-04） |
| wardrobe 绑定合法 | 每个 binding 的 `verifiedFrom` 非空且对应已验证记录；`status!=active` 变体不进产物 | 规则固定（spec 单一事实源【已定】） |

### G-C 端上性能门（半自动，设备证据）

**per-frame 预算思路**【已定框架：persona/her 分层 §5 预算表】：形象进程内存增量、
冷启动到首帧、帧时间 P50/P95、同屏特效并发、包体积/下载流量——结构固定，数值
P0-03 基线实测后定【已定，不虚构】。产线接法（N9）：

- 每个 pack 的 G-C 产物 = `perf_evidence` artifact（T-16）：中位设备型号、
  构建 commit、包 hash、五个指标实测值；
- 证据采集 harness 属客户端任务（Android 第二刀配套），产线只消费证据；
- 设备窗口由协调会话独占（执行手册第 4 条【已定】）——产线的 M0/M1 demo 用
  「协调会话跑 harness」的人工步骤闭合，不算产线自动能力。

### G-D 运行时/人工验收门（人工，签核）

RUNTIME_QA（真实 Cubism runtime 显隐/遮挡/动作逐项验收，可行性 spec §7.2.9【已定】）
+ HUMAN_RELEASE_REVIEW（视觉质量、原创性/授权、发布目标）。非发起人复核【已定 D-OUT】。
结构自检通过**永不**置 `runtime_verified=true`。

### 扩展性约束（门的一部分）

- **renderer 中立**：产线不为任何引擎特化数据面——renderer 是 `ca_her_pack` 列
  （D-HID）；工具链差异（Live2D exp3 / VRM mesh / Rive state machine）全部被
  T-11 的 pack 装配与端上适配器吸收。
- **her_id 命名 `<renderer>-<asset>`**（D-HID【已定已实现】）：产线生成 asset 名时
  必须同时满足它和 F-PACK-CONTRACT 的 `pack_id` 正则（两者字符集一致，`pack_id` =
  asset 名，N10）。
- **映射缺口【事实 F-ENGINE-ENUM → 待决 Q2】**：端上枚举无 VRM，`/v1/hers` 注释
  含 vrm。产线若产 VRM 包，端上第二刀须先扩枚举；在此之前产线对 VRM 包停在
  candidate 不发布。已登记 §8。

---

## 6. 用户自定义生产

### 6.1 边界（全部已定，这里只落实现位置）

1. **不做「上传任意模型」**【D-USER】；自由度 = 参数化模板槽（预绑定槽位/贴图），
   服务端生成填槽内容【已定】。
2. **用户 her renderer ∈ 非 Live2D**（自家分层 2D / Rive / VRM），直到 Expandable
   Application 书面许可落定【D-USER/D-LIC】。
3. 产物 = 一个 `ca_user_her` 实例，**走与系统 her 完全相同的下载/校验/安装链**
   （端上就是 F-PACK-CONTRACT 的 `CharacterAssetPackStore`，不加第二条路）【已定】。

### 6.2 `ca_user_her`（P1-01）如何接【建议 N11】

新迁移（实施期编号顺延，如 `0007_user_her`），与 `ca_her_pack` 分表分命名空间：

```text
ca_user_her
  user_her_id      -- 用户 her 稳定 ID；命名建议 `<renderer>-u<base32 ulid>`，
                      保证与系统 her_id 不相交（/v1/hers 不混入用户行）
  owner_user_id    -- 所有权；只有本人可见/可改（与 ca_her_pack「无 owner」对照）
  renderer         -- 列校验白名单 USER_HER_RENDERERS：{layered, rive, vrm}，
                      live2d 直接拒写（结构约束不靠流程承诺；放开条件=书面许可落定）
  pack_version / payload / status
      -- payload 契约与系统 her 同一份（复用 validate_payload + T-10）；
         status 多两态：draft → pending_review → published → retired（+审核拒绝）
  template_id      -- 所用模板（模板本体先存 payload.template，后议抽表）
  created_at/updated_at
```

- **审核闭环**：用户 her 默认私有；对外分享才过内容审核（复用 avatar_gen 的
  fail-closed provider 纪律与举报/删除流程，P4-03 范围外先行不做分享面）。
- **配额**：镜像 avatar_gen 的 429 QUOTA 模式（每日生成配额）【F-AVGEN】。
- **生成路径**：模板（仓库侧数据，预绑定）→ 用户选择 +（可选）源图 →
  `request_image_generation` 系服务端填槽（风格白名单扩大但要过许可审查；
  真人照片风格化只用 OpenRAIL 系检查点，persona/her 分层 §6.4【已定】）→
  T-11 装配 → T-10 门 → 写 `ca_user_her(status=pending_review)`。
- **与系统 her 的关系**：`ca_user_her` 是 `HerInstance` 的 her 覆盖（persona/her
  分层 §2 表【已定】）；绑定不进 `ca_character_her`（那是系统绑定表），端上按
  「用户 her 覆盖 > her 包默认 > persona 卡内 voice_ref」优先级消费（音色优先级
  已定【persona/her 分层 §2】，resolution 在服务端）。

### 6.3 产线与用户线的关系

Hermes 产线（§1–§5）产**系统 her**；用户线不走 Hermes——用户线是**参数化模板
+ 服务端确定性填槽**，无 agent 自由发挥（用户输入是不可信输入，注入面不进
agent）。两条线共用：asset pack 契约、G-A 门、安装链、`/v1` 摘要风格。这是
「模板边界内保质量」的产品护城河表述【已定，persona/her 分层 §6.3】。

---

## 7. 分阶段落地（每阶段有可跑 demo）

阶段对应关系：M0 是本文新增的「无 Hermes 先走通数据面」缓冲；M1=P0/P2-02；
M2=P1+P2-03/P2-04；M3=P2-04 完整发布面；M4=P1-01 用户闭环（可行性 spec §12、
执行手册 §5 的对齐不改变其门禁）。

### M0 · 数据面演练（脚本级，无 Hermes）

- 做什么：一个离线脚本（形态同 `tools/seed_her_packs.py`）用现有资产（linche/sudai
  素材或 ATRI 派生实验包）走 `build_asset_pack → validate_asset_pack →
  upsert(source="manual") → bind → invalidate`，产出真实可安装的一行 her 包。
- **demo 验收**：`/v1/hers` 可见新行；真机（协调会话装机）`CharacterAssetPackStore`
  安装成功并渲染；重跑脚本 `pack_version` 不动。
- 意义：先证「产线产物契约 ↔ 端上安装」闭环（F-PACK-CONTRACT 与 F-UPSERT 之间
  没有任何未验证假设），产线其余部分只是自动化。

### M1 · Hermes P0 验证（可行性 spec §12-P0 / P2-02）

- 做什么：固定 Hermes 版本 + `her-production` profile（§4 最小集：
  `brief-intake`+`pack-qa`）；控制面 API 起一个限权 task envelope，worker 内
  Hermes 调 T-01/T-02（MCP），产物回 artifact store。
- **demo 验收**（可行性 spec §12-P0【已定门槛】）：一次完整 staging run 可从 API
  创建、在 worker 执行、产物回到 store、杀 worker 后可重试且不重复登记；无未授权
  外部副作用；session/memory 不跨任务泄漏（P0 必须先验证该机制，不假设）。
- 失败处理【已定】：不可行则控制面与工具层不动，替换执行器（自建 loop 或方案 C）。

### M2 · 一套授权资产全流程（P2-03）+ 首次 `source=hermes` 发布

- 做什么：过权益的 brief → `brief-intake` →（概念图经 T-07 人工确认）→ 人工分层
  → T-01/02/03 → T-15（psd2live 或人工 Editor）→ T-13 → G-B → G-D → 非发起人
  复核 → `publish_release`（source=`"hermes"`，N12：`source` 列枚举已有
  `hermes`【F-HER-TBL】，首次使用即此）。
- **demo 验收**：从 brief 到发布可追溯（每 artifact 带工具版本+hash+审批链）；
  失败退回具体阶段不覆盖已验收版本；端上对账 `pack_version` 与 release 记录一致。

### M3 · 发布面完备（P2-04）

- 灰度字段、回滚目标、撤权演练、`retired` 路径与缓存失效（`HerCatalog.invalidate`
  进程级；多副本广播机制【待决 Q3】）。demo：坏包注入 + 回滚 + 撤权三演练通过。

### M4 · 用户自定义 MVP（P1-01 + §6）

- 做什么：`ca_user_her` 表 + 一个模板（非 Live2D，如 layered 2D 模板）+ 服务端
  填槽（复用 avatar_gen 骨架）+ G-A + 私有可见。
- **demo 验收**：非美术用户从选模板到端上看到自己的 her 全程 ≤ 分钟级交互（
  persona/her 分层 §7 存在性判据「非美术用户分钟级完成的产线」）；live2d renderer
  写入被列校验拒绝（负向用例）；用户 her 不进 `/v1/hers` 系统列表。

### 部署约束（各阶段一致）

- **禁止 Docker**（D-DEP）：一切新进程 systemd 单元 + 独立系统账户。
- 104 生产现形态【F-DEPLOY】：`companion-api.service` / `companion-voice.service`，
  api 监听 8081 经 nginx 反代（拓扑：api.ok123find.top → 8.217 nginx → 跨机代理
  → 104:8081；**8081 不得绑回环**）。
- 【建议 N13】产线控制面 API 首版并入 `companion-api` 进程（路由族 `/v1/production/*`，
  镜像现有路由鉴权风格），**不**新开 HTTP 服务；worker 独立：
  `companion-prod-worker.service`（Hermes 子进程由 worker 按任务派生，任务级
  临时工作目录、只读 skill 挂载、出站域名白名单——可行性 spec §10【已定】）。
- Cubism Editor/psd2live 执行器在受控图形工作站，不无头化承诺（可行性 spec
  §10/§14【已定】）。
- 生产库迁移经 alembic（现 head 序列到 0005）；M0 起的新迁移由实施任务提交，
  本文不建迁移。生产库执行归协调会话。

---

## 8. 决定 / 建议 / 待决 汇总

**已定（本文继承，不可由实施者擅改）**：D-B、D-SM、D-OUT、D-USER、D-LIC、D-HID、
D-DEP、D-PLAY；§3 权限口径（READ/AUTO/CONFIRM、危险默认关）；§5 各门的「确定性
检查优先、agent 不覆盖结果」纪律；G-D 人工验收与非发起人复核。

**本文建议（N 系列）**：

| 编号 | 建议 | 主要理由 |
|---|---|---|
| N3 | 控制面表进 companion 同库，`ca_prod_` 前缀，迁移 0006 起 | 发布写入点与 `ca_her_pack` 同事务边界；组件不增 |
| N4 | 队列用 Postgres 任务表 + `SKIP LOCKED` 租约 | 复用提醒调度的既有模式，不引入新组件 |
| N5 | artifact 存储复用 uploads 链路 + 私有目录 + 短期签名 URL | 少建一套签名/清理 |
| N6 | 产线中途不写 `ca_her_pack`；只在 publish 写 `published`，下架写 `retired` | `/v1/hers` 无文件兜底，库里即事实源 |
| N7 | 发布前跑服务端版 pack 契约校验（T-10） | 现 `validate_payload` 挡不住端上必拒的包 |
| N8 | G-B 门配置（yaml、随检查器版本固定）承载数值 | 数值必须可回填、可审计，不写死代码 |
| N9 | 每 pack 带 perf evidence artifact，缺证据 G-C FAIL | 预算表结构已定、数值 P0-03；证据是门不是装饰 |
| N10 | asset 名 = pack_id（两正则字符集一致） | 命名一套，杜绝 `<renderer>-<asset>` 与端上 pack_id 漂移 |
| N11 | `ca_user_her` 分表 + `<renderer>-u<base32>` 命名空间 + renderer 列白名单 | 系统/用户列表不混；Live2D 边界长在最靠内的写入口 |
| N12 | `source=hermes` 首次启用在 M2 | 枚举已在 schema；M0 用 `manual` 保持诚实 |
| N13 | 控制面 API 并入 companion-api（`/v1/production/*`），worker 独立 systemd | 组件最小；worker 才是隔离需求所在 |

**待决（需要用户/立项拍板，本文不装已定）**：

| 编号 | 问题 | 影响 |
|---|---|---|
| Q1 | 首个概念图/填槽图像 provider 及其许可、预算上限 | T-07/M4 的 CONFIRM 面（可行性 spec §16 同款遗留） |
| Q2 | 端上引擎枚举无 VRM（F-ENGINE-ENUM）：VRM 包发布前置=端上第二刀扩枚举 | M2 起 VRM 线停 candidate |
| Q3 | `HerCatalog` 进程级缓存在多副本下的失效广播方式 | M3 灰度/撤权演练内容 |
| Q4 | 产线 UI（工作台）范围：M1 用 CLI/API 驱动是否足够 | 可行性 spec P1 要求阶段看板；首版建议 CLI 起步 |
| Q5 | Expandable Application 书面许可跟进节奏 | 决定用户线 renderer 能否扩 live2d（D-LIC 法务项，非本文可决） |

---

## 9. 风险登记（增量，可行性 spec §14 之外）

| 风险 | 处理 |
|---|---|
| `her_id` 命名与 pack_id 约束由产线生成器保证，人工播种绕过 | T-10/T-12 在发布点统一收口；播种脚本只产 `{renderer,asset}` 桥形态不再新增 |
| Hermes profile skill 文档与工具契约漂移 | skill 引用工具名+版本；`ca_prod_artifact` 记工具版本，对账可追 |
| 端上 100MB/200 files 硬顶与 Live2D 高清纹理冲突 | G-A 硬顶前置：超限在产线拒绝并给 decimation/降页建议，不让端上安装失败 |
| 用户线图像生成的内容安全 | fail-closed provider + 风格白名单 + 成年设定默认（可行性 spec §11【已定】）；审核态 `pending_review` 默认不可见 |
| 生产库误写 | 产线对 `ca_her_pack` 的写只经 T-18；worker 数据库凭据无该表 UPDATE 权限（systemd 账户级隔离，实施期落地） |

---

*本文档由 worker 会话起草（2026-11-28）。并线与发布归协调会话；实施拆解对应
P2-01…P2-05 / P1-01 任务卡。*
