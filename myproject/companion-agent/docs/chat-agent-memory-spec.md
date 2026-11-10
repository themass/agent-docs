# 记忆接口规范 v1

版本：1（`companion/ports/memory.py` 中 `SPEC_VERSION = "1"`）。本文档是记忆接口的唯一规范。
代码中的 `MemoryPort` 是它的实现形式；任何记忆后端只要满足本规范，就可以替换，调用方（app、api、memory_hub）不需要改动。

## 1. 原则

1. **隔离靠 user_id，且必须由存储原生支持**：不同用户之间互相不可见，不依赖 metadata 过滤。
2. **后端无关**：调用方不得依赖任何后端的 id 格式、排序细节、分数含义或错误类型。
3. **错误可区分**：调用方错误 → `MemoryInvalid`；后端暂时不可用 → `MemoryUnavailable`；不得返回部分结果冒充完整结果。
4. **写入不覆盖**：同一个 id 不能被第二次写入。修改一条记忆 = 删除 + 新增（v1 不提供原地更新）。

## 2. 数据模型

### 2.1 MemoryItem

| 字段 | 类型 | 写入时 | 说明 |
|---|---|---|---|
| `id` | str | 可空 | 为空时由后端分配（非空）。返回值中必然非空，且在同一后端内唯一 |
| `content` | str | 必填 | 去首尾空白后非空；长度 ≤ 300 字符 |
| `kind` | MemoryKind | 默认 FACT | 取值见 2.2 |
| `source_character_id` | str | 可空 | 审计字段，原样保存并返回 |
| `source_message_id` | str | 可空 | 审计字段，原样保存并返回 |
| `created_at` | datetime | 可空 | 为空时由后端填写；返回值为 UTC 时间 |
| `score` | float \| None | 忽略 | 仅 search 结果中有意义（越大越相关）；写入与列表结果为 None |

### 2.2 MemoryKind

`FACT`、`PREFERENCE`、`EVENT`。字符串值跨后端保持不变。

## 3. 操作

`user_id` 为 `app:uid`（memory_hub 生成）或裸 uid；非空，至多一个冒号。

| 操作 | 语义 | 错误 |
|---|---|---|
| `add(user_id, items) -> list[MemoryItem]` | 原子写入一批，返回后端确认后的条目 | 批量 > 50、内容不合法、id 重复 → `MemoryInvalid`，整批不写入 |
| `search(user_id, query, limit=5, kinds=None) -> list[MemoryItem]` | 召回最多 `limit` 条（limit 上限 20）；`kinds` 为空不过滤 | 同上 |
| `list_for_user(user_id, limit=50, offset=0) -> list[MemoryItem]` | 分页列出（limit 上限 100） | — |
| `delete_one(user_id, memory_id) -> bool` | 删除单条 | — |
| `delete_user(user_id) -> int` | 删除该用户全部记忆，返回条数 | — |

## 4. 列表与分页

4.1 排序：`created_at` 倒序；同一时间按 `id` 倒序。这一排序是全序，分页结果稳定。

4.2 在两次翻页之间没有被写入或删除的条目，不会重复或被跳过。

4.3 `limit` 超过上限时截断到上限，不报错。

## 5. 召回

5.1 结果只包含该用户的记忆；`kinds` 非空时只包含这些类型。

5.2 空查询（去空白后为空）返回空列表。

5.3 **词法后端（v1 参考实现）的排序是规范的一部分**：
- 文字切分见 `domain/memory/recall.py`：CJK 字符保留单字与相邻双字；其他文字按词（去标点、小写）；
- 分数 = 查询特征在记忆中出现的比例；只返回分数 > 0 的条目；
- 排序：分数降序，分数相同按 `created_at` 倒序，再按 `id` 倒序；
- 只参与排序的最近 500 条（按 `created_at` 倒序）。超出部分不参与召回，这是已知限制。

5.4 **语义后端**（未来，如向量检索）可以使用自己的排序，但必须满足：结果属于该用户；`kinds` 生效；数量 ≤ `limit`；`score` 按降序排列；空查询返回空列表。它不要求与 5.3 的结果一致。

## 6. 删除

6.1 删除是**真删除**：删除后，`list_for_user`、`search` 都不再返回该条目。不允许软删除后仍可召回。

6.2 `delete_one`：不存在、不属于该用户，都返回 `False`；调用方无法据此区分两者（不泄露存在性）。

6.3 `delete_user` 返回删除条数。是否完整，以删除后 `list_for_user` 为空为准，不能只看返回值。

## 7. 写入

7.1 `add` 是原子的：要么整批写入，要么一条都不写入。

7.2 批量上限 50 条；超出即 `MemoryInvalid`。

7.3 重复 id（与已有条目冲突，或同一批内重复）→ `MemoryInvalid`，整批不写入。后端不得覆盖已有条目。

7.4 写入后的读取（同一后端实例、同一 user_id）必须能立即看到该写入（read-your-writes）。

## 8. 错误

8.1 只允许抛出 `MemoryInvalid`（调用方错误，不应重试）与 `MemoryUnavailable`（后端故障，可重试）。

8.2 不得抛出后端原生的异常类型到调用方。

## 9. 版本与一致性测试

9.1 新后端接入的条件：通过 `tests/memory_conformance.py` 中的全部检查，并在 `memory_hub` 的配置中注册。

9.2 规范版本升级（如 v2）时，旧版本的后端必须继续工作，直到调用方全部迁移。

## 10. v1 不包含的内容

- 原地更新（用删除 + 新增代替）；
- 语义检索（需要嵌入模型，本项目暂不使用）；
- 跨应用共享记忆；
- 记忆内容的自动抽取（由 `app/memory/extraction` 负责，不属于存储接口）。
