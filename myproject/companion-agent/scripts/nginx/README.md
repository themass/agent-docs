# companion-agent 的 nginx 配置

部署拓扑：App → nginx 网关（api.ok123find.top, 8.217.122.83）→ agent 机（104.160.191.87:8081）

nginx 是源码编译的（`/root/local/nginx-1.24.0`），配置在 `/root/local/nginx-1.24.0/conf/server/*.conf`，
每个站点一个文件。companion-agent 不新建站点，而是挂在已有的 `api.ok123find.top`（`vpn.conf`）下。

## 改了什么

**`upstream.conf`** 末尾加一段（`server/*.conf` 都会被 `include`，`upstream` 块可以放在任意被加载的文件里）：

```nginx
upstream ca_api {
    server 104.160.191.87:8081 max_fails=3 fail_timeout=10s;
    keepalive 16;
}
```

**`vpn.conf`** 的 `api.ok123find.top` server 块里，在 `/vvv/` 之前加两个 location：

```nginx
location ^~ /v1/ {
    proxy_pass http://ca_api;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;        # SSE 必须关缓冲，否则回复等整段才到 App
    proxy_cache off;
    proxy_read_timeout 3600s;   # 事件流长连接
    client_max_body_size 32m;   # 上传
}

location = /companion-health {
    proxy_pass http://ca_api/health;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
}
```

## 为什么不新建站点

`api.ok123find.top` 已经是 App 的入口（`Constants.BASE_IP`），companion 的 `/v1/` 路由只是其中一条路径。
拆成新域名要改 App 的 `BASE_IP`，没必要。`/v1/` 前缀不会和已有的 `/vvv/api/*` 冲突（前缀不同）。

## 安全

agent 只对网关机开放 TCP 8081（iptables 规则限制 `src 8.217.122.83`），不暴露公网。
公网入口是 nginx，认证由 agent 自己做（`COMPANION_AUTH_VERIFIER=redis_token`，读 Java 登录态）。

## 验证过的

- `http://api.ok123find.top/companion-health` → `{"status":"ok"}`
- `http://api.ok123find.top/v1/sessions`（无 token）→ 401（redis_token 拒绝）
- `https://api.ok123find.top/companion-health` → `{"status":"ok"}`

## 没验证的

- 带真实 Java 登录 token 的端到端请求（需要 App 登录后拿 token 才能测）
- SSE 事件流在公网下的逐字到达（需要真实会话）
- 语音房间端到端（需要手机进房间）
