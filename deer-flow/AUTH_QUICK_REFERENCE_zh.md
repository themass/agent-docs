# 认证与隔离速查（中文）

> 完整设计见 [AUTH_DESIGN.md](AUTH_DESIGN.md)；升级路径见 [AUTH_UPGRADE.md](AUTH_UPGRADE.md)。

## 一句话

DeerFlow Gateway **默认强制认证**（fail-closed）。登录后 session 通过 **HttpOnly `access_token` cookie** 传递；写操作还需 **CSRF 双提交**（`csrf_token` cookie → `X-CSRF-Token` header）。

## 公开端点（无需登录）

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/v1/auth/initialize` | 首次创建 admin（仅无 admin 时） |
| `POST` | `/api/v1/auth/login/local` | 邮箱密码登录 |
| `POST` | `/api/v1/auth/register` | 注册普通用户 |
| `POST` | `/api/v1/auth/logout` | 登出 |
| `GET` | `/api/v1/auth/setup-status` | 是否仍需初始化 admin |

## 需登录端点

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/v1/auth/me` | 当前用户 |
| `POST` | `/api/v1/auth/change-password` | 改密（递增 `token_version`，重发 cookie） |

## 磁盘隔离布局

Auth 启用后，数据按 **`user_id`** 分桶（`config/paths.py`）：

```text
{DEER_FLOW_HOME}/users/{user_id}/
├── memory.json
├── agents/{name}/SOUL.md, config.yaml, memory.json
└── threads/{thread_id}/user-data/
    ├── workspace/
    ├── uploads/
    └── outputs/
```

- 未设置 auth 上下文时，文件路径回退 **`user_id = "default"`**（`runtime/user_context.py`）
- 沙箱内虚拟路径仍为 `/mnt/user-data/...`

## API 调用示例

```bash
# 1. 登录（获取 access_token + csrf_token cookies）
curl -c cookies.txt -X POST http://localhost:2026/api/v1/auth/login/local \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}'

# 2. 带 CSRF 的写操作（从 cookies.txt 读取 csrf_token）
CSRF=$(grep csrf_token cookies.txt | awk '{print $7}')
curl -b cookies.txt -X POST http://localhost:2026/api/threads/abc/runs/stream \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"input":{"messages":[{"role":"user","content":"hi"}]},"stream_mode":["values","messages-tuple"]}'
```

## IM / 内部调用

`app/channels` 进程内调用 Gateway 时使用 **`internal_auth`** 头绕过浏览器 CSRF，仍携带有效用户上下文。详见 `app/gateway/internal_auth.py`。

## 与 MCP OAuth 的区别

- **DeerFlow API Auth**：浏览器/用户会话（JWT cookie + CSRF）
- **MCP OAuth**：`extensions_config.json` 中为 HTTP/SSE MCP 服务器配置的出站 token，与 Gateway 登录无关

## 相关文档

- [API.md § Authentication](API.md#authentication)
- [PATH_EXAMPLES.md](PATH_EXAMPLES.md) — per-user 路径示例
- [APP_PACKAGE_AND_AGENT_ECOSYSTEM_zh.md](APP_PACKAGE_AND_AGENT_ECOSYSTEM_zh.md) — Gateway Auth 中间件
