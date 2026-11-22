# 部署（spec §廿三）

单机上线三步半：

```bash
mkdir -p data && chmod 777 data   # 半：容器内以 node(1000) 用户写档案，宿主机目录先给权限
SITE_ADDRESS=game.example.com docker compose up -d --build
docker compose ps                 # server 应为 healthy
curl -f http://127.0.0.1:8080/healthz   # → ok（宿主机直连容器网络时也可 docker compose exec server wget -qO- 127.0.0.1:8080/healthz）
```

要点：

- **`SITE_ADDRESS` 必须是已备案域名的 A 记录**：Caddy 自动申请 Let's Encrypt 证书；
  留空/localhost 只够本机自签测试。手机在蜂窝网络下必须走 `wss://` 真实域名（§九）。
- **数据卷**：`./data:/repo/apps/server/data` 挂档案文件。删容器不删档案；
  备份就是把 `data/profiles.json` 拷走（写盘是"临时文件 + 原子改名"，拷到什么都是完整档）。
- **停机**：`docker compose stop server` 走优雅序列——退还在途门票 → 档案落盘 → 断连接，
  最长 8 秒（看门狗），compose 侧 `stop_grace_period: 15s` 兜底。玩家端表现为断线重连（客户端 I2 自动处理）。
- **升级**：`docker compose up -d --build`。在途对局作废（§九 既定），排队门票自动退回。
- 广告奖励当前是服务端 mock（§廿二.4）；上线真广告需替换 verifier，协议不变（§廿二.9 检查单）。
