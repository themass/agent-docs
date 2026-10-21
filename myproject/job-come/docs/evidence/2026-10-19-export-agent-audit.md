# 导出与 Agent 故障自查（2026-10-19）

## 范围与证据边界

本轮检查实际代码、只读健康检查、最近导出任务元数据与最近三个已保存文件；没有重放真实用户请求、调用真实付费模型、修改业务数据库或重启用户服务。

- API 8001 与前端 3000 `/health` 都返回 200。
- 最近三个任务（北京时间）：PDF 15:26:22、DOCX 15:29:32、HTML 15:31:36 均为 done。
- 取回对象字节后执行真实 `validate_export`：PDF 423402 bytes / 2页；DOCX 85194 bytes；HTML 91438 bytes；每份51个文本字段检查通过。
- 另对三份文件实际签名下载链接执行只读 HTTP GET，均返回 200，Content-Type/字节数/文件签名正确。
- 这些证据证明文件生成/保存及当前下载地址成功，不证明用户当时的代理响应与浏览器下载成功。未取得当次 HTTP traceback，不把当前发现的隐患冒充那次失败的唯一根因。

## 本轮修改

| 问题 | 修改 | 不付费回归证据 |
|---|---|---|
| 每次导出重新跑模型质检，3格式重复付费/等待 | 质检留在 review 端点；导出只读取指定稿，保留既有 reviewer verdict | mock reviewer 配成一调用就抛错，实际3格式仍通过 |
| 慢渲染/存储期间持有DB事务 | 先快照、释放读事务、提交 PROCESSING，再在线程执行渲染/校验/上传/签名 | 真实SQLite会话，expire_on_commit=True；渲染/上传断言无事务 |
| 失败后使用 broken transaction，二次报错 | rollback 后按纯量job ID重查，再持久化分阶段失败 | 注入真实IntegrityError、上传/签名/渲染失败；独立会话检查最终failed |
| DOCX导出依赖无关的HTML模板渲染 | DOCX直接走自身renderer | 真实DOCX生成与文本保留检查 |
| 指定review draft不存在却回落到另一份稿 | 明确 draft_id 必须存在且属于当前profile | missing draft拒绝测试 |
| 大patch仍会被DeerFlow工具输出预算外置，确认卡消失 | 超阈值只给模型短回执；SSE服务按owner/session/profile从持久化确认表补齐原patch | 18000字修改，短回执→confirm映射→数据库hydration→真实HTTP确认→独立会话正文读回 |
| UI看到确认/错误后断流，事件尚未提交 | 持久化事件提交后再yield；每事件释放事务 | 在confirm yield处关闭生成器并rollback，记录仍在 |
| 工具执行后异常但没有文字，历史却补“处理完成” | error轮次禁止成功占位文案，保留错误事件和已有部分文字 | 失败工具轮次回放无虚构成功回复测试 |
| done先于最后回复落库，前端可提前出队下一条 | done延后至最终assistant/history提交之后 | 收到done时检查无事务且完整assistant已保存 |
| trace序号依赖前端串行队列，COUNT有删除缺口风险 | 每session短DB锁，当前读最大seq+1；FK子行写之前先锁父行 | gaps测试；SQLite不能证明MySQL跨实例并发，见下文 |
| full_reasoning/tool_result同时写UI TEXT并发SSE，重复且可能超64KB | 全量只保留trace；UI消息/网络不含full_* | 全量trace保留、SSE和message排除测试 |
| 正常长回复/大确认卡仍可能超过jc_agent_message TEXT | 015迁移把content/payload_json扩为LONGTEXT | MySQL dialect DDL类型断言；迁移尚未在用户DB执行 |

## 必须明确的剩余风险（本轮没有完成）

1. **P1，多实例运行态仍不是共享的**：`deerflow_harness_client._SESSION_CANCEL` 是进程内字典，取消请求落在另一个worker会找不到运行；默认checkpoint backend仍为SQLite。确认命令是共享DB持久化，不代表整个Agent已经多实例安全。需要单独的共享checkpoint、运行租约、跨worker取消信号设计与验收，不能只改一个env声称完成。
2. **P1，同一session多标签/多实例同时发起模型run**：trace追加序号已加短锁，但这只保证账本序号，不提供整个模型run的跨实例串行化。前端队列不构成服务端互斥。真实MySQL锁/同session并发尚未压测，不宣称已经验证。
3. **P2，中断导出留PROCESSING**：本轮先提交PROCESSING避免任务凭空消失，但进程被kill或请求取消时，尚无共享worker/reconciler将遗留任务转成可恢复状态。同步HTTP导出仍可能受极慢存储或代理超时影响；移到线程只消除event loop阻塞，不等于作业队列。
4. **P2，导出页异步竞态**：`ResumeExportStep`的review/export响应没有draft epoch guard；切换draft/语言时，旧响应可能覆盖新页面状态。应补隔离浏览器的乱序响应测试后修，不以tsc当作交互验收。
5. **P2，列表替换语义**：通用profile patch对数组仍是整体替换；具体字段路径可以安全局部改，但模型提交不完整经历数组仍可能删掉其他条目。当前用户确认+版本快照是保护，不等于自动防遗漏。需显式删除/替换契约和更清晰diff。
6. **P2，已有错误历史不会自动修复**：之前误标applied的旧确认不能直接重放，以免覆盖后续用户修改。新patch验证/新预览链路已修，历史数据如需修复要按版本审计。
7. **没有新做真实模型质量验收**：确定性测试能挡住结构/事务/事件问题，不能证明真实模型永不漏改或虚构；不能拿“测试全过”替代事实忠实度评测。

## 用户需要执行

新增迁移不是新增表：`backend/server/alembic/versions/015_agent_message_longtext.py`。
从项目根执行 `./scripts/db_upgrade.sh` 后，自行重启前后端；本轮未替用户执行迁移/重启。
迁移只加宽两列，保留已有数据；downgrade不缩列，避免审计内容截断。

## 回归入口

- `backend/server/tests/test_export_lifecycle.py`：真实SQL、真实3格式renderer/quality，失败注入；无付费模型。
- `backend/server/tests/test_profile_confirmations.py`：确认、版本、权限、幂等、长patch完整应用。
- `backend/server/tests/test_agent_trace_stream_wiring.py`：流事件落库、断流、done顺序、全量trace与UI隔离。
- `backend/server/tests/test_agent_trace_store.py`：session序号、删除缺口。
- PDF需要本地Chromium可启动；沙箱MachPort拒绝不等于业务渲染失败。

## 本轮执行结果

- 后端本地套件最终复跑：897 passed、6 skipped、4 deselected（PDF/外部浏览器另跑）。
- 真实三格式/PDF套件：23 passed（含真实Chromium、模板质量、失败事务回滚）。与上面的后端测试有重叠，不能相加成独立覆盖数。
- 前端Node：23 passed；TypeScript `tsc --noEmit`通过。
- 隔离浏览器 `verify_confirmed_preview.py`：确认→版本刷新→重新预览→新要点可见，通过。
- Alembic 015离线SQL生成通过；未执行真实迁移。
- 新增 `scripts/check-export-agent.sh` 提供无真实模型/业务DB的专项回归入口，实际执行82 passed（随后新增的失败轮次回放测试也单独通过并包含在最终897中）。
- 存在第三方deprecation、LiteLLM测试清理warning等既有告警；不是“零告警”报告。故意注入重复主键产生的SAWarning是失败回滚测试的一部分。
