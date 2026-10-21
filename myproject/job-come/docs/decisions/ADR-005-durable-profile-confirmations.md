# ADR-005：简历修改确认使用持久化命令，不使用 Redis TTL

- 状态：接受
- 日期：2026-10-19

## 故障证据

`POST /agent/sessions/{id}/confirm` 的日志显示：`get_pending` 未命中后，
`apply_confirmed_patch` 抛出未处理的 `ValueError("Confirm request expired or not found")`，返回 500。
确认卡片长期保存在 `jc_agent_message`，待执行 patch 却仅保存在两小时 TTL 的 Redis key。
因此 Redis 过期、清空或配置变化后，历史页面仍提供无法兑现的确认按钮。
日志只证明 key 不存在，不能据此断言这次一定是 TTL 过期。
此外，原实现先 GETDEL，再写数据库；数据库写入失败也会永久丢失确认。

## 决策

增加 `jc_profile_patch_confirm`，表示一个待用户决策的写入命令：

- 保存 owner、session、profile、patch、预览的版本号；不重复保存全量合并简历。
- `pending → applied | rejected`；不因时间到期删除，不依赖本地文件或 Redis。
- MCP 必须提交命令后才返回 `pending_confirm`，确保用户看到的卡片可被服务端解析。
- 确认时先锁定所属会话，再读取命令。锁只覆盖短暂的数据库写入，不覆盖模型推理，
  不串行化其他会话或其他用户。MySQL 多实例共用同一数据库行锁。
- 写入使用原有 `Profile.version` CAS。profile、版本快照、命令状态、决策事件同事务提交。
  任何一项失败都回滚，命令仍可重试。
- 对同一确认重复批准返回原应用版本，不再次写简历、不重复新增决策事件。
- 已拒绝命令不可批准，已批准命令不可拒绝；撤销使用版本历史，不改写决策记录。
- message 是 UI/审计投影，不负责执行命令。trace 和 llm_call 不承担命令存储职责。

## 历史卡片兼容

新表找不到记录时，只允许从该用户所属 session 的服务端 `confirm` 事件恢复。
必须存在 patch、profile_id、整数 `preview.version_before`；客户端不提供 patch。
恢复后仍经过原版本 CAS，禁止把旧 patch 自动套用到最新简历。
已有决策记录、缺失版本或缺失卡片分别返回可理解的业务错误，不抛裸 ValueError。

## 部署

迁移：`backend/server/alembic/versions/014_profile_patch_confirm.py`。
从项目根执行 `./scripts/db_upgrade.sh`，再重启 API；常驻 MCP 进程也需随运行时重新加载。
多实例滚动升级时，应先执行迁移，随后更新所有 API / MCP 实例；旧实例仍可能使用 Redis。
不删除原 message/trace/llm_call，不主动清空 Redis。

## 验证边界

HTTP + 独立数据库会话集成测试验证确认、拒绝、重复请求、三天前的命令、跨用户/会话、
历史恢复、版本冲突，以及 UPDATE 后审计失败的整事务回滚。
SQLite 测试不证明 MySQL 多进程真实竞争；行锁与 CAS 的生产竞争行为仍需 MySQL 环境验收。
前端投影单元测试验证确认成功/拒绝后历史卡片状态；隔离浏览器脚本已补充刷新后按钮检查。
本轮真实浏览器复验受本地 3000 服务连接拒绝阻断，未将其计为验收通过。

## 2026-10-19 补充：确认成功但正文不变

实际 trace 提交 `experiences[1].highlights[0]` 路径型 patch。旧 deep-merge 将路径
当成顶层键，随后 ProfilePayload 的 extra-ignore 丢弃该键，却照常增加版本、标记 applied。
因此版本递增不等于内容已修改。

现提议与确认共同调用纯函数 `profile_patch_ops.apply_profile_patch`：
- 支持嵌套部分对象和明确的点/数组路径；检查路径存在、下标范围、互相重叠；
- 严格拒绝任意层级被模型校验丢弃的未知字段及无实际变化的修改，不再返回假成功；
- 重新投影源语言展示字段，将另一语言标记 stale，防止旧翻译覆盖确认内容；
- 延续确认命令的 ownership/CAS/快照/单事务提交，不绕过已确认状态或重放旧 applied 命令。

优化预览同时按 profile_version 失效，前端监听档案版本并重读预览，过期响应不覆盖新预览。
已经 applied 的历史空操作不会自动重放：无法安全推断用户之后的编辑意图，应基于最新档案
生成新的确认；这是避免旧提案覆盖当前档案所必须保留的边界。此次无需新增数据库迁移。
