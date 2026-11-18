# Cursor 测试结果 — 2026-11-18-R2

## 结论

- 代码：API 主套件跑于 `b979ad8`；浏览器补测 / G 复测时仓库 HEAD=`c0ad8a1`（≥`24429c6`）
- 生产 CORS OPTIONS **200**（Allow-Origin 回显、Allow-Headers 含 content-type、Expose-Headers 含 ETag）；生产未对真实进程做 kill
- **直传主通道（E1–E4/E7–E9）本地+生产 API 全绿**；生产浏览器 E1/E2 **PASS**（`chat-image` 真直传）
- **E5 FAIL（生产浏览器）**：PUT 中途 abort 后仍走 data_url 中继并显示为正常图（`jc/prod/agent/…`），违反「不得静默显示为正常图片」
- **E6 PASS（生产浏览器，隔离复测）**：TOS 全屏蔽 → sign 后 PUT 失败 → messages 200 + agent 路径附件可读
- **B-1（F1/F2）本地 PASS**；**F3/F4 生产浏览器 PASS**
- **G1/G2 FAIL（两端；HEAD `c0ad8a1` 生产复测仍 FAIL）**：历史不回 `client_message_id`；同 id 重放静默双写
- D1/D2/D3 PASS（D3 实际上限 **15MB**）
- 新缺陷：P0 0 / P1 **3** / P2 0
- 证据：`/tmp/jc-validation/2026-11-18-r2/`（`local/`、`prod/`）

---

## 环境基线

| 检查 | 结果 |
|---|---|
| `git`（job-come） | API 套件 `b979ad8`；补测时 `c0ad8a1` ≥ `24429c6` |
| 生产 HEALTH | 200 |
| 生产 SIGN（无 cookie） | **200**（guest 可签，与计划「401/403」文案不符，路由存在） |
| TOS CORS OPTIONS | **200** + ACAO=`https://jc.sspacee.com` + ACH=`content-type` + Expose=`ETag` |
| 本地 HEALTH/WEB | API 套件时 200；G 复测时本地 `8088` **Connection refused**（未再杀进程复测 F） |

---

## 总表

| # | 本地 | 生产 | 备注 |
|---|---|---|---|
| E1 sign→PUT→messages(object_key) | PASS | PASS | API + **浏览器**（cookie 登录；`accept=image/*`→`chat-image`） |
| E2 刷新后可读 | PASS | PASS | API download_url；浏览器 signed `<img>` 无坏链 |
| E3 未 PUT 即发消息 | PASS | PASS | **404** `upload_not_found` |
| E4 CT/魔数不符 | PASS | PASS | 错 CT→PUT **403**；同 CT+PNG 魔数→bind **400** `attachment_rejected` |
| E5 中途断网 | N/A | **FAIL** | PUT abort 后仍 messages 200 + 正常图（中继路径） |
| E6 屏蔽 TOS 回退中继 | N/A | **PASS** | 隔离复测 `e6-iso-result.json`；套件内首次因路由残留误判 FAIL |
| E7 语音直传 | PASS | PASS | transcript + storage_key + download_url |
| E8 B 用 A 的 key | PASS | PASS | **403** `foreign_upload` |
| E9 合计超限 | PASS* | PASS | *本地初测口径过松后复测；生产 4×7MB→**400** `attachment_too_large` |
| F1 kill -9 + 图 | PASS* | N/A（禁杀生产） | *须等用户行落库后再杀 |
| F2 kill -9 纯文本 | PASS | N/A | |
| F3 关标签页 | N/A | PASS | 关页 ~2.5s → 等 30s → 重开，用户文案仍在 |
| F4 断网对账 | N/A | PASS | UI 命中 1 / 服务端用户行 1（`agtr_1fn6vwsim4qhxowl`） |
| G1 历史带 client_message_id | **FAIL** | **FAIL** | `c0ad8a1` 生产复测仍无字段（`prod/g-recheck.json`） |
| G2 同 id 重放不双写 | **FAIL** | **FAIL** | 复测 `rows=2`：`agtr_d02o30udgivrqdx6`, `agtr_7ve2zbpcr5eqydfw` |
| D1 upload-direct | PASS | PASS | |
| D2 multipart 兼容 | PASS | PASS | |
| D3 超上限 | PASS* | PASS | *上限实为 **15MB** |

---

## Phase E 明细（原始响应摘要）

### E3（正例：拒收未上传 key）

```json
{"status": 404, "body": {"code":"upload_not_found","message":"文件没有上传成功，请重试。"}}
```

### E4（正例：类型不一致）

- PUT `Content-Type: image/png`（签名为 jpeg）→ **403**
- PUT 成功但字节为 PNG、声明 jpeg → 发消息 **400**  
  `{"code":"attachment_rejected","message":"附件内容与声明的类型不一致，请重新选择文件。"}`

### E8

```json
{"status": 403, "body": {"code":"foreign_upload","message":"无权使用此上传。"}}
```

### E9（生产 / 本地复测）

请求：4×`object_key`（各 ~7MB，合计 28MB > 24MB）

```json
{"status": 400, "body": {"code":"attachment_too_large","message":"这条消息的附件合计超过 24 MB，请分几次发送。"}}
```

无半状态用户行。

### E1 时序（两端一致；浏览器已复核）

`POST /media/sign` 200 → `PUT` TOS 200 → `POST …/messages` 200 SSE；历史附件仅 `storage_key`，无 `data:image`。

生产浏览器 E1 storage_key：

`jc/prod/uploads/usr_3nk1des9911jl0xn/chat-image/2026/11/18/lg0EWjuNMhstWPmqaIfwfw.jpg`

（首轮误点 `profile-source` 的假 PASS 已作废；重跑脚本锁定 `input[accept="image/*"]`。）

### E5 FAIL（生产浏览器）

网络：`sign` 200 → PUT `chat-image` → `net::ERR_INTERNET_DISCONNECTED` → 仍 `POST …/messages` **200**。

历史用户行 `agtr_2rfbu4gogz19j7kl` 附件：

```text
jc/prod/agent/agsn_yzzxxh2ly201emwh/attachments/agm_95182qhdlvnnqa34-0.jpg
```

即走了 data_url 中继落盘，UI 呈现为正常图片——违反计划「要么整条不存在、要么 storage_error 气泡」。证据：`prod/browser-r2-results.json`、`prod/screenshots/e5-offline-put.png`。

### E6 PASS（生产浏览器，隔离）

TOS host 在 attach 前全屏蔽：`sign` 200 → PUT fail → `messages` 200；marker「浏览器E6iso」可见；附件：

```text
jc/prod/agent/agsn_735cqaczus1270iu/attachments/agm_snip792rtpyn92u5-0.jpg
```

证据：`prod/e6-iso-result.json`、`prod/screenshots/e6-iso.png`。  
说明：同脚本串行跑时 E5 的 route 残留曾导致 E6 `net=[]` 误 FAIL；以隔离复测为准。中继是观察期正式降级，**回退本身不计缺陷**。

---

## Phase F — B-1

| 用例 | 结果 | 证据 |
|---|---|---|
| F1 带图 | PASS | 用户行 `agtr_o22yckbdc02bpzr7` 在 kill 前已落库；重启后仍在且含 `storage_key`（`local/F1r-result.json`） |
| F2 无附件 | PASS | `local/f-results.json` |
| F1 第一次尝试 | FAIL→测试操作过早 | 2.5s 即 kill，用户行尚未 durable；不记产品缺陷 |
| F3 关标签页 | PASS（生产） | `prod/browser-r2-results.json` / `screenshots/f3-reopen.png` |
| F4 断网对账 | PASS（生产） | UI 1 条 / 服务端 1 行；`has_client_message_id=false`（与 G1 一致） |

---

## Phase G

### G1 FAIL（本地+生产；`c0ad8a1` 复测仍 FAIL）

`GET /api/v1/agent/sessions/{id}/messages` 用户行字段仅有：

`id, session_id, role, event_type, content, payload, created_at`

**没有** `client_message_id`（顶层与 `payload` 皆无；payload 仅 `text`）。  
复测：`prod/g-recheck.json`（`cmid_sent=r2-g-recheck-24092275099b`）。

说明：计划引用的 `1790a45` 只改了 **companion-agent**，JC 历史序列化未带回该字段。

### G2 FAIL（本地+生产）— 原始行为

| | status | 结果 |
|---|---|---|
| 第一次 | 200 SSE | 写入用户行 |
| 第二次（同 `client_message_id`） | 200 SSE | **再写一行** |

生产初测：`rows=2`，ids=`agtr_k30p9v7g2embmrvp`, `agtr_44r3wtcg7ds9l9go`（`prod/g2b.json`）。  
生产复测：`rows=2`，ids=`agtr_d02o30udgivrqdx6`, `agtr_7ve2zbpcr5eqydfw`（`prod/g-recheck.json`）。

---

## Phase D

| # | 结果 | 原始要点 |
|---|---|---|
| D1 | PASS | sign(profile-source)→PUT→`POST /profiles/upload-direct` 200 |
| D2 | PASS | multipart `/profiles/upload` 200 |
| D3 | PASS | `sizeBytes=15MB+5000` → **400** `size_over_limit`「文件超过 15 MB 上限…」；`limits.maxBytes=15728640` |

---

## 缺陷清单

### P1-1 JC 历史消息不回传 `client_message_id`（G1）

- **现象**：发送体可带该字段；`GET …/messages` 永不返回。
- **复现**：任意登录用户发带 `client_message_id` 的消息后拉历史。
- **影响**：乐观 UI 刷新后无法按 id 合并富内容行。
- **建议**：在 `AgentMessageRecord` / 列表序列化中写出存储的 client id（需先落库）。

### P1-2 普通聊天对 `client_message_id` 重放静默双写（G2）

- **现象**：同 id 连发两次 → 两个用户行，皆 200。
- **复现**：见 `local/eg-d-results.json`、`prod/g2b.json`、`prod/g-recheck.json`。
- **影响**：弱网重试/关页重开可能出现重复气泡。
- **建议**：按 `(session_id, client_message_id)` 幂等；第二次返回已有行或 409。

### P1-3 PUT 中途失败仍中继成正常图（E5）

- **现象**：浏览器在 PUT 中途断网后，前端仍以 data_url 发消息；服务端落 `jc/prod/agent/…` 附件，UI 无 `storage_error`、消息未撤销。
- **复现**：chat 选图 → Playwright/DevTools 在 TOS PUT 时 abort → 发送。
- **影响**：用户以为直传成功；与「失败可重试 / storage_error」验收不符；和 E6 观察期中继语义纠缠（E6 是「一开始就打不通 TOS」的正式降级）。
- **建议**：区分「用户主动发送前的可达性降级（E6）」与「已选文件、PUT 已开始后的失败（E5）」——后者应阻断发送或标 storage_error，而不是静默中继。

---

## 测试缺陷 / 计划口径

1. **E9 初测 3×7MB=21MB < 24MB**：未触发上限，属用例过松；复测 4×7MB 才 FAIL→PASS。
2. **D3 计划写 >10MB**：代码 scene 上限 **15MB**；按 10MB 测会误报。
3. **SIGN 无登录期望 401/403**：guest 签发返回 200（与 R1/A3 一致）。
4. **浏览器登录**：表单 fill 不稳 → 改用 `/api/v1/auth/login` 注入 `jc_session` cookie。
5. **E1 首轮假 PASS**：点到简历 `profile-source`；必须以 `chat-image` storage_key / `accept=image/*` 为准。
6. **E6 套件顺序污染**：E5 `page.route` abort 残留导致同会话 E6 无网络事件；隔离复测 PASS。
7. **`1790a45` 归属**：companion，不是 JC。

---

## 生产测试账号（请清理）

| 角色 | email | user id |
|---|---|---|
| A | `cursor-r2-20261118162645-a@sspacee.com` | `usr_3nk1des9911jl0xn` |
| B | `cursor-r2-20261118162645-b@sspacee.com` | `usr_esxoh62xxqaom163` |

密码仅存本机 `/tmp/jc-validation/2026-11-18-r2/prod/accounts.secret`（未入库）。

本地对照账号：`cursor-r2-20261118155903-{a,b}@sspacee.com` → `usr_i8hc2mo0bf9l0x5r` / `usr_5ghop21gspkqxgai`。

---

## storage_key 清单

- 生产直传：`jc/prod/uploads/…`（API 主清单 + 浏览器 E1 `chat-image`）；无串 `jc/dev/`
- 生产中继（E5/E6）：`jc/prod/agent/{session}/attachments/…`
- 本地：全部 `jc/dev/uploads/…`（`…/local/storage_keys-all.json`）
- 主清单（签发键）：各环境 `storage_keys.json`（12 条/侧）
- presigned URL 已在结果 JSON 中打码（`?…`）

---

## 产物索引

| 路径 | 内容 |
|---|---|
| `…/local/eg-d-results.json` / `f-results.json` / `F1r-result.json` | 本地 E/G/D/F |
| `…/prod/eg-d-results.json` / `g2b.json` / `g-recheck.json` | 生产 API + G 复测 |
| `…/prod/browser-r2-results.json` / `browser-r2b-console.txt` | 生产浏览器套件 |
| `…/prod/e6-iso-result.json` | E6 隔离复测 |
| `…/*/storage_keys*.json` | key 清单 |
| `…/prod/screenshots/{e1,e2,e5,e6,e6-iso,f3,f4}*.png` | 浏览器证据 |
| `…/cors-options` 相关 | CORS 头（基线） |
