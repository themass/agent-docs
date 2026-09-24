# `~/.hermes/profiles/content-studio` 里都是什么？

本机 Hermes Profile 目录里 **混有两类东西**：你们开发的 **Agent 包**（应进 git），和 Hermes 运行后自动生成的 **运行时数据**（不要分享、不要提交）。

**可分享的完整包（Agent + 运维 + 启停栈）**：

```text
docs/hermes/content-studio-agent/bundle/
├── profile/          # SOUL、skills/content-studio、content-studio.sh
├── ops/scripts/      # sync-secrets、TTS 代理、Notebook 维护…
└── stack/            # start/stop-content-studio-stack.sh、ports.env
```

安装：`cd docs/hermes/content-studio-agent/bundle && ./install.sh`  

开发镜像（与 `bundle/profile` 同步）：`hermes-dev/profiles/content-studio/`

---

## 1. 一张表分清「要 / 不要」

| 路径（在 `~/.hermes/profiles/content-studio/` 下） | 是否你们开发的 Agent | 是否应进 git | 说明 |
|--------------------------------------------------|---------------------|--------------|------|
| **`SOUL.md`** | ✅ 是 | ✅ | 人设与 Skill 路由 |
| **`profile.yaml`** | ✅ 是 | ✅ | Profile 描述 |
| **`skills/content-studio/`** | ✅ 是 | ✅ | 自研 Skill + 脚本 + 模板 |
| **`scripts/`** | ✅ 是 | ✅ | `content-studio.sh` 主编排器 |
| **`config/tts-providers.example.yaml`** | ✅ 是 | ✅ | TTS 模板 |
| **`docs/TTS_CONFIG.md`** | ✅ 是 | ✅ | TTS 文档 |
| **`config.yaml`** | ⚙️ 环境 | ❌ 用 `config.yaml.example` | 含模型、base_url；可能有 api_key |
| **`secrets.env` / `.env`** | 🔐 密钥 | ❌ | 仅本机 |
| **`config/tts-providers.yaml`** | 🔐 密钥 | ❌ | 真实 TTS key |
| **`reports/`** | 📦 产出 | ❌ | 日报、视频、脚本（可单独备份） |
| **`logs/`** | 📦 运行 | ❌ | `sop-latest.log`、MPT 渲染日志 |
| **`skills/`（除 content-studio 外）** | ❌ 否 | ❌ | 从市场/官方安装的其它 Skill（体积大） |
| **`state.db`** | ❌ 运行时 | ❌ | 会话与 Gateway 状态（可达数十 MB） |
| **`sessions/`** | ❌ 运行时 | ❌ | 请求 dump、调试 JSON |
| **`home/`** | ❌ 运行时 | ❌ | Agent 终端家目录（可非常大） |
| **`cache/`、`audio_cache/`** | ❌ 运行时 | ❌ | 缓存 |
| **`checkpoints/`** | ❌ 运行时 | ❌ | Checkpoint 存储 |
| **`cron/`** | ⚙️ 混合 | 可选 | 定时任务定义可导出；output 是产物 |
| **`plugins/`** | ⚙️ 混合 | 一般否 | 插件状态 JSON |
| **`bin/`** | ❌ 工具 | ❌ | 下载的二进制（如 tirith） |
| **`auth.json`、`auth.lock`** | ❌ 运行时 | ❌ | OAuth 等 |
| **`gateway_state.json`** | ❌ 运行时 | ❌ | Gateway 状态 |
| **`memories/`** | 📦 Agent 记忆 | 可选备份 | Hermes 长期记忆（非 Skill 源码） |

---

## 2. 你们开发的 Agent 到底指什么？

**Content Studio Agent** = 下面四件套，全部在 git 的 `hermes-dev/profiles/content-studio/`：

```text
SOUL.md
profile.yaml
skills/content-studio/     # playbook、日报、三条视频、报告库…
scripts/content-studio.sh  # 唯一 CLI 真相源（+ 薄包装 *.sh）
```

Hermes **对话时**还会读 `config.yaml` + 已安装的其它 `skills/*`，但那些 **不是** Content Studio 产品定义的一部分；分享给别人时只需安装本 profile + 自行 `hermes skills install` 额外能力。

---

## 3. 启动脚本在哪？（不在 Profile 里）

| 脚本 | 作用 |
|------|------|
| **`hermes-dev/start-content-studio-stack.sh`** | 一键起 Gateway + Workspace + Open Notebook + MPT + OpenInspector |
| **`hermes-dev/stop-content-studio-stack.sh`** | 停止全栈 |
| **`hermes-dev/start-dev.sh`** | 仅 Hermes + Workspace |
| **`hermes-dev/scripts/sync-content-studio-secrets.sh`** | 把 `secrets.env` 同步到各服务 |
| **`$HERMES_HOME/scripts/content-studio.sh`** | **内容生产** CLI（日报/视频/SOP），不是起服务 |
| **`$HERMES_HOME/scripts/setup-cron.sh`** | 安装 Cron |

起 **Hermes Gateway** 本身：`hermes gateway run`（需 `HERMES_HOME` 指向 content-studio）。

---

## 4. 开发 → 分享工作流

```bash
# 在本机 Profile 里改 Skill / SOUL / content-studio.sh
export HERMES_HOME=~/.hermes/profiles/content-studio
# ... 编辑 ...

# 回灌到 git（只同步 Agent 包，不带 state.db）
cd hermes-dev/profiles/content-studio
./sync-from-live.sh

git add hermes-dev/profiles/content-studio
git commit -m "..."
```

别人克隆仓库后：

```bash
cd hermes-dev/profiles/content-studio && ./install.sh
cp ../../config/secrets.env.example ~/.hermes/profiles/content-studio/secrets.env
# 编辑密钥后
../../scripts/sync-content-studio-secrets.sh
```

---

## 5. 体积为什么这么大？

典型本机 Profile **500MB+** 多半来自：

- `home/` — 终端沙箱家目录  
- `state.db` — 历史会话  
- `skills/` 里 **几十 MB 第三方 Skill**（不是 content-studio 包）

git 里整个 Agent 包约 **< 1MB**（仅 `skills/content-studio` + scripts）。
