# CURSOR-TEST-PLAN 2026-11-18：直传 B 步 + 消息格式 + 前端性能优化验证

- **状态**：待执行
- **下发对象**：Cursor（Playwright + curl + 脚本）
- **执行环境**：**本地 main 检出**（不是生产，原因见 §0.1）
  - API：`http://127.0.0.1:8001`（`./scripts/dev.sh` 打印的实际端口为准）
  - Web：`http://127.0.0.1:3000`
- **验收人**：项目负责人
- **前序**：`CURSOR-TEST-PLAN.md`、`CURSOR-TEST-RESULT-2026-11-15.md`、`QA-ROUND3-RESULT.md`

---

## 0. 这一轮测什么、为什么

11-15 那轮之后 main 上落了四批改动，全部**未经人手浏览器验证**：

| 改动 | commit | 验证现状 |
|---|---|---|
| 直传 B 步（sign/GC，ADR-011） | `344acb2` | 只有 19 个 pytest，没有任何真实 HTTP/浏览器验证 |
| 消息附件账本格式（offload→storage_key→re-sign 回放） | 早前 | 从未被端到端独立验证过 |
| 前端性能：DeferredFeedbackLauncher、LCP priority | `081e1de` | 只在 stubbed auth 的浏览器里看过一次按钮出现 |
| 五个角色长尾指南 + /resume-template | `081e1de` `962d7fb` | 没人用浏览器打开过 |

你的判断标准还是那一条：**不是"我跑通了"，而是"我能证明它坏了/它没坏"。** 每条断言都要正反两侧：既验证合法输入通过，也验证非法输入被拒。

### 0.1 为什么不是生产

已实测（2026-11-18）：`POST https://jc.sspacee.com/api/v1/media/sign` → **404**；`/guides`、`/guides/sres`、`/resume-template` → **404**；sitemap 里没有新页。生产停在旧构建，部署被 1Password SSH 卡着（负责人处理中）。**所有用例一律打本地 main 检出。** 若负责人中途说"部署好了"，把整份计划对生产重跑一遍，报告里生产/本地两套结果分开写。

### 0.2 环境基线（必须先做，不达标就停）

```bash
cd docs/myproject/job-come
git log --oneline -1          # 必须是 b20b15b 或之后（含 344acb2）
./scripts/dev.sh              # 前台跑，另开终端做测试
curl -s -o /dev/null -w 'API=%{http_code}\n' http://127.0.0.1:8001/health
curl -s -o /dev/null -w 'WEB=%{http_code}\n' http://127.0.0.1:3000/
```

```bash
curl -s -o /dev/null -w 'SIGN=%{http_code}\n' -X POST http://127.0.0.1:8001/api/v1/media/sign -H 'content-type: application/json' -d '{"scene":"chat-image","contentType":"image/jpeg","sizeBytes":100}'
```

`SIGN` 期望 **401/403**（未登录被拦，但路由存在）。出现 **404 说明构建不对，停止**。

⚠️ 本地 `.env` 配了真 TOS 凭据：聊天图片和直传测试会**真实写入 `sspacee` 桶的 `jc/dev/` 前缀**。这是预期行为（dev 前缀、GC 会清），但报告必须附**本次产生的所有 storage_key 清单**。

### 0.3 账号（双账号，同前序计划）

| 角色 | 用途 | 凭据来源 |
|---|---|---|
| 主账号 A | 主旅程 | `JC_E2E_EMAIL` / `JC_E2E_PASSWORD` |
| 普通用户 B | 跨用户隔离对照 | `JC_E2E_EMAIL_B` / `JC_E2E_PASSWORD_B` |

---

## 1. Phase A — 直传签发 API（B 步新代码，重点）

A1 **正向签发**（登录态 user）：`POST /api/v1/media/sign` `{scene:"chat-image", contentType:"image/jpeg", sizeBytes:50000}` → 200。断言：
- `objectKey` 形如 `jc/dev/uploads/<usr_id>/chat-image/<yyyy>/<mm>/<dd>/<22位keyId>.jpg`
- `upload.method=="PUT"`、`upload.headers` 恰为 `{"Content-Type":"image/jpeg"}`、`limits.maxBytes==8388608`
- 每次签发 keyId 不同（连发 3 次比对）

A2 **签名约束 Content-Type（B 步的关键决策，必须实测）**：拿 A1 返回的 `upload.url`：
- `curl -X PUT -H 'Content-Type: image/jpeg' --data-binary @照片` → 期望 200，再用返回 URL 中的签名参数 GET 回来字节一致
- 同一 URL、同一字节，**只把 header 改成 `image/png`** → 期望 **403**（Content-Type 在签名内）
- 不带 Content-Type → 期望 403
- ⚠️  presigned URL 是 bearer secret：不得出现在日志、报告正文、截图里（报告里引用时截断为 `…/<sig前4位>…`）

A3 **guest 也可签发**：无 cookie 请求 sign → 200，key 的 actor 段为 `gst_` 前缀。

A4 **拒绝路径穷举**（每条都要断言状态码和响应里的 `code` 字段）：

| 输入 | 期望 |
|---|---|
| `scene:"evil"` | 400 `invalid_scene` |
| scene=chat-image + `image/svg+xml` | 400 `unsupported_content_type`（SVG 不能混进图片白名单） |
| scene=chat-image + `application/pdf` | 400 `unsupported_content_type` |
| sizeBytes=9MB | 400 `size_over_limit` |
| sizeBytes=0 / -1 / 缺字段 | 422 |
| profile-source + `application/pdf` | 200（白名单正确分支，正反对照） |

A5 **限流**：同一账号 60 秒内第 21 次 sign → **429 `rate_limited`**；换账号 B 立即仍能 200（按 actor 限，不是全局限）。

A6 **降级通道**：临时把本地 `.env` 的 `JC_STORAGE_REMOTE_ENABLED=false` 重启 → sign 返回 **503 `direct_upload_disabled`**；前端聊天页仍能走 multipart 正常发图（降级可用，不是报错页）。测完恢复原值。

A7 **边界确认（不是 bug，写进报告即可）**：本阶段**没有** `/media/complete`，业务接口也**还没有**任何地方消费 `objectKey`（C 步才接）。所以你 PUT 上去的对象会停在桶里、签发行停在 ISSUED，等 GC 清。看到这些**不是缺陷**，但确认没有任何接口能"使用"这个 key。

---

## 2. Phase B — 消息格式与账本回放（用户可感知，重点）

用主账号 A 在聊天里发**照片**（手机原图 >1MB 和 <100KB 各一张）和**语音条**（>10s 一段），然后：

B1 **落库格式**：取该消息的会话历史 API 响应，断言附件行含 `storage_key`（`jc/dev/agent/…` 形状）、`size_bytes`、`download_url`；**payload 里不得出现裸 `data:` URL**（搜 `data:image` 必须 0 命中）。

B2 **回放签名轮换**：同一条历史连拉两次，两次 `download_url` 必须**不同**（re-sign），且**两次都能 200 打开**。等 15 分钟以上（TTL 900s）再拉一次，仍然能打开。

B3 **图片/语音真的可读**：浏览器里重开旧会话，照片渲染、语音能播。截屏。

B4 **跨用户隔离**：B 账号登录，直接 GET A 的 `storage_key` 对应下载 URL、以及 A 会话的附件图片路由 → 都不能拿到 A 的内容（403/404）。

B5 **对抗输入**（消息级，期望全部 4xx 带人话文案，绝不 5xx）：
- 单附件 >8MB；一条消息 4 张共 >24MB
- `data:` URL 非 base64 / 空 payload / `text/html` 伪 mime / 伪装 `image/jpeg` 的 SVG 字节
- 一张真 GIF、一张 HEIC（若设备有）：渲染 + 落库 mime 不串
- 语音条 + 照片同一条消息

B6 **稳定性**：整个"发图+发语音→重开会话→回放"旅程连跑 3 次，三次全部一致。任何一次不一致都是 P1 起报。

---

## 3. Phase C — 前端性能优化

C1 **DeferredFeedbackLauncher**：Playwright 打开 `/guides/resume-quantification`：
- load 事件时刻：页面上反馈按钮数 **0**
- 静置 ≥3s 后：按钮数 **1**，可点开
- DevTools 慢网（Slow 3G）下重复一次：按钮最终仍出现（load 兜底生效）

C2 **Lighthouse（本地 prod build：`pnpm build && pnpm start`）**跑 `/guides/resume-quantification` 与 `/resume-template`：
- 断言 Perf ≥ 95、TBT ≤ 100ms（修前基线 72 / 1600ms，写进报告对比）
- `/resume-template`：LCP 元素是首图且 `<img>` 带 `fetchpriority="high"`

C3 `pnpm test` 全绿（含 `tests/perf-budget.test.ts`）。

---

## 4. Phase D — 新页面与 SEO 完整性

D1 指南逐个打开：`/guides/why-resume-rejected`、`/guides/resume-quantification`、`/guides/outsourcing-experience`、`/guides/mock-interview-preparation` 及五个角色指南（准确 slug 以 `lib/seo/content.ts` 的 `ALL_GUIDES` 为准），加上索引页。逐页断言：200、标题正确、related guides 互链都能点开、`/sitemap.xml` 含全部页面。

D2 上轮 P1 回归：超长姓名（>128 字符）走简历编辑 → 400 校验错误（**不是 503**）；优化稿不再虚构"N 年"工龄（对照 P1-1 复现步骤）。

---

## 5. 产物与红线

- 结果写 `docs/operations/CURSOR-TEST-RESULT-2026-11-18.md`，格式沿用上轮：结论 → 分 Phase 明细 → 缺陷清单（P0/P1/P2 + 复现步骤）→ 测试缺陷（用例写错不算产品缺陷）→ 产物索引（截图、Lighthouse JSON、storage_key 清单）。
- **红线**：不碰生产环境；不改生产 `.env`；本地除 A6 临时项外不改任何 `.env`；本地不 `git commit/push`；bucket 里只允许 `jc/dev/` 前缀出现测试对象，报告列全清单；presigned URL 不落任何日志/报告/截图。

---

## 附录 A：2026-11-18 执行中更新（负责人批准后追加）

**A-1 生产已全量部署**（publish --deploy --restart 完成于 11-17 18:00 UTC，迁移 `026→027` 已执行）。§0.1 的"生产缺新功能"前提作废：**整份计划现在必须对 `https://jc.sspacee.com` 再跑一遍**，报告里本地/生产两套结果分开。生产基线 gate：

```bash
curl -s -o /dev/null -w 'sign=%{http_code}\n' -X POST https://jc.sspacee.com/api/v1/media/sign -H 'content-type: application/json' -d '{"scene":"chat-image","contentType":"image/jpeg","sizeBytes":100}'
curl -s -o /dev/null -w 'guides=%{http_code}\n' https://jc.sspacee.com/guides/resume-quantification
```

（sign 未登录返回 200 是预期——guest 可签发，见 A3。生产测试同样只允许产生 `jc/prod/uploads/`、`jc/prod/agent/` 下测试账号自己的对象，报告列清单。）

**A-2 已知陷阱：stale 进程导致的假 AttributeError**。实例：`/media/sign` 报 `presigned_put_url` 不存在，根因是 dev 服务进程启动早于 agentkit wheel 重建（11-17 23:36 本地），内存里是旧 agentkit；`uvicorn --reload` 不重载 site-packages，路由新、依赖旧。**规则：测前确认后端进程启动时间晚于 wheel 重建时间，否则先重启 dev.sh；测试期任何 AttributeError 先查进程启动时间，这不是产品缺陷。**

## 附录 B：负责人自测已证实的生产事实（2026-11-18，勿重复劳动，要当靶子测）

**已验证通过**：本地+生产图片消息端到端（发图→账本 `storage_key/size_bytes/download_url`→回放 re-sign→跨用户隔离 404）；生产第二次发图 32 events 完整 `done`。

**已证实的事故（当 P1 回归靶子，别当你的新发现）**：
- B-1 **worker 中途死亡 = 用户消息整条丢失**。`user_message` 行按设计挂起到 `system_prompt` 落库才写（`agent_service.py` trace 挂起写），worker 死在这之前则历史 0 条、无重试痕迹；对象已 PUT 成孤儿。**GC 只扫 `jc/<env>/uploads/`，agent 附件永远无人清。** 用例：发图过程中重启后端（本地），断言消息可见或有恢复路径；孤儿清单要能查出来。
- B-2 生产内存余量小（available ~144MB、swap 49%），worker 死亡无 traceback，OOM 嫌疑最大。Phase B6 在**生产**跑 3 连发时记录 `/health` 与响应时长，任何一次流被掐（`peer closed connection`）都单独报 P1 并附时间点。
- B-3 `profile_parse` 毒行 `prof_1jwhnmndkd2u9ivd` 每 30s `MissingGreenlet`（`profile_service.py:258` async 惰性加载），永久重试。测试期 grep `MissingGreenlet` 出现即记录频率，这是已知缺陷非你引入。
- B-4 TOS 策略拒绝 `jc/prod/agent/` 前缀 ListObjectsV2（`InvalidPathAccess`），`jc/prod/uploads/` 可以列。孤儿盘点不能靠列 agent 前缀，报告里说明用的什么替代办法。
