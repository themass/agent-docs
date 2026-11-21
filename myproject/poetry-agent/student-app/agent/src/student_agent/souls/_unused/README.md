# 不生效的 soul

这两个文件**从未被加载**，放在这里只是为了留着当初的设计文字。

- `evaluator.md` — 评估。实际实现是 `evaluator.py`，**纯关键词规则，不调用模型**，因此不需要 soul。
- `reviewer.md` — 审校。实际实现是 `reviewer.py`，**纯规则**（长度、越界、uses 核对），同样不调用模型。

`service.py` 只加载 `guide.md` / `poet.md` / `narrator.md`（见 `LLM_ROLES`）。
如果将来评估或审校要走模型，再把对应文件移回上一级并加进 `LLM_ROLES`。
