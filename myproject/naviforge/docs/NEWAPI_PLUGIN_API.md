# NewAPI × NaviForge 插件对接

> **Portal 示例:** `http://gpt.sspacee.com`  
> **插件侧:** `naviforge/apps/extension/src/lib/newapi-auth.ts`, `newapi-sync.ts`  
> **服务端:** `new-api/controller/plugin.go`, `new-api/service/plugin_bootstrap.go`  
> **回调页:** 扩展内 `auth-callback.html`

## 1. 端到端方案（谁做什么）

```
用户点击「登录 NewAPI」
    → 扩展打开 {portal}/plugin/connect?redirect_uri=chrome-extension://…/auth-callback.html&client=naviforge-extension
    → 专用授权页（浅色、步骤清晰）
    → 登录成功重定向 auth-callback.html?token=<access_token>&expires_in=…
    → 扩展 GET /api/plugin/bootstrap (Bearer token)
    → 写入本地 Chat + OCR 两个 Model Profile，Agent 可直接跑
```

| 层 | 职责 |
|----|------|
| **NaviForge 扩展** | 打开登录、收 token、调 bootstrap、写 Profile（已实现） |
| **NewAPI Web** | `/plugin/connect` 授权页、`/plugin/docs` 接口文档（已实现） |
| **NewAPI API** | `GET /api/plugin/meta`（公开）、`GET /api/plugin/bootstrap`（已实现） |
| **你（运维）** | 配环境变量、渠道、默认模型 ID、新用户额度 |

## 2. 你需要做的（运维清单）

### 2.1 环境变量（`new-api` 部署）

```bash
# 必须
SERVER_ADDRESS=https://gpt.sspacee.com          # 系统设置里也可配，bootstrap baseURL 依赖它

# 新用户
GENERATE_DEFAULT_TOKEN=true                     # 注册时自动创建 API Key（bootstrap 也依赖有可用 key）
QuotaForNewUser=2500000                         # 新用户赠送额度（后台「运营设置」里也可配，约 $5 量级按你站点 ratio）

# 插件默认模型（Model ID 必须与渠道里真实存在的名称一致）
PLUGIN_DEFAULT_CHAT_MODEL=gpt-4o                # Agent 对话
PLUGIN_DEFAULT_OCR_MODEL=gpt-4o-mini            # 截图/OCR（需支持 vision + image_url）

# 可选：部署时在页面上显示的构建标签（如 git sha / 日期）
PLUGIN_BUILD_LABEL=2026-08-22-naviforge-plugin

# 可选展示名
PLUGIN_CHAT_PROFILE_NAME=NewAPI 托管
PLUGIN_OCR_PROFILE_NAME=NewAPI OCR
```

### 2.2 后台必配项

1. **系统设置 → 站点**：`Server Address` = 公网 URL（与 `SERVER_ADDRESS` 一致，带 `https://`）
2. **渠道**：至少一条可用 OpenAI 兼容渠道，且渠道模型列表包含你设的 `PLUGIN_DEFAULT_*`
3. **运营设置**：
   - 开启用户注册（若要走自助注册）
   - `新用户赠送额度`（QuotaForNewUser）
   - `GENERATE_DEFAULT_TOKEN` 或让用户手动建 Key（否则 bootstrap 会失败）
4. **模型 ID**：在「模型」页确认 **对外模型名**（不是上游原名）— bootstrap 返回的是这个 ID

### 2.3 如何选 / 配置 Chat 与 OCR 模型

| 用途 | 要求 | 配置位置 |
|------|------|----------|
| **Chat** (`PLUGIN_DEFAULT_CHAT_MODEL`) | 支持 tool calling 更好；常规对话 | 环境变量或后续扩展后台选项 |
| **OCR** (`PLUGIN_DEFAULT_OCR_MODEL`) | **必须 vision**：OpenAI 格式 `image_url`；扩展走 chat/completions | 同上 |

**原则：Model ID = NewAPI 控制台「模型」里用户看到的名字**，不是 Azure deployment 内部名（除非你把它们配成一样）。

示例（按你实际渠道改）：

| 上游 | Chat 建议 | OCR 建议 |
|------|-----------|----------|
| OpenAI | `gpt-4o` | `gpt-4o-mini` |
| 火山方舟 | `ep-xxxx`（控制台别名） | 同系列 vision 接入点 |
| 通义 | `qwen-vl-max`（OCR）/ `qwen-plus`（Chat） | 分开配 |

验证：用 bootstrap 返回的 `apiKey` + `baseURL` 在 curl 里打一条带 `image_url` 的请求。

### 2.4 部署与验证

```bash
# 构建（你本地已跑通 extension build；new-api 需分别 build web + 起服务）
cd new-api/web && npm run build
# 起 new-api 服务（按你现有 docker/二进制流程）

# 验证 meta（无需登录）
curl -s https://gpt.sspacee.com/api/plugin/meta | jq .

# 验证 bootstrap（先浏览器登录拿 access_token，或登录回调里的 token）
curl -s -H "Authorization: Bearer <access_token>" \
  https://gpt.sspacee.com/api/plugin/bootstrap | jq .
```

期望 JSON：

```json
{
  "user": { "id": "1", "displayName": "...", "quotaUsd": 5 },
  "apiKey": "sk-...",
  "baseURL": "https://gpt.sspacee.com/v1",
  "chatModel": "gpt-4o",
  "ocrModel": "gpt-4o-mini",
  "chatProfileName": "NewAPI 托管",
  "ocrProfileName": "NewAPI OCR"
}
```

扩展侧：Reload → Side Panel「登录 NewAPI」→ 回调成功 → Options 里应看到托管 Profile 已填 Key/模型。

## 3. 接口契约

### 3.1 登录跳转（扩展 → Portal）

```http
GET {portal}/plugin/connect?redirect_uri={urlencode}&client=naviforge-extension&state={nonce}
```

（`/login?...` 仍可用，会自动跳到 `/plugin/connect`）

### 3.1b 文档与构建信息

- 授权页：`GET /plugin/connect`
- 接口文档（可点「试一试」）：`GET /plugin/docs`
- 元数据 API：`GET /api/plugin/meta`

### 3.2 登录回调（Portal → 扩展）

Chrome **禁止**网页跳转到 `chrome-extension://`（会显示 `invalid is blocked`）。扩展使用 `chrome.identity.launchWebAuthFlow`，回调地址为：

```http
https://<extension-id>.chromiumapp.org/auth-callback?token=<access_token>&expires_in=86400
```

`launchWebAuthFlow` 捕获该 HTTPS 重定向并完成登录（无需 `auth-callback.html` 标签页）。

### 3.3 Bootstrap

```http
GET /api/plugin/bootstrap
Authorization: Bearer <access_token>
```

**401** → 扩展清 session，提示重新登录。

## 4. 本地 Profile 写入（扩展自动）

| Profile ID | 用途 |
|------------|------|
| `mp_newapi_managed_chat` | Agent 默认 |
| `mp_newapi_managed_ocr` | OCR / 截图 |

## 6. 行为回放云端存储（rrweb）

NaviForge 扩展可将行为回放会话（指针事件 + rrweb DOM）上传到 NewAPI。

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/plugin/replay/sessions` | Bearer | 列出当前用户的回放元数据 |
| POST | `/api/plugin/replay/sessions` | Bearer | 上传完整 payload（gzip 存盘，单条 ≤25MB） |
| GET | `/api/plugin/replay/sessions/:id` | Bearer | 下载完整回放 |
| DELETE | `/api/plugin/replay/sessions/:id` | Bearer | 删除 |

**部署环境变量（可选）：**

```bash
PLUGIN_REPLAY_DATA_DIR=/data/plugin-replays   # 默认 data/plugin-replays
```

**扩展侧：** `naviforge/apps/extension/src/lib/replay-sync.ts`

## 5. 验收清单

- [ ] `GENERATE_DEFAULT_TOKEN=true` 或每用户至少一个启用中的 Key
- [ ] `PLUGIN_DEFAULT_*` 与渠道模型名一致
- [ ] OCR 模型实测支持 `image_url`
- [ ] 未登录打开 Side Panel → 跳转登录
- [ ] 登录回调 → bootstrap 200 → Agent 能跑
- [ ] bootstrap 401 → 提示重新登录
