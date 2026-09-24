# Content Studio Agent Profile（可分享包）

本目录是 **Content Studio 内容生成 Agent** 的完整开发产物（人设、Skills、编排脚本），可从 git 安装到 `~/.hermes/profiles/content-studio`。

**不包含**：state.db、sessions、home/、第三方 Skill 市场整包。

## 安装

```bash
cd hermes-dev/profiles/content-studio
chmod +x install.sh sync-from-live.sh
./install.sh
```

## 使用

```bash
export HERMES_HOME="$HOME/.hermes/profiles/content-studio"
"$HERMES_HOME/scripts/content-studio.sh" help
```

全栈：`hermes-dev/start-content-studio-stack.sh` · 端口：`hermes-dev/PORTS.md`

## 文档

- [docs/hermes/content-studio-agent/README.md](../../../docs/hermes/content-studio-agent/README.md)
- [HERMES_HOME_GUIDE.md](../../../docs/hermes/content-studio-agent/HERMES_HOME_GUIDE.md) — `.hermes` 目录说明

## 从本机回灌

```bash
./sync-from-live.sh
```
