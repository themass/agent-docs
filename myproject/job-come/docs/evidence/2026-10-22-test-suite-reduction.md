# 测试套件缩减至核心流程（2026-10-22）

## 做了什么

后端测试从 **126 个文件 / 962 个测试函数** 缩减到 **7 个文件 / 21 个测试函数**
（27 个用例，含参数化）。全量运行时间从 40 秒降到 **2.7 秒**。

保留的是端到端流程，不是单点行为：

| 文件 | 个数 | 覆盖的流程 |
|---|---|---|
| `test_v1_mcp_contracts.py` | 4 | agent 工具面：提议→确认卡→写档案、模型无法自行 apply、跨用户越权被拒、重复确认幂等 |
| `test_profile_confirmations.py` | 3 | 确认→档案：路径型 patch 真的落库、他人命令不可消费、失败不半保存 |
| `test_preview_execution.py` | 5 | 档案→预览→缓存：已确认文字存活、缓存命中与失效、写手失败不缓存、降级可见、范围行来源 |
| `test_resume_repair.py` | 6 | 生成→评估→修复：不触发的情况、端到端修回丢失事实、三道闸、不改身份字段、坏掉不影响预览 |
| `test_export_lifecycle.py` | 2 | 预览→导出：三种格式产出、审稿结论被保留 |
| `test_profile_ingest_service.py` | 1 | 上传→结构化档案 |

`conftest.py` 保留（10 个 fixture）。`test_profile_confirmations.py` 另外为
`test_preview_execution.py` 提供 `env` / `click` / `scope` fixture，不能删。
`FIXTURE_SECTIONS` 原本从 `test_export_pdf.py` 导入，该文件已删除，已就地内联。

## 这是一个有代价的取舍

删掉的 941 个测试里包含为真实事故补的回归：确认成功但正文不变（ADR-005）、
`payload_json` 写入 base64 导致 MySQL TEXT 溢出（原注释写明测试跑 SQLite
测不出来，只能断言序列化字节数）、项目叙事被拆散、权限边界与事务回滚。

**这些保护现在没有了。** 本次缩减的理由是开发节奏，不是这些测试没价值。
下次在这些区域改动时，没有东西会提醒你改坏了。

**运行时间从来不是瓶颈**：缩减前全量 40 秒。真正的耗时在开发侧的代码探查。
记在这里是为了避免以后误以为「测试慢」已经被解决了。

## 如何恢复

全部删除都在 git 历史里，随时可取回单个文件：

```bash
git show <本次提交>^:myproject/job-come/backend/server/tests/test_agent_attachments.py \
  > myproject/job-come/backend/server/tests/test_agent_attachments.py
```

或整体恢复 `tests/` 目录：

```bash
git checkout <本次提交>^ -- myproject/job-come/backend/server/tests/
```

建议在重新改动权限、确认命令、导出闸门这些区域之前，先把对应的测试文件取回来。
