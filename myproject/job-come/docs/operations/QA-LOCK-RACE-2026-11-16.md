# 快照版本号竞态（第二轮）：多提交函数的锁释放

- 日期：2026-11-16
- 修复提交：`fe77c30`（基于 `addbb4c` 的行锁修复）
- 状态：本地与远程数据库验证通过，**待部署**（本机 1Password SSH agent 未运行，无法 SSH）

## 现象

`addbb4c` 部署后，生产日志在 16:49–16:50 仍出现 `UniqueViolation`，失败点为后台任务
`prepare_resume_tracks`，冲突索引仍是 `ix_jc_profile_snapshot_profile_version`
`(profile_id, version_after)`，随后级联 `PendingRollbackError` 使整个请求失败。

## 根因

`ResumeService.prepare_tracks` 在函数开头取一次 `FOR NO KEY UPDATE`，但函数内有三个
`row.version += 1` + `commit()` 块。**COMMIT 即释放行锁**：第一次提交后，翻译成功路径和
翻译失败路径的两次 version bump 都在无锁状态下运行。该任务在后台执行，与用户驱动的档案写
并发时，两边读到同一 version、算出同一后继版本，快照唯一索引拒绝其中一个。

同源漏网：`mcp/handlers.py::intake_record` 仍在用普通 `get_by_id` 后直接 bump——旧的源码
守卫只扫描 `services/`，看不到 `mcp/`。

## 修复（fe77c30）

1. `prepare_tracks` 成功分支与异常分支：在分钟级 LLM 翻译返回**之后**重新
   `get_for_update` 再做 read-modify-write。锁只覆盖几毫秒的写入，不包裹整个 LLM 调用。
2. `mcp/handlers.intake_record` 改用 `get_for_update`，与 HTTP intake 路径同一契约。
3. 守卫测试 `test_profile_write_locking.py` 用 AST 重写：
   - 扫描范围从 `services/` 扩大到整个 `src/jc`；
   - AST 识别真实 `AugAssign`，天然排除 docstring 里的字面文本；
   - 新增第二类违规：最近一次取锁与 bump 之间存在 `commit()`（即锁已被释放）。
   - 变异测试验证：删掉成功分支的重新取锁后，守卫精确报错
     `services/resume_service.py:750 (lock from line 712 released by commit at line 732)`。

## 远程 Postgres 双向验证（newdb.sspacee.com/job_come）

8 线程 × 3 轮 = 每个档案 24 次 bump，临时档案跑完即删（快照外键 ON DELETE CASCADE）：

| 模式 | 结果 | 最终 version | 快照序列 |
|---|---|---|---|
| 新（每轮重新 `FOR NO KEY UPDATE`） | **24/24 成功** | 25 | 2..25 无空洞 |
| 旧（普通 SELECT 后 bump） | 11 次中 **7 次 IntegrityError** | 5 | 4 行 |

旧模式稳定复现生产冲突，新模式在同等并发强度下零失败——诊断与修复同时得到证明。

## 部署步骤（web 用户，勿用 root）

```bash
cd ~/work/agent-docs && git pull --ff-only
cd myproject/job-come
./scripts/publish.sh --deploy --restart -- --skip-frontend
```

纯后端改动，跳过前端构建。部署后验证：

```bash
grep -c "UniqueViolation" .data/logs/production/api.log   # 重启后应不再增长
./scripts/backend.sh status && curl -sf http://127.0.0.1:8000/health && echo API-OK
```

## 备注

- 本地全量 pytest：1043 passed，1 failed 为环境缺 `jc[export]`（playwright 未装），与本改动无关。
- `test_resume_repair.py` 两个失败同为本地 venv 的 agentkit 旧拷贝漂移，`setup-venv.sh` 重同步后消失。
