# 合订本构建（历史工具，非日常维护入口）

> 现行 `volumes/` 含手写增补；日常直接编辑对应分卷。校订 `archive/legacy/` 时也不要运行下面旧流程覆盖分卷。详见 `../archive/legacy/DOC_MAINTENANCE.md`。

```bash
cd docs/hermes/docs
python3 _merge/build_volumes.py
```

- **输入**：`archive/legacy/*.md`（合并前单篇归档）  
- **输出**：`volumes/*.md`（9 卷合订本）  
- **`sources/`**：可选本地快照；若比 legacy 新会覆盖同步到 legacy  

`volumes/` 现在是手写的设计章，不要用本脚本覆盖。长文仍在 `archive/legacy/`。确认要退回「按篇拼接」时才设置 `HERMES_REBUILD_VOLUMES=1`。
