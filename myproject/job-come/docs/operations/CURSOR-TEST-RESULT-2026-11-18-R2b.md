# Cursor 测试结果 — 2026-11-18-R2b（P1-1/2/3 复验）

## 结论

针对 `aa9d73d` 修复的三个 P1，**本地 + 生产均已关闭**：

| 原缺陷 | 用例 | 本地 | 生产 |
|---|---|---|---|
| P1-1 历史不回 `client_message_id` | G1 | **PASS** | **PASS** |
| P1-2 同 id 静默双写 | G2 | **PASS** | **PASS**（`rows=1`，二次仍 200 复用原行） |
| P1-3 PUT 中途失败仍中继成正常图 | E5 | **PASS** | **PASS**（PUT abort 后 **无** `POST …/messages`） |

E6（观察期中继）在 **sign 失败** 路径上两端 **PASS**（`data_url` → `jc/*/agent/…/attachments/…`）。

**口径变更（相对计划原文）**：计划 E6 写的是「host 屏蔽 TOS」。`aa9d73d` 把「sign 成功 + PUT 失败」并入 E5 闸门（阻断发送），中继只留给 **sign 不可用**。计划步骤「只屏蔽 TOS」现在表现与 E5 相同（`GATED_like_E5`），不是回归。

证据根：`/tmp/jc-validation/2026-11-18-r2b/`。

---

## 环境基线

| 检查 | 结果 |
|---|---|
| 仓库 HEAD（复验时） | 本地跑于含 `aa9d73d` 的 tree；命令结束时 tip=`557030d` |
| 生产 HEALTH | 200 |
| 生产 SIGN（无 cookie） | 200（guest 可签，同 R2） |
| TOS CORS OPTIONS | 200 + ACAO 回显 + ACH=`content-type` + Expose=`ETag` |
| 生产未对真实进程 kill | 是 |

---

## Phase G

### G1 PASS

历史用户行含顶层 `client_message_id`，与发送值一致。

- 生产：`cmsg_c628d047bef0c8b4204a08fb`（`prod/g-results.json`）
- 本地：`cmsg_e8412d6735309467e4c56276`（`local/g-results.json`）

### G2 PASS

同 `client_message_id` 连发两次 → **仅 1 行**用户消息（二次 200 复用，非静默双写）。

- 生产：`agtr_ri3deqg0gebtyolw`
- 本地：`agtr_huvspsgkcxz3wt8x`

---

## Phase E5 / E6（浏览器）

### E5 PASS（PUT 中途 abort）

网络：`sign` 200 → PUT `chat-image` → `ERR_INTERNET_DISCONNECTED` → **无** `POST …/messages`。

历史检索「浏览器E5r2b」：**0 行**（消息未落库）。UI `hintish`（失败/重试/未发送类文案）为 true。

证据：`prod|local/browser-e56.json`、`screenshots/e5.png`。

### E6 PASS（sign 失败 → 中继）

阻断 `/media/sign` → 仍 `POST …/messages` 200；附件落 agent 路径：

- 生产：`jc/prod/agent/agsn_8bcu5fg95potoiqt/attachments/agm_s1sqdgbqd8qltwnp-0.jpg`（`agtr_3oxi200kanhhvssw`，带 `client_message_id`）
- 本地：`jc/dev/agent/agsn_93emqg9utzjzfb7m/attachments/agm_g5vxqhabx2k5e63b-0.jpg`

### E6 计划原文步骤（仅屏蔽 TOS）

`E6_plan_tos_block` = `GATED_like_E5`（无 messages POST）。与 `aa9d73d` 设计一致：sign 已成功则不可再静默中继。

---

## 缺陷清单（本轮）

- 原 P1-1 / P1-2 / P1-3：**关闭**
- 新开缺陷：**无**
- 测试/文档备注：计划 E6 操作步骤与实现语义已漂移，建议下次改计划文案为「使 `/media/sign` 失败」或「签发前 TOS/直传通道不可用」

---

## 生产测试账号（请清理）

| 用途 | email | user id |
|---|---|---|
| G/E 复验 A | `cursor-r2b-1795009969-a@sspacee.com` | `usr_3zfpb40nvmkkpgk4` |

密码仅存 `/tmp/jc-validation/2026-11-18-r2b/prod/accounts.secret`。

本地：`cursor-r2b-1795010481-a@sspacee.com` → `usr_aoedtxmys7d4yhdu`。

---

## 产物索引

| 路径 | 内容 |
|---|---|
| `…/prod/g-results.json` / `local/g-results.json` | G1/G2 |
| `…/prod/browser-e56.json` / `local/browser-e56.json` | E5/E6 浏览器 |
| `…/*/screenshots/e5.png` / `e6-sign-fail.png` / `e6a-tos-block.png` | 截图 |
| `…/run_browser_e56.mjs` / `run_g_e56.py` | 复验脚本 |
