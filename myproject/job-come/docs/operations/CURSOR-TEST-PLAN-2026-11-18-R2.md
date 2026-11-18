# CURSOR-TEST-PLAN R2：直传 C/D 步 + B-1 修复后的回归测试

- **状态**：待执行
- **下发对象**：Cursor（Playwright + curl + 脚本）
- **执行环境**：生产 `https://jc.sspacee.com`（本轮**可以且应当**打生产，见 §0.1）+ 本地 main 检出（`http://127.0.0.1:8001` / `:3000`，代码同版本）
- **验收人**：项目负责人
- **前序**：`CURSOR-TEST-PLAN-2026-11-18.md`、`CURSOR-TEST-RESULT-2026-11-18.md`（其全部缺陷已关闭）、`B1-WORKER-DEATH-MESSAGE-LOSS-2026-11-18.md`

---

## 0. 这一轮测什么、为什么

上一轮报告（11-18 上午）之后，main 上又落了四批改动并已部署生产。这些改动**没有经过独立浏览器验证**：

| 改动 | commit | 已有哪些证据 | 缺什么 |
|---|---|---|---|
| B-1：worker 中途死亡不丢用户消息 | `087a056` | 9 个 pytest + 1 次产线 disposable 取证 | 真实浏览器路径：发送中刷新/断网，消息仍在 |
| 直传 C 步（聊天图/语音 `object_key` 路径） | 早前 + `251721e` | 单测 + 产线 1 次真实直传 | 直传失败→中继回退、弱网、取消上传 |
| D 步（简历原件直传 JSON 形态） | `949f517` | 单测 | 浏览器端真实走通 + multipart 兼容仍在 |
| 历史消息带回 `client_message_id` | `1790a45` | 单测 | 客户端乐观 UI 与服务端行对账 |

判断标准不变：**每条断言正反两侧**——合法路径必须通过，非法/故障路径必须被正确拒绝或降级。「我点了一下没报错」不算通过。

### 0.1 为什么这次可以打生产

CORS 已在产线桶配置并验证（双 origin `OPTIONS` 200），直传在生产是真通道。产线 2 日数据里直传已成功跑过 1 次。生产测试账号用 `cursor-r2-<时间戳>@sspacee.com` 前缀，测完在报告里列出账号 id，负责人负责清理。

### 0.2 环境基线（不达标就停）

```bash
git log --oneline -1    # 必须 ≥ 24429c6
```

```bash
curl -s -o /dev/null -w 'HEALTH=%{http_code}\n' https://jc.sspacee.com/health
```

```bash
curl -s -o /dev/null -w 'SIGN=%{http_code}\n' -X POST https://jc.sspacee.com/api/v1/media/sign -H 'content-type: application/json' -d '{"scene":"chat-image","contentType":"image/jpeg","sizeBytes":100}'
```

`HEALTH=200`、`SIGN=401/403`（路由存在、未登录被拦）。`SIGN=404` 说明部署落后，停止并报告。

CORS 前置快检（若失败直接定 P0，不用再往下测直传）：

```bash
curl -s -i -X OPTIONS 'https://sspacee.tos-s3-cn-beijing.volces.com/jc/prod/test' -H 'Origin: https://jc.sspacee.com' -H 'Access-Control-Request-Method: PUT' -H 'Access-Control-Request-Headers: content-type' | head -12
```

期望 `200`，且 `Access-Control-Allow-Origin` 回显该 origin、Allow-Headers 含 `content-type`、Expose-Headers 含 `ETag`。

### 0.3 明确不测的（测了也不计入）

- **性能/Lighthouse**：P2-1 与 fetchpriority 已复测关闭（3 连跑 TBT 4/57/48ms），无需再测。
- **E 步（拒收 `data_url`）**：观察期未结束，中继通道必须仍然可用是**预期行为**，不是缺陷。
- **PDF 导出**：本地环境缺 playwright，已知失败，不算本轮。

---

## Phase E — 聊天附件端到端（直传为主通道）

每条都要正反两侧。

| # | 用例 | PASS 判据 |
|---|---|---|
| E1 | 登录 → 对话中发一张 JPG（浏览器 UI 正常路径） | 请求序列 = `POST /media/sign` → `PUT`（TOS 域名，200/204）→ `POST …/messages`（200，SSE 正常出字）。**不得**出现消息体带 `data_url` |
| E2 | E1 之后立即刷新页面 | 图片气泡仍在；打开 DevTools 该 `<img>` src 是签名 URL；网络面板无 403/404 |
| E3 | 篡改：sign 拿到的 key，PUT 前先发消息 | 消息 4xx（bind 拒绝「根本没传」），且 SSE 流**不得**先 200 后死（P1-1 规则） |
| E4 | 篡改：PUT 一张 PNG 但 sign 时声明 jpeg | PUT 或 bind 阶段被拒（Content-Type 是签名的一部分；类型不符魔数校验也要拦），气泡不出现 |
| E5 | 取消/失败：选文件后在 PUT 中途断网（DevTools offline 即可） | 前端给出可重试的失败提示；**这条消息要么整条不存在、要么以 `storage_error` 气泡出现**——不得静默显示为正常图片 |
| E6 | 直传回退：把页面所在 origin 临时打不通 TOS 域名（host 级屏蔽 `sspacee.tos-s3-cn-beijing.volces.com`）后发消息 | 回退中继（消息体带 `data_url`），消息正常送达；**图片仍然可用**。中继是观察期内的正式降级通道，回退本身不是缺陷 |
| E7 | 语音条：录制约 10s 发送 | 同 E1 时序；回放有 transcript 文本 + 可播放录音（二者同在一行） |
| E8 | 越权：账号 B 拿账号 A 的 key 发消息 | 4xx；A 的历史不受影响 |
| E9 | 合计超限：一次贴 3 张接近上限的图 | 4xx 带明确文案；无半状态（有消息无附件行） |

## Phase F — B-1 回归：worker 生死之间消息不丢

生产环境**不得**在真实 API 进程上做任何 kill；用 disposable 方式或只在本地做。

| # | 用例 | PASS 判据 |
|---|---|---|
| F1（本地） | 发一条带图消息，在 SSE 出第一个字后立刻 `kill -9` 本地 uvicorn，重启，刷新历史 | 用户那条消息**存在**（文本+附件行）；assistant 行允许缺失 |
| F2（本地） | F1 同场景但消息不带附件 | 同上 |
| F3 | 发送中直接关浏览器标签页 30s 后重开 | 消息与 assistant 回复都在 |
| F4 | 断网 5s → 恢复 → 刷新历史 | 刷新前 UI 与刷新后服务端行**一致可对账**（见 Phase G） |

## Phase G — `client_message_id` 对账

| # | 用例 | PASS 判据 |
|---|---|---|
| G1 | 发消息 → 刷新 → 读 `GET …/messages` | 每条用户消息 JSON 里带 `client_message_id`，且与发送时前端生成值一致；页面不出现重复气泡 |
| G2 | 同一 `client_message_id` 重放提交（脚本重发） | 不产生第二条用户行，或有明确幂等错误码（报告里写清实际行为即可，但不得静默双写） |

## Phase D — 简历原件直传（profile-source）

| # | 用例 | PASS 判据 |
|---|---|---|
| D1 | 上传 PDF 简历走新 JSON 形态 | sign(scene=profile-source) → PUT → 提交成功；简历解析结果正常 |
| D2 | multipart 旧表单提交仍可用 | 200，结果与 D1 路径一致（观察期兼容是预期） |
| D3 | profile-source 场景发超上限 PDF（>10MB） | 拒收 + 明确文案；GC 后桶内无该对象（报告附 key） |

---

## 报告要求

- 落盘：`docs/operations/CURSOR-TEST-RESULT-2026-11-18-R2.md`，逐条 PASS/FAIL/N-A + 证据（网络面板截图路径、请求/响应序列、storage_key 清单）。
- 证据根目录：`/tmp/jc-validation/2026-11-18-r2/`（生产子目录 `prod/`）。
- 新缺陷按 P0/P1/P2 分级，给复现步骤；**FAIL 必须贴原始请求/响应，不要只写结论**。
- 生产测试账号与本轮产生的 storage_key 全部列出（负责人清桶用）。
- 签好的 presigned URL 是 bearer secret：报告与截图里必须打码，不得原样落盘（ADR-011 §7.4）。
