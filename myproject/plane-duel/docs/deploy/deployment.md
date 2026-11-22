# 部署手册

## 架构

```
浏览器 / App ──wss──▶ Caddy (443, 自动 HTTPS) ──/ws──▶ server (Node, 8080, 内存态)
                         └─ 其余路径：静态 H5（apps/client/dist）
```

单进程、内存态（spec §八）。**服务端重启会让所有在途对局失效**——这是 P0 明确接受的取舍。

## 本地整套验证

```bash
docker compose up --build
# 打开 https://localhost（Caddy 本地自签证书，浏览器接受一次）
```

## 上线

1. 一台 1 核 2G 的服务器即可。
   - 面向国内公众：服务器须在境内、域名须 **ICP 备案**（2–3 周），见设计文档 §七。
   - 只给自己和朋友测：香港/海外服务器免备案，当天可用。
2. 域名 A 记录指向服务器。
3. ```bash
   SITE_ADDRESS=game.example.com docker compose up -d --build
   ```
   Caddy 自动申请并续期 Let's Encrypt 证书。
4. App 端构建时注入 `VITE_WS_URL=wss://game.example.com/ws`（见 `packaging.md`）。

## 运维

| 事项 | 命令 |
|---|---|
| 看日志 | `docker compose logs -f server` |
| 重启（会断掉在途对局） | `docker compose restart server` |
| 更新 | `git pull && docker compose up -d --build` |
