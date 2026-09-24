# Content Studio — 可分享完整包

本目录包含 **Content Studio Agent** 的全部自研产物与联调脚本，可单独打包给他人（需同 monorepo 内的 `hermes-agent`、`open-notebook`、`MoneyPrinterTurbo` 等）。

## 目录结构

```text
bundle/
├── README.md                 # 本文件
├── env.sh                    # REPO_ROOT / HERMES_DEV / 各服务路径
├── install.sh                # 安装 Agent Profile 到 ~/.hermes
├── sync-from-live.sh         # 从本机 ~/.hermes 回灌 profile
├── profile/                  # ★ Agent：SOUL + skills/content-studio + content-studio.sh
├── ops/scripts/              # ★ 密钥同步、TTS 代理、Notebook/MPT 联调
├── stack/                    # ★ 一键启停全栈 + ports.env + PORTS.md
├── config/secrets.env.example
└── lib/deepagents-python.env.sh
```

## 快速开始

```bash
# 1. 安装 Agent（人设 + Skills + 编排脚本）
cd docs/hermes/content-studio-agent/bundle
./install.sh

# 2. 配置密钥
cp config/secrets.env.example ~/.hermes/profiles/content-studio/secrets.env
# 编辑后
./ops/scripts/sync-content-studio-secrets.sh

# 3. 启动全栈（在 monorepo 根目录克隆完整仓库的前提下）
./stack/start-content-studio-stack.sh
# 停止：./stack/stop-content-studio-stack.sh
```

## Agent CLI（不启动全栈）

```bash
export HERMES_HOME=~/.hermes/profiles/content-studio
"$HERMES_HOME/scripts/content-studio.sh" daily
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline
```

## 文档

上层说明：[../README.md](../README.md) · [.hermes 目录说明](../HERMES_HOME_GUIDE.md)
