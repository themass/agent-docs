# systemd 单元：companion-api / companion-voice

把 api(:8081) 与 voice worker 从 setsid 裸跑（process.sh 起、挂在 ssh session scope 里）
换到 init 名下：机器重启自起、崩溃自动拉起、进程族归 system.slice（CPUWeight/cgroup
策略真正可控，不再随登录会话漂移）。

## 装（104，root）

```bash
D=/home/web/webroot/companion-agent
cp $D/deploy/systemd/companion-api.service $D/deploy/systemd/companion-voice.service /etc/systemd/system/
# web 免密管这两个 unit（process.sh 检测到 unit 存在就走 systemctl，需要 sudo -n）：
printf 'web ALL=(ALL) NOPASSWD: /usr/bin/systemctl start companion-api, /usr/bin/systemctl stop companion-api, /usr/bin/systemctl restart companion-api, /usr/bin/systemctl status companion-api, /usr/bin/systemctl is-active companion-api, /usr/bin/systemctl start companion-voice, /usr/bin/systemctl stop companion-voice, /usr/bin/systemctl restart companion-voice, /usr/bin/systemctl status companion-voice, /usr/bin/systemctl is-active companion-voice\n' > /etc/sudoers.d/companion-service
chmod 440 /etc/sudoers.d/companion-service
```

## 切换顺序（关键：别让两套同时跑）

1. 静默窗口（LiveKit 无活跃房间）里，先停 setsid 起的旧进程：
   `sudo kill -TERM $(cat $D/.data/run/api.pid) $(cat $D/.data/run/voice.pid)`
   （unit 未装前 process.sh 还走 PID 文件模式，`process.sh stop` 也可以。）
2. `systemctl daemon-reload && systemctl enable --now companion-api companion-voice`
3. 验证：`curl -sf localhost:8081/health`；journal 里 `worker registered`；
   `systemctl status` 看进程族在 companion-*.service 下（不再是 user.slice）。

装好后 `process.sh start|stop|restart|status|logs` 自动委托 systemctl，发布流程
（publish.sh --restart）不用改。

## 日志

unit 模式下日志只进 journal（`journalctl -u companion-voice -f`），
`.data/logs/*.log` 停更——两处写同一文件会互相踩。旧日志留在原地备查，
journald 默认自己轮转（104 上未设上限，可加 SystemMaxUse=500M）。

## 回滚

```bash
systemctl disable --now companion-api companion-voice
rm /etc/systemd/system/companion-{api,voice}.service /etc/sudoers.d/companion-service
systemctl daemon-reload
cd $D && ./scripts/process.sh start   # 回到 setsid 模式（unit 文件不在了，自动回落）
```
