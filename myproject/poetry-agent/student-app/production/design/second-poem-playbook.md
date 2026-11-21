# 第二首诗复制指南(以《静夜思》为演练)

- 日期:2026-11-07;状态:**方法验证稿**。《静夜思》的全部内容是 mock(草稿/待核),不是可上线内容。
- 目的:验证"做下一首诗的内容、审核和工程流程是否已经清楚",分清哪些能复用、哪些必须逐首创作、哪些是别的目录写死了《春望》。
- 原则(沿用基线 §5.1):**不给每首诗编一个确定的创作故事**。背景不可考的诗,要能表达"不可考",而不是被逼着编场景。

## 1. 每首新诗的步骤清单

| # | 步骤 | 输入 | 输出 | 复用还是逐首 |
|---|---|---|---|---|
| 1 | 确认底座事实(只读) | 内容底座已发布的 work/text_version/claim | 事实夹具(真实,不是 mock) | 复用流程;内容逐首 |
| 2 | 写 `tasks/<poem>/demand.json` | 诗句、vars(体裁、字音说明、音色)、holds、场景要素结论 | 需求文件 | **逐首** |
| 3 | 写剧本骨架 `tasks/<poem>/script.*.json` | 底座 id、台词与依据 | 剧本(编译器输入) | **逐首**(台词与依据) |
| 4 | `gen <poem>` | demand + kinds.json | `tasks.json`、`INDEX.md`、`sheets/`(不冲掉 state.json) | 复用 |
| 5 | 逐条处理 holds | 内容负责人的定稿 | 删 hold 字段后重新 gen | **逐首**(人) |
| 6 | 占位素材生成 | 任务单的 brief | `inbox/<id>/` | 通用脚本复用(gen-text / gen-audio);**场景几何逐首写** |
| 7 | `placeholder <poem>` 机检并登记 | inbox | `published/` + `registry.json` | 复用 |
| 8 | `bundle-refs <poem>` | 登记簿 | `published/bundles/<poem>.assets.json` | 复用 |
| 9 | `compile-check <poem> [facts]` | 剧本 + 登记素材 + 事实 | `/tmp/qj-<poem>/`(只读检查) | 复用 |
| 10 | 生产闸门 | — | `bundle-refs <poem> --channel production` 必须拒绝占位 | 复用 |
| 11 | 人工验收、派发、发布 | 任务单的验收清单 | `PUBLISHED` | 复用流程;人逐首做 |

**单独一条**:角色(若该诗有"见"这一步)。杜甫角色是逐人的(`gen-character-dufu.mjs`),不要因为复用流程就复用角色。《静夜思》没有人物,所以没有 `meet` 步骤、没有角色任务。

## 2. 《静夜思》演练中每一步的手工干预(按原因分类)

分类:**A 写死《春望》**(工具或契约把春望当默认)、**B 契约不够表达**(规则或格式无法说清新诗的情况)、**C 本来就该逐首**(创作判断)。

### 2.1 我的工具里写死的,已修(有 diff 证据,见 §5)

| 位置 | 原来 | 改成 |
|---|---|---|
| `tools/lib/tasks.mjs` 与 `specs/kinds.json` | 类型模板写死"律诗""『胜』shèng""春望八句全覆盖" | 模板用 `{form}`、`{polyphone_note}`、`{glyph_coverage}`,值来自 `demand.vars`;缺省取 `template_defaults`。《春望》把原文搬进 vars,输出逐字不变 |
| `tools/lib/tasks.mjs` | 任务的 constraints 无法按诗调整(例如四句诗的诵读时长下限) | 任务可写 `constraints.<role>`,浅合并进同角色的交付物约束 |
| `tools/prod.mjs report` | 无参数时只看 `chun-wang` | 无参数列出 `tasks/` 下全部诗 |
| `tools/prod.mjs gen` | 没有跨诗的 id 检查(inbox 与 published 是按 id 平铺的全局空间) | 与其他诗的任务 id 冲突则报错 |
| `tools/prod.mjs bundle-refs` | 没有生产渠道开关 | `--channel production`:含占位或缺素材即失败 |
| `tools/prod.mjs` 新增 `compile-check` | — | 合成候选 bundle 写到 `/tmp/qj-<poem>/`,交 A 的编译器和校验器只读检查 |
| `tools/gen/gen-text.mjs`、`gen-audio.mjs`(新增) | 原脚本名与内容都带 chun-wang | 通用版,按 `<poem>` 参数运行;春望的历史脚本保留不动 |

### 2.2 本来就该逐首创作(不是工具问题)

| 步骤 | 为什么逐首 |
|---|---|
| 场景几何(`gen-jing-ye-si-scene.mjs`) | 画什么由诗句字面决定,不能复用春望的远山城郭 |
| 台词与依据、旁白文本 | 每首的解读不同 |
| `demand.vars` 的音色选择 | 音色是对内容的判断 |
| 场景要素表 / 禁止出现项 | 每首的"不能画什么"不同;《静夜思》的"床"就是例子 |
| 角色与其 bible | 人物是逐首的 |
| 诗句版本选择 | 课本用哪一版,是内容判断 |

### 2.3 契约不够表达(B 类,我记录,不改他人的契约)

这些是《静夜思》暴露的真正难点:

1. **"背景不可考"只能勉强表达。** 现有 R6 规则要求:引用了 `unknown_date_ids` 的 id 时必须有 `unknown_dates_notice`。它能说"时间不确定",但**不能说"背景不展示"**。我用 `coverage_notice` 写了"不展示,不代表没有",这是文字约定,不是结构化字段。
2. **解读型台词没有合法的依据类型。** R3 要求 INTERPRETATION 台词绑定一个 `claim_id`,并且该 claim 必须"有已核查引文(VERIFIED source + real locator)"。《静夜思》的 "疑是地上霜" 这类解读,依据是**诗句本身**,没有外部出处。契约只有"claim"一种依据,于是要么编一条假出处,要么规则拒绝。**最需要扩展的是:依据类型增加 `text`(依据作品原文的某一句)。**
3. **多版本文本无处表达。** `text_version` 只有一个 id,`lines` 只按 `line_seq` 存一份。"床前明月光 / 床前看月光"之类的版本差异,契约里没有位置。当前做法是只用一种版本,并在 holds 里写"版本待核"。
4. **"没有见这一步"被当成缺陷。** R0 对没有 `meet` 步骤的 bundle 发出警告。《静夜思》没有可靠的"此时此地的诗人",不见是正确的;规则应允许声明"该步骤有意省略"。
5. **`hold` 没有结构化状态。** 暂缓派发的原因只存在 `demand.holds` 里,bundle 与登记簿都看不到。这不是契约的一部分,但如果要让 B 的前端标注"这一课还没定稿",需要进契约。

### 2.4 写死《春望》的其他目录(需要所有者处理)

以下是我全仓库检索得到的结果(grep `chun-wang|春望|dufu|杜甫`,排除 node_modules、dist、测试)。**我没有改任何一处**,只写建议。

#### 给 content-studio(任务 A,目录 `content-agent/pipeline/`)

| 位置 | 写死的内容 | 建议修改 |
|---|---|---|
| `tools/scene-compiler/compile.mjs` 第 9、22 行 | 默认 `sample.chun-wang.json` 与 `facts.chun-wang.json` | 去掉默认值,`--script` 与 `--facts` 必填;或改为"按诗 id 查找" |
| `tools/scene-compiler/fixture-facts.mjs` | 默认路径指向春望;**不带 `--out` 时会覆盖 `contracts/facts.fixture.json`**;并且把**所有被引用的 claim 都标为已引用**(`cited_claim_ids`),使 R3 的引文检查形同虚设 | 默认输出改到临时目录;`cited_claim_ids` 保持为空,让 R3 如实拦截;夹具只保留 id 的发布状态 |
| `tools/scene-validator/validate.mjs` | 无论传入什么 facts 都打印 `facts: "from base"` 与 `COMPILES`(即使是 fixture) | 根据 facts 的 `generated_by` 字段(是否含 FIXTURE)如实标注来源 |
| `tools/scene-validator/rules.mjs` 顶层 | 模块顶层读取 `process.argv`,无参数时 `process.exit(2)`,**不能被 import** | 把 CLI 部分移到 validate.mjs,rules.mjs 只导出 `checkRules` |
| `tools/scene-validator/rules.mjs` R0 | 没有 meet 步骤就警告 | 允许 `steps[i].omitted: true` 或在 script 声明 `omitted_steps` |
| `contracts/bundle.schema.json` | `kind` 枚举缺 `subtitle`;`level` 枚举缺 `L0`(而样例 bundle 与 Java 都用);`steps[].layers[].lines[].basis` 只允许 claim | 补 `subtitle`、`L0`;`basis` 增加 `text` 分支(依据作品原文某句) |
| `tools/scene-validator/export-preview.mjs` 第 5 行 | 写死 `work-chun-wang`、`text-chun-wang-draft` | 从参数读取 |
| `tools/scene-validator/preview-content.sh`、`gap-report.sql`、`facts-from-db.sh` | 整段 SQL 写死春望的 id | 参数化;gap-report 的"春望缺口"改为通用的"剧本缺口" |
| `tools/agent-draft/plan-poem.mjs` 第 5 行 | 只是用法示例,不影响运行 | 改注释 |
| `tools/dev/smoke.sh` 第 7 行 | 冒烟用的 payload 写死春望 | 参数化 |
| `tools/dev/check_profile.py` 第 535 行 | `"chun-wang" in body` 决定是否走快照 | 改为读取配置,不靠字符串匹配 |
| `scene-runtime/scripts/verify.ts`、`verify-shell.ts` | 读取 `sample.chun-wang.json` | 参数化(B 那边也有同样的副本) |
| `agent/poetry-domain-mcp/tests`、`agent/agent-bff/tests`、`agent/agent-worker/tests` | 测试里的春望 fixture | 不运行,仅记录;迁移时统一改为参数化夹具 |

#### 给 student-app(任务 B,目录 `student-app/`)

| 位置 | 写死的内容 | 建议修改 |
|---|---|---|
| `frontend/serve.mjs` 第 52、118–120 行 | 只对 `work-chun-wang` 返回 lesson、pack、works;其他 id 一律 404 | 从一个按诗 id 索引的目录读取 |
| `frontend/serve.mjs` 第 25 行 | `STUDENT_DEMO_MISSING=a-dufu-bust,a-changan-dusk` 是春望的素材名 | 演示参数化 |
| `agent/src/student_agent/sources.py` 第 57–62 行 | 只读 `sample.chun-wang.json`,且 `work_id != "work-chun-wang"` 直接报错 | 改为按 work_id 查找 |
| `agent/src/student_agent/evalrun.py` 第 26–28 行 | 默认评测集 `chun-wang.cases.jsonl`,`WORK_ID` 写死 | 从参数读取,每首诗一个评测集 |
| `agent/src/student_agent/reviewer.py` 第 25 行 | 人名、地名关键词表写死(杜甫、长安、鄜州…),用于审查台词是否越界 | 关键词表改为每首诗的数据文件;《静夜思》的关键词应是"床、窗、屋…" |
| `agent/tests/*`、`frontend/tests/*` | 测试夹具写死春望 | 不运行,记录 |
| `runtime/scene-runtime/scripts/verify.ts` | 同上(与 A 的副本相同) | 参数化 |

#### 给 Java(只读,`testserverV/vvv-poetry`,归 A 与用户)

本次没有检索 Java 的春望写死(它是数据层,规则是通用的 `PoetryMediaService`)。`PoetryMediaService` 的规则对《静夜思》登记是通用的,不需要改。**需要 A 或用户另外确认**:Java 侧的 `poetry_asset` 词表与 bundle schema 的 `kind`/`level` 不一致(`subtitle`、`L0`),这是 §2.4 第一节的同一个问题。

## 3. 生产闸门与登记簿

- 《静夜思》的 4 个占位素材登记后,`bundle-refs jing-ye-si --channel production` 拒绝(退出码 1),列出 4 项。
- 登记簿是单一来源:登记前后《春望》的 26 项逐项哈希相同(§5)。新诗只追加。
- 任务 id 与其他诗冲突时,`gen` 会报错(见 §2.1)。

## 4. 复制时的检查清单

- [ ] `demand.json` 有 `mock` 或正式标记;`vars` 填了音色与字音说明;没有写死任何具体诗的字样。
- [ ] 剧本的每条 INTERPRETATION 台词都说清依据;依据是作品原文时,契约需要 §2.3 第 2 条的扩展,否则**不能发布**。
- [ ] 写明"创作背景不可考"的诗:`unknown_date_ids` 包含作品 id,并有 `unknown_dates_notice`;`coverage_notice` 写明"不展示,不代表没有"。
- [ ] 没有指明时间、地点、天气、季节、人物心理的事实陈述。
- [ ] 场景几何逐首画,不沿用其他诗的图。
- [ ] 诗句版本只用一种,并在 holds 里写明版本待核。
- [ ] `gen` 后检查 `sheets/` 没有残留 `{变量}`。
- [ ] `bundle-refs --channel production` 对占位必须拒绝。
- [ ] `compile-check` 用真实事实,不是 fixture。fixture 的结果不能作为发布依据。
