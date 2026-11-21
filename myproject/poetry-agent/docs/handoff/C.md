# 交接 C:素材任务体系与 2D 角色

- 日期:2026-11-06;状态:里程碑 1–5 全部完成(占位素材已能被学生端消费;正式素材一件都没有)。
- 我只写了:`student-app/production/**`、`scripts/student-app-production/**`、本文件,以及 `Makefile` 末尾追加的 4 个目标。没有碰 git、数据库、Java、`content-agent/`、`student-app` 的其余部分。

## 1. 给 B:怎么消费

| 要什么 | 在哪 |
|---|---|
| 角色清单格式 | `student-app/production/contracts/character.schema.json` |
| 素材登记格式 | `student-app/production/contracts/asset-registry.schema.json` |
| 占位角色「杜甫」 | `published/characters/du-fu/manifest.json`(+ `layers/*.svg`、`still.svg`、`alt.txt`) |
| 全部已登记素材 | `published/registry.json`(26 项,全部是占位) |
| 给 bundle 用的素材引用 | `published/bundles/chun-wang.assets.json`(`assets` 的形状与 `bundle.assets[id]` 一致:kind/level/hash/files/fallback/rights/meaning) |
| 文件 | `published/` 下按 `uri` 相对路径取(`uri_root: "published/"`),CDN 前缀由 B 决定 |

### 1.1 角色渲染约定(`svg-layers`)

1. `layers[]` 是树:`group` 无文件只做变换;`svg` 图层的 `viewBox` 都等于画布(512×768),叠放无需换算坐标。同级按 `z` 升序;变换原点是 `pivot`(画布坐标),缺省取画布中心;子节点继承父节点变换。
2. 状态 `idle / talk / listen / sorrow / bow`。每个状态:`loop`、`fps`、`duration_ms`、`tracks[]`(`[毫秒, 值]`;`prop` ∈ translateX/Y、rotate(度,顺时针为正)、scale/scaleX/scaleY、opacity)、`show`/`hide`(进入状态时强制显隐)、`then`(非循环状态结束后去哪)、`transition_ms`(淡入)、`fallback_state`(该状态不可用或性能不足时降到哪,链最终到 `idle`)。
3. 口型不要求对齐:`mouth_mode: amplitude`。有音频振幅(0..1)就线性映射到 `mouth.layer` 的 `mouth.prop`(`mouth_open.scaleY` 从 0.1 到 1,`smoothing_ms` 平滑)。没有振幅源时播放 `talk` 里 `role: "mouth_cycle"` 的循环轨。`viseme` 预留,本版不用。
4. 眨眼在 `ambient.blink`(与状态无关,`bow` 期间抑制);reduced-motion 时关闭。
5. 降级:`degrade.still.file`(静帧)→ `degrade.text_alt`(文字)。`reduced_motion_state` 只显示该状态第 0 帧。
6. `depiction.declared_as` 恒为 `DRAMATIZATION`,`depiction.notice` 是界面要随角色显示的那句话。`placeholder.not_for_release=true` 的素材,非生产渠道请显示「占位」角标。
7. `anchors`:`feet`、`head`、`mouth`、`speech_bubble`(气泡挂靠点)。

**待 C 确认的字段(B 之前列的)**:全部已定,没有"待确认"项。唯一仍开放的是 `viseme` 的口型表格式(本期不用,没有设计)。

### 1.1b 参考播放器(新增,B 可直接拷贝)

`student-app/production/reference-player/`:
- `core.mjs`:不碰 DOM 的纯函数 + `CharacterPlayer`(采样、叠加规则、变换顺序 translate→rotate→scale、状态过渡、fallback 链、reduced-motion、眨眼、振幅嘴)。**它是 manifest 语义的唯一参考实现**;与 schema 文字描述不一致时以它为准,发现错误请在 handoff 里报告,不要各改各的。
- `dom.mjs`:`mountCharacter(host, manifest, layerSvgText)`,把图层装配成一个 `<svg>`,`apply(frame)` 逐帧更新。
- `build-preview.mjs`:生成单文件预览页 `/tmp/c-preview/character-preview.html`(内联全部资源,可 `file://` 打开)。默认是交互预览;`?sheet=1` 是联合表(每个状态 4 个时刻 + 眨眼 + 三档嘴部振幅 + reduced-motion + still)。

用法:`node reference-player/build-preview.mjs`,再用浏览器打开输出文件。

关键语义(B 重写时务必一致):
1. 同一图层同一属性多条轨道:平移/旋转相加,缩放与 opacity 相乘。
2. 状态切换:对旧姿态做快照,在 `transition_ms` 内线性过渡到新姿态;可见性(show/hide、眨眼、嘴形)不过渡,切换即生效。
3. `amplitude` 为数值 → 嘴由 `mouth` 配置接管并忽略 `role: mouth_cycle` 轨;`undefined` → 循环嘴动;`null` 或 `mouth_mode: none` → 嘴不动。
4. **正面视角没有"前倾"**:行礼和低头用 `translateY + scaleY`(压缩)表达。我先用旋转做过一版,在 Chrome 里看是侧倾,已改掉。

### 1.2 登记簿的 26 项(降级链)

| 链 | 说明 |
|---|---|
| `a-dufu-bust`(L3)→ `a-dufu-still`(L1)→ `a-dufu-text`(L0) | 角色 |
| `a-changan-dusk`(L1,视差 5 层 + poster)→ `a-changan-dusk-text`(L0) | 场景;`render: "parallax"` |
| `a-chang-an-map`(L1)→ `a-chang-an-map-text`(L0) | 示意地图 |
| `a-recite-demo`(L2)→ `a-recite-demo-subtitle`(L0) | 诵读示范(say 合成,韵律不可信) |
| `a-nar-{arrive-scene,arrive-city,arrive-world,arrive-person,meet-dufu,return-world,return-person}`(L2)→ 同名 `-sub`(L0) | 旁白/杜甫台词,文本逐字取自样例 bundle |
| `voice-dufu-1`(L2)→ `a-recite-demo-subtitle`(L0) | 音色档案 + 试听,和样例 bundle 的 fallback 一致 |
| `a-sfx-birds`(L2)→ `a-sfx-birds-text`(L0) | 鸟鸣(P2,bundle 尚未引用) |

- 总体积约 494 KB(L0 1.9 KB、L1 95 KB、L2 376 KB、L3 21 KB),远低于首场景 8 MB 预算。
- **旁白/台词/字幕那 14 项当前样例 bundle 没有引用**。`chun-wang.assets.json` 的 `usage` 给出了每个素材应挂在 bundle 的哪个位置(如 `steps[1].layers[0].lines[0]`),但 bundle 里没有 `asset` 字段指向它们。要不要在 lines 上加 `audio` 引用是 A/B 的契约决定,我没有改 bundle。
- 视差:`files.json` = `parallax.json`(层序、`depth`、`max_shift_pct`、`drift`)、`files.poster` = 合成静帧(reduced-motion 与弱网用)、`files.layers[]` = 5 个透明 SVG。

### 1.3 与现有契约的不一致(我没有改它们,请对应方处理)

1. **bundle schema 的 `kind` 枚举没有 `subtitle`,`level` 枚举没有 `L0`**,但样例 bundle 自己用了 `subtitle`/`L0`,Java 也要求 L0 作为降级地板。`chun-wang.assets.json` 里 L0 素材就是 `kind: subtitle, level: L0`,按现行 bundle schema 会校验失败。(B 与 A 的两份 `bundle.schema.json` 需要同步修改。)
2. **样例 bundle 的 `a-changan-dusk`(L1)降级到 `a-changan-dusk-mini`(L1)是同级降级**,Java `createAsset` 会拒绝("fallback must be a strictly lower level")。我的处理:mini 不是独立资产,而是同一资产的变体文件;降级链改为 L1 → L0 文字卡。`gen` 会持续打印这条警告。
3. **Java 词表没有 `L1.5`、`parallax`、`frames`、`scene3d`**。登记簿只用 Java 词表:视差登记为 `illustration` + `render: "parallax"`,等级 L1。
4. **uri 约定不同**:样例 bundle 写 `assets/dufu/dufu.moc3`;登记簿 uri 相对 `published/`(`characters/du-fu/manifest.json`)。
5. **`content-agent/pipeline/tools/scene-validator/rules.mjs` 号称"importable",但文件顶层在没有命令行参数时 `process.exit(2)`**,import 它会直接退出进程。我因此在 `tools/lib/registry.mjs` 里独立复刻了 R4/R9/R10 与 Java 的规则,没有 import。这属于 A 的文件,只报告。
6. **样例 bundle 的 PERSON 台词写"他四十六岁",样本规格 §0 要求写"四十多岁"并标注待核**。已在对应任务的 `grounding` 里标出,录音前需要内容负责人定稿。

## 2. 目录与命令

```
student-app/production/
  contracts/   character / asset-registry / task / delivery / parallax / voice-profile 六份 schema
  specs/       kinds.json(11 种任务类型模板:规格+约束+人工验收清单)、state-machine.json(状态机)
  tasks/<poem>/ demand.json(人写的需求)→ gen → tasks.json(机器可读)+ sheets/*.md(人读)+ INDEX.md + state.json(动态状态)
  inbox/<task_id>/   交付落点(含 delivery.json)
  published/   assets/ characters/ resources/ bundles/ registry.json
  tools/       prod.mjs(命令行)、character-check.mjs、register-character.mjs、lib/、gen/(占位生成器)、tests/
  reference-player/  core.mjs、dom.mjs、build-preview.mjs(角色清单的参考播放器与预览页)
  design/      2d-character.md、offline-production.md
  reports/progress.md
```

入口(均在 `poetry-agent-platform/` 下):

```bash
make production-report                  # 进度报告
make production-check                   # 检查 registry.json
make production-gen                     # 重新生成任务单(不冲掉 state.json)
make production-regen-placeholders      # 重新生成并登记全部占位素材(约 13 秒)
./scripts/student-app-production/prod.sh <gen|list|state|check|publish|placeholder|registry-check|bundle-refs|report> ...
node student-app/production/tools/character-check.mjs <manifest.json>
node student-app/production/reference-player/build-preview.mjs   # 生成角色预览页
./scripts/student-app-production/prod.sh bundle-refs chun-wang --channel production   # 含占位素材就失败
```

状态机:`TODO → DISPATCHED → DELIVERED → AUTO_PASSED → HUMAN_ACCEPTED → PUBLISHED`,任一环节不通过 → `REJECTED`。机检不过的交付物到不了人工验收;验收人不能与交付人相同。完整流程见 `design/offline-production.md`。

## 3. 决定记录

- **hash**:多文件素材(角色、视差)的 `hash` = 文件索引(按 path 排序的 `path\tsha256\n`)的 sha256,`hash_scheme: files-index-sha256`;单文件 = 文件 sha256。满足 Java 的 12–64 位小写十六进制且全库唯一。
- **占位用正式 asset_id**,`placeholder.not_for_release=true`,`rights.license` 写"自有占位,不可上线"。对应任务保持 `TODO`,不进 `PUBLISHED`;真素材 `publish` 时以同一 id 覆盖。占位**不进入 Java**。
- **杜甫占位直接生成进 `published/characters/du-fu/`**(里程碑 1 为了让 B 立刻开工),没有走 inbox 流水线,因此它的三项登记没有 `task_id`;任务 `a-dufu-bust/-still/-text` 仍是 TODO,`placeholder_plan.strategy = existing`。
- **字体不进 `poetry_asset`**(Java 词表没有字体),`registry: false`,发布到 `published/resources/` 与 `resources.json`。目前没有字体素材。
- **暂缓派发 `dispatch_hold`**:没有依据就不派发(见 §5),`state … DISPATCHED` 会拒绝,`--override-hold --note` 可强行并留痕。这是我加的机制,目的是把"不写没有依据的历史事实"落到流程里。
- **杜甫台词与诵读占位音色**用 macOS `Grandpa`,旁白用 `Tingting`。只是占位,没有选音色的含义。
- **形象一律 DRAMATIZATION**,不依据任何画像;场景插画只画概括轮廓(山、城郭长墙与门楼块、近草),不画人物、旗帜、兵器、文字。
- **没有《春望》场景要素表**:docs 里只有设计文字,没有数据。所有创作说明都只依据诗句字面与 bundle 台词,器物/服饰/建筑一律写"待场景要素表"。
- 音效只保留鸟鸣(诗句"恨别鸟惊心"字面可落实),且定为 P2;没有加风声、战鼓、号角。
- **杜甫 manifest 改动**(播放器目视后):`sorrow` 改为下沉+压扁、`bow` 改为躯干压缩+头下沉(不再靠旋转);`text_alt` 去掉"黑色软帽、青灰长袍",只说抽象半身人物——外貌与服饰没有史料依据,不应写进会被读出来的替代文字。图里的帽子与长袍只是占位的几何形状。
- 没有 import 任何 npm 包;JSON Schema 用自己写的子集校验器(`tools/lib/jsonschema.mjs`)。

## 4. 已知缺口

- 角色动画已在 headless Chrome 里按确定性时钟渲染出联合表并目视检查(五个状态、眨眼、三档振幅、reduced-motion、still)。**没有做过的**:交互预览页的实时 `requestAnimationFrame` 播放、真机(iPad Safari、中端安卓)、长时间运行的帧率。
- 视差层的移动效果、poster 的实际观感只看过合成静帧(截图合格,但"城门"是个白色块,雾层把城墙压得偏淡,占位够用)。
- `viseme` 口型表未设计。
- 没有 `tsc`,所以没有写 TypeScript 类型定义;B 若用 TS 重写播放器,类型以 schema 为准。
- `not_for_release` 的拦截只做在 `bundle-refs --channel production`(含占位或缺素材就失败,已演练:当前 26 项占位被正确拒绝)。其他入口(例如直接读 `registry.json`)没有拦截。
- 未写把 registry 同步到 Java `createAsset` 的导入脚本(需要写接口授权;按约定不碰库)。
- `production/workflows/` 目录没建(没有 GPU,没有工作流)。
- 只有《春望》一首诗;`gen` 对 `tasks/<poem>/demand.json` 是通用的。

## 5. 需要用户做的(卡住的任务)

| 卡点 | 挡住 | 需要 |
|---|---|---|
| **场景要素表**(地点/季节/时段/天气/可见物件/禁止出现项) | `a-changan-dusk`、`a-chang-an-map`,以及角色服饰 | 内容负责人建表 |
| **台词定稿 + 引文核查**(claim 无可核查引文) | 7 条旁白/台词的录音 | 定稿并核查 claim |
| **课本版原文、注音、停顿**(尤其"胜" shèng) | 真人诵读示范 | 对照纸质课本 |
| 年龄口径(四十六岁 vs 四十多岁) | PERSON 旁白 | 定稿 |
| 角色 bible 定稿 + 美术风格参考 | 正式杜甫角色 | 见 `design/2d-character.md` §6 |
| 真人诵读录音 + 朗读人书面授权 | `a-recite-demo` | |
| 授权字体(诗句衬线体必需) | `res-font-poem-serif` | 许可原文 |
| **Live2D / Spine / lottie-web 的商用许可** | 外包角色路线 | **我没有核实,见 `2d-character.md` §9** |
| 音色选择与授权 | `voice-dufu-1` | |
| 验收人是谁 | 所有人工验收 | |

## 6. 汇报三段

### 6.1 已实际运行并验证

- `node --check`:`tools/**/*.mjs`(含 gen、tests、lib)全部通过;`bash -n`:`scripts/student-app-production/*.sh` 通过;6 份 schema 与 2 份 specs 均能被 `json.load`。
- `node tools/character-check.mjs published/characters/du-fu/manifest.json` → ok,20,946 字节(预算 204,800)。
- `node tools/prod.mjs gen chun-wang` → 28 个任务单;一次因 5 条 `creative_notes` 少于 8 字被 schema 拦下并修正(证明校验在起作用)。
- `./scripts/student-app-production/regen-placeholders.sh` 端到端跑通两次(第二次在把字幕函数拆到 `lib/vtt.mjs` 之后):23 个占位素材走完机检(格式、尺寸、大小、WAV/m4a 时长与采样率、VTT 时间轴、文字与脚本逐字一致、delivery.json 授权完整)并登记,0 失败;`registry-check` → 26 项 0 错误 0 警告(含 hash 唯一、降级链严格降层且到 L0、无环、文件 hash 与字节数与磁盘一致)。
- `prod.mjs bundle-refs chun-wang` → 26 项已登记、0 项缺失;`prod.mjs report` 生成 `reports/progress.md`。
- `make -n production-report production-check` 展开正确;`make check-layout` 退出码 0。
- 目视:`still.svg`(qlmanage 渲染)与 `poster.webp`(headless Chrome 栅格化 → cwebp)均已看过,形象/场景可辨认。
- 参考播放器:`build-preview.mjs` 生成预览页,headless Chrome 截 `?sheet=1` 联合表三次并目视;第一轮发现 bow 读成侧倾、sorrow 读成歪头、降级行格子过大,已修正并重新截图确认。修改后重新生成并登记杜甫(22,666 字节,`registry-check` 仍 26 项 0 错误)。
- `prod.mjs bundle-refs chun-wang --channel production` → 按预期失败(退出码 1,列出 26 项占位);不带参数 → 正常生成。
- 本机工具探测:ffmpeg/ffprobe、cwebp、macOS `say`(含 Tingting、Grandpa 等中文声音)、Chrome 均存在;`rsvg-convert`、ImageMagick、cairosvg 不存在。

### 6.2 已写但没有运行

- `tools/tests/registry.test.mjs`、`tools/tests/checks.test.mjs`(`node --test tools/tests/`):应满足——降级链严格降层/无环/L0 无 fallback、hash 唯一与索引 hash 与顺序无关、PNG/WAV 文件头解析、文件伪装被识破、SVG 脚本与外部引用被拦、viewBox 对画布、VTT 递增/重叠/超 34 字、交付缺 delivery.json/缺文件/禁止来源/空 evidence 被拦、视差引用的 poster 未交付被拦、状态机不能跳级且派发要 assignee、退回要原因、验收要验收人、字幕切分拼回与原文一致。
- `tools/tests/player.test.mjs`(`node --test tools/tests/`):应满足——采样边界与插值、循环状态首尾值相同、fallback 链到 idle、振幅映射与 `null` 静嘴、过渡混合、`bow` 播完回 idle、reduced-motion 不眨眼不切状态、眨眼被 `suppress_in` 抑制、切换后姿态处于旧值与新值之间。
- 命令的**负向路径**:`check` 对不合格交付自动 `REJECTED`、`state … DISPATCHED` 对 hold 任务的拒绝与 `--override-hold`、`state … HUMAN_ACCEPTED` 的"验收人≠交付人"、`publish` 的真素材入库与覆盖占位。这些只在代码里,没有拿真实交付演练过。
- `init-delivery`、`state`、`check`、`publish` 子命令没有被调用过(`list` 和 `placeholder` 跑过)。
- Java 侧:**我从未调用 `PoetryMediaService`**。登记簿与 Java 规则的一致性来自我对源码的逐条复刻,不是联调结果。

### 6.3 没有做到 / 需要用户做

见 §4 与 §5;其中最重要的三件:建《春望》场景要素表、台词定稿与引文核查、核实 Live2D/Spine 许可。**没有任何正式素材**,26 项全部是不可上线的占位。没有建 `production/workflows/`,没有字体,没有真人录音。需要用户合并的 pom 片段:无。需要用户执行的 SQL:无。Makefile 末尾追加了 `production-gen`、`production-report`、`production-check`、`production-regen-placeholders` 四个目标,未改他人的行。

---

## 第二阶段:《静夜思》方法复制演练(2026-11-07)

- 目的:验证素材任务体系能否表达一首**背景不可考、诗句有多版本**的诗,并分清哪些能复用、哪些是写死《春望》、哪些必须逐首创作。
- 完整指南:`student-app/production/design/second-poem-playbook.md`(含各目录的写死清单,按所有者分类,只写建议,我没有改别人的文件)。
- 所有 mock 内容在 `student-app/production/tasks/jing-ye-si/`,状态一律「草稿/待核」,诗句只写一种版本并注明待核,没有卷页或引文。

### 决定记录(第二阶段)

1. **不重跑《春望》的任何生成器**。只用已有的登记与文件哈希做比对,避免 `published_at` 等时间戳变化掩盖真正的改动。
2. **《春望》的类型模板差异用 `demand.vars` 还原**:把原先写死在模板里的"律诗""『胜』shèng""春望八句全覆盖"搬进 `vars`,输出逐字不变。这是最强的"没有回归"证据。
3. **新增通用脚本 `gen-text.mjs`、`gen-audio.mjs`,保留春望的历史脚本**,不让已登记的输出因重写而变化。代价是有少量重复,已在两份脚本头部注明。
4. **《静夜思》不设"见"步骤、没有角色任务**:没有可靠的"此时此地的诗人",不替它编一个。
5. **"背景不可考"用 `unknown_date_ids` + `unknown_dates_notice` + `coverage_notice` 表达**,不编造场景。这是契约的现有能力范围内最接近的做法,但仍不是结构化的"不展示"。
6. **text_version 的 hold 只挡真人诵读**,字幕和文字卡暂用 mock 的一种版本。这是我的决定:字幕与文字卡是降级终点,不能因版本待定而缺席。若内容负责人认为字幕也应等待定稿,改 `demand.json` 即可。
7. **compile-check 的候选 bundle 与 fixture 都只写 `/tmp`**,不写 A 的 `dist/`,也不改 `contracts/facts.fixture.json`。
8. 没有运行任何测试套件。`node --check`、`bash -n`、`make check-layout` 是静态检查。

### 工具修复(发现写死后直接修,我的目录内)

| 文件 | 修改 |
|---|---|
| `tools/lib/tasks.mjs` | 模板变量 `{form}` 等;按任务覆盖 constraints;`listPoems`、`takenElsewhere` |
| `specs/kinds.json` | 去掉写死的"律诗""春望八句";加 `template_defaults` |
| `tasks/chun-wang/demand.json` | 新增 `vars`、`regen`、`regen_note`(原有字段一字未改) |
| `tools/prod.mjs` | `report` 默认列出全部诗;`gen` 查跨诗 id 冲突;`bundle-refs --channel production`;新增 `compile-check` |
| `tools/gen/gen-text.mjs`、`gen-audio.mjs`、`gen-jing-ye-si-scene.mjs` | 新增,按诗参数化或为新诗写的几何 |

### 证据:《春望》输出不变

| 检查 | 结果 |
|---|---|
| 修改前后 `gen chun-wang`:`tasks.json` | `diff` 为空(IDENTICAL) |
| 同上:`INDEX.md` | `diff` 为空(IDENTICAL) |
| 同上:`sheets/` 目录 | `diff -r` 为空 |
| `tasks/chun-wang/state.json` | `cmp` 相同,未被冲掉 |
| 登记簿《春望》26 项逐项 SHA-256(登记前后) | 26/26 不变,0 缺失 |
| `published/` 中春望相关文件、`inbox/` 中春望文件的 SHA-256 | 全部一致 |
| `registry-check` | 30 项(26 春望 + 4 静夜思),0 错误,0 警告 |

### 证据:《静夜思》登记与闸门

- `gen jing-ye-si` → 4 个任务单;`placeholder jing-ye-si` → 4 项登记,0 失败;4 个新增条目。
- `bundle-refs jing-ye-si` → 4 项占位。
- `bundle-refs jing-ye-si --channel production` → **退出码 1**,列出 `a-jys-moonlight、a-jys-moonlight-text、a-jys-recite、a-jys-recite-subtitle`,且在写入文件之前拒绝。

### 证据:编译器只读检查(A 的 12 规则)

| 场景 | 结果 |
|---|---|
| 真实事实(mock 事实,全部未发布) | **BLOCKED**:R2 拦截 3 个未发布的 id;R3 拦截 2 条未发布、无可核查引文的 claim。拦截正确。 |
| 同上,换成 `fixture-facts` 生成的夹具 | **COMPILES**,但这是假象:fixture 工具把全部被引用的 claim 标为已引用,R3 的引文检查被绕过。**不能作为发布依据。** |
| 春望的真实事实(基线) | BLOCKED(R2 拦截全部未发布 id),与预期一致 |

### 12 规则对《静夜思》的表达结果

| 规则 | 结论 |
|---|---|
| R0 shape | 通过 |
| R0 step | **警告**:没有 meet 步骤。这是诗的性质决定的,规则应允许声明"有意省略"(§2.3 第 4 条) |
| R12 自由移动 | 通过 |
| R5 coverage | 通过(写明"不展示,不代表没有") |
| R1/R2 引用存在且已发布 | 合理拒绝(mock 未发布) |
| R7 注释来自底座 | 通过(无注释) |
| R6 未知日期 | 通过,但只能表达"日期不确定",不能表达"背景不展示"(§2.3 第 1 条) |
| R8 line 链接 | 通过 |
| R11 无堆砌 | 通过 |
| R3 依据 | **合理拒绝的一部分**:未发布的 claim 被拦是对的;但**解读型台词没有"依据是作品原文"的合法类型**,是契约缺口(§2.3 第 2 条) |
| R4 降级链与资产声明 | 通过(L0 为终点) |
| R9 hash、R10 rights/meaning | 通过 |

**结论**:规则基本合理。真正表达不了的是"依据是作品本身"和"多版本文本"两件事,都属于契约扩展,不是规则写死了春望。

### 发现写死《春望》的地方(所有者)

完整清单与建议修改见 `design/second-poem-playbook.md` §2.4。摘要:

- **content-studio(任务 A,`content-agent/pipeline/`)**:
  - `compile.mjs` 默认路径写死春望;
  - `fixture-facts.mjs` 默认路径写死、默认覆盖 `facts.fixture.json`,且把所有引用的 claim 标为已引用,绕过 R3;
  - `validate.mjs` 对 fixture 也标"from base";
  - `rules.mjs` 顶层读 argv 并 `process.exit`,**不能被 import**;
  - `bundle.schema.json` 的 `kind` 缺 `subtitle`、`level` 缺 `L0`,且 `basis` 没有"作品原文"分支;
  - `export-preview.mjs`、`preview-content.sh`、`gap-report.sql`、`smoke.sh` 写死春望 id;
  - `check_profile.py` 用 `"chun-wang" in body` 做判断。
- **student-app(任务 B,`student-app/`)**:
  - `frontend/serve.mjs` 只对 `work-chun-wang` 返回内容;
  - `agent/src/student_agent/sources.py` 只读春望样例,其他 work 报错;
  - `evalrun.py` 评测集与 WORK_ID 写死;
  - `reviewer.py` 的越界关键词表写死人名地名(杜甫、长安…),对《静夜思》无效;
  - `runtime/scene-runtime/scripts/verify.ts` 写死样例。
- **归我(已修)**:模板内容写死、`report` 默认只看春望、缺跨诗 id 检查。
- **Java(归 A 与用户,本次未检索)**:`poetry_asset` 词表与 bundle schema 不一致(`subtitle`、`L0`)。

### 1) 已实际运行并验证

- `node --check`:`tools/prod.mjs`、`tools/lib/tasks.mjs`、`tools/gen/gen-text.mjs`、`gen-audio.mjs`、`gen-jing-ye-si-scene.mjs` 通过。
- 《春望》`gen`(修改前后各一次)的 `tasks.json`、`INDEX.md`、`sheets/` 逐字一致(见上表)。
- 《静夜思》`gen`、`placeholder`、`bundle-refs`、`bundle-refs --channel production`、`registry-check`、`report`、`compile-check`(两种事实)全部按预期运行。
- 编译器与校验器只以 `--check-only` 或只读方式调用,未写 `dist/`。
- 生成的占位:`inbox/a-jys-*` 4 个,`main.webp` 1280×720、`mini.webp` 640×360 由 headless Chrome 栅格化后 cwebp 转换。

### 2) 已写但没有运行

- `tools/tests/` 下的测试仍未运行(按约定)。
- `gen-audio.mjs` 的 `constraints` 覆盖、`takenElsewhere` 的冲突分支、`fill` 的未知变量警告没有专门的负向测试。
- 没有对《静夜思》的 `check`、`publish`、`state` 做过负向演练。
- 《静夜思》场景图已目视检查(`main.webp` 1280×720):只有夜空、一轮月和地上的白,没有床、窗、屋或人,符合 `forbidden_elements`。`mini.webp` 只看了尺寸,未目视。

### 3) 没做到 / 需要用户做

- **需要内容负责人**:《静夜思》的诗句版本定稿;场景要素表(尤其"床"的所指);台词依据的扩展决定(见 §2.3 第 2 条)。
- **需要 A 处理的契约问题**:`bundle.schema.json` 补 `subtitle`/`L0`;`basis` 增加"作品原文"分支;R0 允许声明省略步骤;R3/fixture 的绕过。
- **需要 B 处理的写死**:见上。
- **需要你决定**:compile-check 是否只允许用真实事实(目前 mock 事实 → BLOCKED 是预期结果;fixture 结果我明确标注为不可发布依据)。
