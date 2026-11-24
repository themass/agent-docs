# emit 框架与审计不变量（emit-framework）

2026-11-24 立。此前 64 个阶段 D 生成器（emit_v00x…v077）各带一份复制的机器活：
切片器、快照装载、幂等 INSERT、回滚枚举、既往域查重、二十来条审计断言。
本文是这些不变量的**唯一文档**；实现在
`content-agent/pipeline/data/chronology/emit_common.py`（唯一实现）。

**移植判据（一条）**：这件事与「这首诗的解读」无关，且已在多个生成器里复制过 → 进框架。
诗的特有物永远留在生成器里：切片、四层正文（BG/CLAIMS/CITATIONS/locator）、
该首特有负证扫描与入引硬卡、系年判决语、文件头注释。

**框架不放宽任何断言。** check_* 全部是把 v019–v077 里已经在跑的断言搬进函数；
每个生成器仍必须显式调用第 0 节的必跑项。移植的验收标准是**产物逐字节不变**：
emit_v077 移植后重跑，与已提交的 V077 SQL（24,138 B）及回滚（1,182 B）`cmp` 通过。

---

## 0. 每首必跑项（生成器 audit() 的最小集）

| 框架函数 | 断言的内容 |
|---|---|
| `check_slices` | 每枚切片①逐字节进入 SQL ②逐字节进入某条引文；字面量零反斜杠 |
| `check_not_reopen` | 判例在册关键语（各迁移句读式全引、署名行、耗尽句…）不得混入本迁移引文 |
| `check_shape` | background_line 形制（四句绝常规 1/1/1/1 顺次，其余须显式声明） |
| `check_bgline_count` | bg_line INSERT 中该 version 的行数 = 预期 |
| `check_sources` | 恰新建 N 枚 source；回滚恰删这 N 枚；复用的既有源零删除 |
| `check_zero_known` | 有意零 KNOWN 的迁移：SQL 无 `'KNOWN'` 字面量、claim 全 LIKELY |
| `check_pairs` | (claim_id,source_id) 主键文档内不重复；引文组数 = 预期 |
| `check_no_cast` | 零铸造纪律：不铸 written_during / time.span / event.name、零 relation 行、work 不做 claim 主语 |
| `check_no_textline_touch` | 不碰 poetry_text_line（SQL 与回滚都不出现） |
| `check_phrases` | 本首判决语（让渡形态/在册外零/存储面即定読面…）必须在 BG 正文出现 |
| `check_id_unique` | 文档内 (表,id) 不重复 |
| `check_widths` | id≤64 / slug≤120 / title≤200 / locator≤300 / excerpt≤500 |
| `check_idempotent` | 每条 INSERT 带 WHERE NOT EXISTS；版本账本带显式守卫 |

诗特有硬卡另写（V077 例：768 三件套入引、淚痕耗尽句零入引、只计数件零入引、
「同款装置」「不升格」locator 声明）。

## 1. 前提查重（Premises）

「这句话谁引过」是机器查的，不是记忆的：
- 域 = 既有 `V0*.sql` 中 `evidence_excerpt` 所在行含针的迁移集合（逐字引文都在一行上）；
  源 id 这类跨段事实用 `whole`（整文件含针）。
- 生成器必须以 `exclude_prefixes=('V0xx',)` 排除自己，否则自引用。
- 在册句前提：`must_be(label, needle, ['V0yy'])`——期望域恰是前人集合。
- 首引句前提：`must_be_first(label, needle)`——既往域必须为空，否则换句或降级。

V077 用它钉住：V018 两句读式/两页署名在先（零重开）、V056 泪痕句在先（让渡前提）、
source-quantangshi-768 未立（新建前提）、二十枚首引句零域。

## 2. 快照语料（Snap）与闭域档扫

- 语料在 `/tmp/src-dl`（fetch_*.sh 拉取，wikisource API + parse_api.py）。
- `Snap()` 装载即断言规模：ws 295 页 / 全唐詩 118 卷 / 通鉴 75 卷。规模变了 → 中止，
  因为所有「恰 N / 全零 / 唯某页」判决的地基就是语料闭域。
- `all_tj / all_qts / all_hist / all_ws` 是拼接域；`qts_where / tj_where / ws_where /
  line_pages` 返回含针页集合，调用方做恰 N 断言。
- 年标题窗口：`window(txt, needle, want)`——摘句前最近年标题必须含 want；
  窗口断言失效即中止（判决须重估），绝不在正文里写没核过的年份。

## 3. 切片纪律（slice_between）

唯一锚点闭区间：start/end 各恰一次、顺序正确、切片本身唯一，否则中止。
宁可生成失败，不能引错字。切片进 SQL 后由 `check_slices` 双向复核（SQL 面+引文面）。
V018 存储面重建比对（ws-raw 净文 ≡ 折叠 poem 面）留在生成器里——那是这首诗的判决。

## 4. SQL 六段与回滚（格式即事实）

段的顺序与格式（source → content → claims+selection → background → citations UNION →
background_line → schema_version）与全部已提交 V0xx 一致；框架的 `guard /
citation_union / bgline_union / version_row` 保证新迁移不再手抄格式。
只用 MySQL 5.6 子集写法：无 CTE、无 JSON、字面量禁反斜杠（`sql_s` 硬断言）。
**这条不是「因为服务器是 5.6」**——V001–V007 当年（2026-11-06）确实在 5.6.40 上执行，
但今天 `mysql.sspacee.com:6666` 实测已是 **8.0.46**（握手横幅；与 testserverV
`docs/game/README.md` 11-22 的 `SELECT VERSION()` 一致）。保留 5.6 子集的理由是
**前向兼容**：同一套脚本在两版上都能一次跑过，不必先探测版本再决定写法。
（另见 testserverV `docs/poetry/network-architecture.md`：那台库是**第三台机器**
`47.82.163.162`，既不是网关也不是应用机——迁移执行位置、备份、防火墙都挂在这一跳上。）

`rollback_sql(version_no, BG, CLAIMS, new_source_ids, header_lines)` 按 id 全枚举删除，
顺序 claim_selection → citation → background_line → background → claim → content →
新建 source → 账本。既有源绝不入删除列表（`check_sources` 反向断言）。
用户手工在已备份的目标库执行；生成器从不连库。

## 5. 新诗接入流程（扩展 recipe——这是框架存在的理由）

V078《春思》起，每首新诗只写四样：

1. **判断**（docstring）：这一新的在册形态是什么、与哪些判例接续。
2. **切片+快照断言**：`Snap()` + `slice_between` + 该首负证档扫（用 SNAP 语料与 where 助手）。
3. **四层正文**：BG / BG_TITLES / BG_SUMMARY / CLAIMS / CITATIONS / BG_LINES / source 行。
4. **audit()**：第 0 节必跑项 + 该首特有硬卡 + 前提查重（Premises）。

骨架约 400–600 行（V077 移植后 704 行，其中判断性注释与硬卡占大头；机器活零行）。
新形态族（如同题三诗、新挂法）进来时：生成器加硬卡；只有当同一断言在 ≥3 首重复出现，
才提升进框架——框架 growth 跟判例走，不预先抽象。

## 6. 旧生成器

v001–v076 不回头改（已提交 SQL 是事实，重生成必须逐字节一致才允许动它们的脚本）；
新首一律走框架。emit_v019 的 slice_between/sql_s/join 与框架版逐字节同义，
旧脚本继续 import 它，不产生行为分叉。
