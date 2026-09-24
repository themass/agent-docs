# 压缩源码归档（索引）

> **全文已移至** [_archive/13-compression-source-archive.md](./_archive/13-compression-source-archive.md)（~6000 行逐行 walkthrough）。  
> **设计层请读**：[07-compression.md](./07-compression.md) · [00-HARNESS-DESIGN-PHILOSOPHY.md](./00-HARNESS-DESIGN-PHILOSOPHY.md) §第 5 步

---

## 归档里有什么

- 各框架压缩函数的源码级逐步说明  
- C01–C22 方案与实现对照的冗长展开  
- 与 [07-compression.md](./07-compression.md) 矩阵 **内容重叠**，仅多路径细节

## 设计层已覆盖

| 问题 | 读 |
|------|-----|
| 六层压缩模型 L0–L5 | [07-compression](./07-compression.md) §2 |
| 改 S 还是只改 L | [07-compression](./07-compression.md) §4 |
| 选型决策树 | [07-compression](./07-compression.md) §5 |
| 黄金法则 | [07-compression](./07-compression.md) §7 |
