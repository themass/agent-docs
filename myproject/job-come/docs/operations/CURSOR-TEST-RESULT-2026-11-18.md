# Cursor 测试结果 — 2026-11-18

## 结论

- 环境：本地（测前 HEAD `18a1da2` ≥`344acb2`；落盘时工作树已到 `c720cbf`，但 API 进程仍是 `02:06` 那次启动，未跟随重启）+ 生产 `https://jc.sspacee.com`（附录 A 后两套全跑）
- 本地后端启动：`2026-11-18 02:06:44`（晚于 agentkit wheel 重建 `11-17 23:36`）✓；测试期无 AttributeError
- Phase A 直传：本地/生产 **A1–A5、A7 全绿**；本地 A6 **PASS**；生产 A6 **N/A**（禁改 prod `.env`）
- Phase B 账本：本地/生产 **B1–B4、B6 PASS**；**B5 FAIL**（对抗输入未在入口以 4xx 拒绝）
- Phase C 性能：DeferredFeedback 时序本地/生产 **PASS**；本地 prod-build Lighthouse **Perf 100/97、TBT 4/0**；生产 quant **Perf 95 但 TBT 215** 未达标；两端 **`fetchpriority="high"` 均未出现在渲染 HTML**
- Phase D：本地/生产 **D1/D2 全绿**（超长姓名 → 422；优化稿无「6 年」）
- 新增缺陷：P0 0 / P1 3 / P2 1
- 证据根：`/tmp/jc-validation/2026-11-18-cursor-plan/`（生产子目录 `prod/`）

---

## 环境基线

| 检查 | 本地 | 生产 |
|---|---|---|
| HEALTH | 200 | 200 |
| WEB | 200 | 200 |
| SIGN（无 cookie） | 200（guest，见 A3） | 200 |
| `/guides/resume-quantification` | 200 | 200 |
| `/resume-template` | 200 | 200 |
| 后端进程 vs wheel `23:36` | 启动 `02:06:44` ≥ cutoff | 已部署（附录 A-1） |

---

## Phase A — 直传签发

| # | 本地 | 生产 | 备注 |
|---|---|---|---|
| A1 正向签发 | PASS | PASS | key 形如 `{jc/dev\|jc/prod}/uploads/usr_…/chat-image/…/{22}.jpg`；method PUT；headers 仅 Content-Type；maxBytes=8MB；连发 3 次 key 不同 |
| A2 Content-Type 绑定 | PASS | PASS | PUT jpeg 200；改 png / 无 CT → 403；unsigned GET → 403 |
| A3 guest | PASS | PASS | `gst_` 段；生产落在 `jc/prod/uploads/gst_anonymous/…` |
| A4 拒绝穷举 | PASS | PASS | evil/svg/pdf/9mb → 400+code；0/-1/缺字段 → 422；profile-source+pdf → 200 |
| A5 限流 | PASS | PASS | 第 16 次左右 429 `rate_limited`；账号 B 仍 200 |
| A6 降级 | PASS | N/A | 实际闸门是 `storage_remote_enabled`（`JC_S3_SECRET_KEY`），不是计划里的 `JC_STORAGE_REMOTE_ENABLED`。临时 blank secret → 503 `direct_upload_disabled`；multipart upload 仍 200；已恢复 |
| A7 无 complete | PASS | PASS | `/media/complete|bind|confirm` → 404（预期，非缺陷） |

---

## Phase B — 消息附件账本

| # | 本地 | 生产 | 备注 |
|---|---|---|---|
| B1 落库格式 | PASS | PASS | `storage_key`=`{prefix}/agent/…`，有 `size_bytes`/`download_url`；历史 JSON 中 `data:image` = 0 |
| B2 re-sign + TTL | PASS | PASS | 连拉两次 URL 不同且均可 200；等 910s 后再拉仍可开 |
| B3 可读 | PASS* | PASS* | API GET download_url=200；*浏览器截屏未作为硬门禁（见产物 C1 截图） |
| B4 跨用户 | PASS | PASS | B 直取 A 的 download_url → **403**；会话图片路由 → 404 |
| B5 对抗 | **FAIL** | **FAIL** | 见缺陷 P1-1 / P1-2 |
| B6 ×3 稳定 | PASS | PASS | 三轮均 200 + storage_key + 无裸 data URL |

### B5 明细（本地 vs 生产）

| 输入 | 本地 HTTP | 生产 HTTP | 是否落库 |
|---|---|---|---|
| 单附件 >8MB | 200（空/流式） | 200 | 未落库 |
| 4 张合计 >24MB | 200 | **413 nginx** | 未落库 |
| 非 base64 / 空 / html mime | 200 | 200 | 未落库 |
| SVG 字节伪装 `image/jpeg` | 200 | 200 | **已落库**（mime=jpeg，size≈46） |
| 真 GIF | 200 | 200 | 落库 gif（可接受） |
| 语音+照片同条 | 200 | 200 | 落库（正例） |

计划期望「全部 4xx、绝不 5xx」。现状是多数对抗输入在入口仍 200（SSE 先开），超大包依赖 nginx 413；伪 jpeg SVG 被当成图片写入账本。

---

## Phase C — 前端性能

| # | 本地 | 生产 |
|---|---|---|
| C1 DeferredFeedback 时序 | PASS（load=0，≥3s=1） | PASS（load=0，≥3s=1，可点） |
| C2 Lighthouse `/guides/resume-quantification` | Perf **100** / TBT **4ms** | Perf **95** / TBT **215ms**（TBT 超标） |
| C2 Lighthouse `/resume-template` | Perf **97** / TBT **0** | Perf **97** / TBT **19** |
| C2 `fetchpriority="high"` | **FAIL** | **FAIL** |
| C3 `pnpm`/`vitest` | PASS | PASS（同仓单测） |

说明：

- 源码 `resume-template/page.tsx` 对首图写了 `priority={index === 0}`，但 SSR HTML 的 `<img>` **没有** `fetchpriority="high"`（首图甚至没有该属性；仅 webpack preload 链路上出现 `fetchPriority="low"`）。按计划字面断言记 **P1-3**。
- 生产 quant TBT=215 > 100，相对修前基线 1600ms 已大幅改善，但仍未过计划门槛 → **P2-1**。
- 本地 C2 须 `rm -rf .next && pnpm build` 后在 **3010** 起 `next start`（`package.json` 的 `start` 写死 3000，且脏 `.next` 会 500）。

---

## Phase D — 指南 / SEO / P1 回归

| # | 本地 | 生产 |
|---|---|---|
| D1 指南 + 索引 + resume-template + sitemap | PASS | PASS |
| D2 超长姓名 >128 | PASS（**422** `string_too_long`，非 503） | PASS（同） |
| D2 不虚构「N 年」 | PASS（无「6 年」；硬事实 820/130/3000/5 保留） | PASS |

指南 slug（均 200）：`why-resume-rejected`、`resume-quantification`、`outsourcing-experience`、`mock-interview-preparation`、`backend-engineer-resume`、`product-manager-resume`、`data-engineer-resume`、`sre-devops-resume`、`sales-resume`。sitemap 含全部 + `/resume-template`。

---

## 缺陷清单

### P1-1 消息附件超限未在应用层以 4xx 拒绝（本地+生产）

- **现象**：单图 >8MB 的 `POST …/messages` 返回 **200**（SSE），而非 400/413/422；合计 >24MB 在生产被 **nginx 413** 挡住，本地 uvicorn 仍可能 200。
- **复现**：登录后对任意 session 发送 `data:image/jpeg;base64,…` 且解码后 >8MB。
- **影响**：客户端无法区分「已拒」与「流已开」；依赖网关限流不一致。
- **建议**：在解析 attachments 时同步校验 size/总数，失败直接 4xx JSON（人话文案），不要先开 SSE。

### P1-2 SVG 伪装 jpeg 可写入附件账本（本地+生产）

- **现象**：`mime_type=image/jpeg` + SVG 字节 → 200，历史中出现 `storage_key=…jpg`、`size_bytes≈46`。
- **复现**：见 Phase B `bad-svg_as_jpeg`。
- **影响**：账本信任声明的 mime，内容嗅探不足。
- **建议**：落库前做 magic-bytes / 白名单嗅探，不匹配则 4xx。

### P1-3 `/resume-template` 首图未输出 `fetchpriority="high"`（本地 prod-build + 生产）

- **现象**：源码有 `priority={0}`，渲染 `<img>` 无 `fetchpriority`。
- **复现**：`curl -s https://jc.sspacee.com/resume-template | grep -i fetchpriority`（仅命中 script preload 的 low，无 img high）。
- **影响**：计划验收项未满足；LCP 优先级声明未落到 DOM。
- **建议**：确认 Next 15 Image 在该布局下是否应产出属性；必要时显式 `fetchPriority="high"`。

### P2-1 生产 `/guides/resume-quantification` TBT=215ms > 100ms

- Perf 已到 95，相对基线 72/1600 明显好转；仍差计划 TBT 门槛。

---

## 测试缺陷（不算产品）

1. **A6 环境变量名**：计划写 `JC_STORAGE_REMOTE_ENABLED`，代码闸门是 `JC_S3_ACCESS_KEY`∧`JC_S3_SECRET_KEY` → `storage_remote_enabled`。本轮按真实闸门测并恢复密钥。
2. **D2 状态码**：计划写 400，实现为 **422**（Pydantic `string_too_long`）。语义正确（校验错误、非 503），按通过记；计划可改文案为「4xx」。
3. **本地 Lighthouse**：脏 `.next` / `start` 端口写死 3000 会导致误报 500；需干净 build + `next start --port 3010`。
4. **C1 脚本**：从 `/tmp` 直接 `import playwright` 会丢 `node_modules` 解析；须在 `frontend/web` 目录执行。

---

## storage_key 清单

### 本地（仅 `jc/dev/`）— 28 个

完整列表：`/tmp/jc-validation/2026-11-18-cursor-plan/all-storage-keys-local.json`

前缀分布：`jc/dev/uploads`（签发/限流）+ `jc/dev/agent`（聊天 offload）。

### 生产（仅 `jc/prod/`）— 28 个

完整列表：`/tmp/jc-validation/2026-11-18-cursor-plan/all-storage-keys-prod.json`

- 全部前缀 `jc/prod/` ✓（无串到 `jc/dev/`）
- 主体为测试账号 `usr_ebidh236m6tgbrvn` / B 账号限流对照 / guest `gst_anonymous`（A3 必测）
- 聊天 offload：`jc/prod/agent/agsn_4xpsnuvelusuapkk/attachments/…`

presigned URL 已从结果 JSON 中截断；报告正文不收录完整签名。

---

## 产物索引

| 路径 | 内容 |
|---|---|
| `…/phase-a/a-results.json` / `a6-result.json` / `storage_keys.json` | 本地 A |
| `…/phase-b/b-results.json` / `b5.json` / `messages-1.json` / `storage_keys.json` | 本地 B |
| `…/phase-c/c1-result.json` / `c1-deferred.png` / `lh-*-scores.json` / `c-results.json` | 本地 C |
| `…/phase-d/d-results.json` | 本地 D |
| `…/prod/phase-{a,b,c,d}/…` | 生产对应产物 |
| `…/all-storage-keys-{local,prod}.json` | 合并 key 清单 |
| `…/summary.json` | 汇总 |

---

## 总表（一眼）

| Phase | 本地 | 生产 |
|---|---|---|
| A | PASS（含 A6） | PASS（A6 N/A） |
| B | FAIL（仅 B5） | FAIL（仅 B5） |
| C | FAIL（fetchpriority） | FAIL（TBT + fetchpriority） |
| D | PASS | PASS |

---

## 负责人复验与关闭（2026-11-18 晚，`b743e4b` + `e1998a4` 已部署生产）

| 缺陷 | 处置 | 关闭证据 |
|---|---|---|
| P1-1 超限附件 200+SSE | 校验提到路由体（SSE 头发出前 4xx JSON）；服务层原校验保留给其他调用方 | 生产实弹：9MB jpeg → **400 `attachment_too_large`**；合法 jpeg 仍 200+完整 done；拒绝请求历史零落库。单测 10 条双侧（含 8MB/24MB 的 `>` 边界） |
| P1-2 SVG 伪装 jpeg | `decode_data_url` 加 magic-bytes 嗅探（validate/offload 共用收口；未识别 mime 放行避免误杀冷门格式） | 生产实弹：svg-as-jpeg → **400 `attachment_rejected`** |
| P1-3 fetchpriority | 根因：next 15.5.25 `priority` 只发 preload link，**不给 img 写 fetchpriority**（核对已装 get-img-props.js 只透传不解默认）→ 显式 `fetchPriority={index===0 ? "high" : undefined}` | 生产 SSR：`<img alt="中文单页…" fetchPriority="high">` 实测存在 |
| P2-1 quant TBT 215ms | **未修**，保留待排期 | — |

部署插曲两则（对以后跑生产的人有效）：
1. 生产 clone 曾积累 **85 个 root 属主文件**（早前 root 跑 git 所致），web 用户 checkout 前端文件时 unlink 被拒、半途中断；已 `chown -R web:web` 修复。之前部署都 `--skip-frontend`，恰好绕开。
2. expect/SSH 会话里裸跑 `git log`/`git diff` 会进 pager 吞掉后续命令（假"已执行"）；自动化必须 `GIT_PAGER=cat`。

复跑本计划时，P1-1/P1-2 的期望值应更新为 **4xx JSON（非流）**：>8MB 与伪 mime 现在都在 SSE 打开前被拒；"绝不 5xx" 仍成立。
| D | PASS | PASS |
