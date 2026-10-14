# 恢复 AgentScopev2.md 完整长文

## 发生了什么

1. **2026-10-12**：将你的 ~3705 行笔记 **重组为九部分 + 附录**（`_reorganize_v2.py`），技术正文保留，仅删 UI 垃圾行。
2. **2026-10-12 晚 / 2026-10-13**：误把「去掉 v1」理解成 **整篇替换为 ~350 行简版**，导致崩溃推演、DB 改造、模块 1–11 等 **大量段落丢失**。  
   该文件 **从未进 git**，无法 `git checkout` 恢复。

**正确规则（你的要求）**：

- 只删 **纯 v1、且 v2 已不成立** 的叙述；
- **v1→v2 未变的设计**（Session 快照、EventStream、DataBlock、权限链路等概念模型）**必须保留**，必要时用附录做 **命名对照**（`AgentState.context` 等），而不是删章节。

## 请你先恢复本地历史（推荐）

在 Cursor / VS Code 中：

1. 打开 `docs/agentscope/AgentScopev2.md`
2. 资源管理器右键该文件 → **Open Timeline** / **本地历史**
3. 选择 **2026-10-12** 中体积约 **130KB / 3700 行** 的版本（重组后长文或重组前原文均可）
4. **Restore** 到工作区

若 Timeline 里没有：

- macOS **Time Machine** 还原该文件  
- 或从备份/U 盘/另一台机器拷贝原始 `AgentScopev2.md`

## 恢复后在本目录执行

若恢复的是 **重组前** 的乱序原文：

```bash
cd docs/agentscope
python3 _reorganize_v2.py          # 生成九部分 + 附录 A–F
python3 _strip_v1_only.py AgentScopev2.md --dry-run   # 预览将删行数
python3 _strip_v1_only.py AgentScopev2.md             # 仅删纯 v0.x 专节（默认很保守）
```

若恢复的是 **重组后** ~3703 行版本：

```bash
cd docs/agentscope
python3 _strip_v1_only.py AgentScopev2.md --dry-run
python3 _strip_v1_only.py AgentScopev2.md
```

然后手工检查：文首保留「阅读导航」；**不要**再整篇替换为简版。当前误生成的简版已另存为 `AgentScopev2.v2-brief.md`（恢复成功后可删）。

## 若无法恢复

请把能找到的 **任何副本**（哪怕旧导出）放到 `AgentScopev2.source.md`，再联系协助合并；仓库内 **没有** 完整长文的第二份拷贝。
