# 01 — `manager` 编排闭环源码走读

> 文件：`src/lh_harness/manager.py`（约 2241 行）  
> 入口：`async def run` → `async def _run_impl`

---

## 0. 两个入口的分工

```117:151:src/lh_harness/manager.py
async def run(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Run the management loop and always leave a durable terminal record.
    ...
    """
    task = str(kwargs.get("task") or "")
    config = kwargs.get("config")
    try:
        return await _run_impl(*args, **kwargs)
    except asyncio.CancelledError as exc:
        return _write_terminal_failure(..., status="cancelled", ...)
    except BaseException as exc:
        return _write_terminal_failure(..., status="failed", ...)
```

**设计意图（注释原文）**：历史上只有 happy path 写 `report.json`，异常时 Supervisor 会误判「已完成」。  
因此：

- **内核**在 `_run_impl`  
- **`run` 是唯一崩溃/取消护栏**：任何 `BaseException`（含 `KeyboardInterrupt`）都落盘终端失败记录  

调试「worker 没 report」时先看是否绕过了 `run()`。

---

## 1. `_run_impl` 签名：角色绑定

```154:222:src/lh_harness/manager.py
async def _run_impl(
    *,
    task: str,
    env: Environment,
    config: HarnessConfig,
    agent: AgentAdapter | None = None,
    auditor_agent: AgentAdapter | None = None,
    manager_agent: AgentAdapter | None = None,
    gui_executor_agent: AgentAdapter | None = None,
    cli_executor_agent: AgentAdapter | None = None,
    gui_auditor_agent: AgentAdapter | None = None,
    cli_auditor_agent: AgentAdapter | None = None,
    ...
    human_hook: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
```

启动时 **一次解析** fallback：

```text
manager_agent     = manager_agent or agent
gui/cli_executor  = … or agent
gui/cli_auditor   = … or auditor_agent or agent
```

缺任一角色且无 default `agent` → `ValueError`。  
主循环里不再做 adapter 回退——注释：*loop stays focused on state transitions*。

### 回调语义

| 回调 | 时机 | 失败策略 |
|------|------|----------|
| `progress(event, payload)` | 同步状态行（CLI 打印） | try/except 吞掉，**绝不**打断 run |
| `human_hook(context)` | 每轮结束（及完成/阻塞/询问） | 返回 `continue`/`stop` + 可选 instructions / extra_rounds |

---

## 2. 落盘布局（循环开始前）

```232:283:src/lh_harness/manager.py
    log_dir = Path(config.log_dir).expanduser().resolve(strict=False)
    role_dir = log_dir / "role_orchestration"
    rounds_dir = role_dir / "rounds"
    events_path = role_dir / "events.jsonl"
    ...
    await _ensure_remote_layout(env, config)
    _append_event(events_path, "role_harness_start", {...})
    rounds: list[ManagedRound] = []
    current_task_state = ""
    current_task_contract = ""
    gate = _GateContext(...)
```

| 路径 | 用途 |
|------|------|
| `role_orchestration/events.jsonl` | 编排事件流（start/role/done/cancel） |
| `rounds/round_NNN/` | 该轮全部输入输出文本 + 轨迹 |
| `*_episodes/` | 按角色归档的 episode 产物 |
| `report.json` | 终态（log_dir 与 role_dir 各一份） |

`log_dir` **强制 resolve**：相对路径在不同 cwd 下否则会撞 event id（注释说明）。

---

## 3. while 主循环骨架

```285:289:src/lh_harness/manager.py
    while round_index < gate.round_budget:
        round_index += 1
        round_dir = rounds_dir / f"round_{round_index:03d}"
```

`gate.round_budget` 可被 human_hook 的 `extra_rounds` 拉长；初始来自 `config.max_total_episodes`。

### 3.1 Manager 阶段（每轮必跑）

```291:338:src/lh_harness/manager.py
        manager_prompt = build_role_manager_prompt(
            task=task,
            rounds=rounds,
            round_index=round_index,
            task_state=current_task_state,
            task_contract=current_task_contract,
            round_budget=gate.round_budget,
            language=config.prompt_language,
            max_history_chars=config.role_history_chars,
        )
        # carryover_instructions 注入（dashboard）
        manager_result = await _run_role_episode(
            manager_agent, manager_prompt, env, manager_budget,
            live_trajectory_path=str(round_dir / "manager_raw_trajectory.jsonl"),
        )
```

**信息隔离（注释）**：

> Manager sees original task, maintained task state, and auditor reports.  
> **It never receives raw trajectories or previous full prompts.**

随后：

1. `cancelled` → 记 abort，`break`  
2. `classify_agent_runtime_failure` → 合成 `Next: blocked` 的 `ManagedRound`，`break`  
3. `extract_role_manager_plan_text` → 空则合成 blocked  
4. 抽取并持久化：`task_state` / `task_contract` / `related_report_refs`  
5. `parse_role_manager_next_step(plan_text)` → 路由

### 3.2 路由分支（源码顺序）

| `next_step` | 行为 | 关键守卫 |
|-------------|------|----------|
| `done` | 若 `_latest_auditor_is_clean_complete` → `completion_satisfied` + human_gate | **否则**写入 `_invalid_completion_feedback`，当 `invalid` 续跑 |
| `blocked` | 记 round → human_gate(`blocked`) | |
| `ask` | 抽 question/choices → human_gate(`ask`) | 答案进下一轮 carryover |
| `invalid` | `_invalid_plan_feedback` → 当审计反馈 | |
| `gui` / `cli` | 进 Executor → Auditor | |

伪完成路径（必须读注释）：

```446:484:src/lh_harness/manager.py
        if next_step == MANAGER_NEXT_DONE:
            if _latest_auditor_is_clean_complete(rounds, language=config.prompt_language):
                gate.completion_satisfied = True
                ...
                if await _human_gate(gate, "completed", ...):
                    break
                continue
            # Completion is not accepted unless grounded in previous clean auditor report
            repair_report = _invalid_completion_feedback(...)
            record = ManagedRound(..., next_step=MANAGER_NEXT_INVALID, harness_feedback=repair_report, ...)
```

**公理落地**：没有干净审计，Manager 自称完成无效。

### 3.3 Executor 阶段

```546:588:src/lh_harness/manager.py
        executor_agent, executor_budget = _executor_binding(next_step=..., ...)
        auditor_for_step = gui_auditor_agent if next_step == GUI else cli_auditor_agent
        related_auditor_reports = format_related_auditor_reports(
            rounds, related_report_refs, max_chars=config.role_verified_context_chars, ...
        )
        executor_prompt = build_role_executor_prompt(
            task, plan_text, next_step, task_state, task_contract,
            related_auditor_reports, workspace_path, ...
        )
        executor_result = await _run_role_episode(executor_agent, ...)
```

- GUI 结束后可 `_capture_environment_screenshot`  
- 失败/取消与 Manager 对称：写 feedback、event、可选 `break`  
- 成功：`executor_output` 写入磁盘与 remote

**上下文边界**：Executor 只拿 Manager 点名的 related auditor reports，不是全历史。

### 3.4 Auditor 阶段

```694:890:src/lh_harness/manager.py
        auditor_prompt = build_role_auditor_prompt(
            task, plan_text, executor_output, next_step, task_state, task_contract,
            related_auditor_reports, workspace_path,
            max_executor_output_chars=config.auditor_output_chars, ...
        )
        auditor_result = await _run_role_episode(auditor_for_step, ...)
        auditor_report, auditor_status = await _auditor_report_with_format_repair(...)
        record = ManagedRound(..., auditor_report=auditor_report, ...)
        rounds.append(record)
        await _record_round(...)
        audit = parse_audit_report(auditor_report, round_index, ...)
        if await _human_gate(gate, "progress", ...):
            break
```

要点：

- Auditor **只审刚结束的子任务**（注释）  
- 报告自然语言 → 结构化靠 `auditor_agent` / format repair  
- 每轮正常进度路径末尾都过 human_gate（dashboard 可注入指令而不停）

---

## 4. `_run_role_episode`：取消归一化

```1104:1127:src/lh_harness/manager.py
async def _run_role_episode(agent, prompt, env, budget, *, live_trajectory_path=None) -> EpisodeResult:
    try:
        return await agent.run_episode(prompt, env, budget, live_trajectory_path=...)
    except asyncio.CancelledError:
        return EpisodeResult(status="cancelled", error="Execution cancelled by operator", ...)
```

Adapter 抛 `CancelledError` 与返回 `status=cancelled` **统一成 EpisodeResult**，主循环用同一套分支处理。

---

## 5. 循环结束：终态报告

```892:928:src/lh_harness/manager.py
    final = _final_report(
        task=task, rounds=rounds,
        completion_satisfied=gate.completion_satisfied,
        abort_reason=gate.abort_reason,
        last_plan=last_plan, task_state=..., task_contract=...,
        max_rounds=..., elapsed_seconds=..., final_response=gate.final_response,
        failure_reason=gate.failure_reason,
    )
    _write_local(role_dir / "report.json", ...)
    _write_local(log_dir / "report.json", ...)
    ...
    _append_event(events_path, "role_harness_done", final)
    return final
```

另写 `orchestration_transcript.txt`、合并 episode logs、远程 harness_dir 镜像。

---

## 6. 一次成功 gui 轮的调用栈

```text
run()
  _run_impl()
    while:
      build_role_manager_prompt
      _run_role_episode(manager) → AgentAdapter.run_episode → env.exec(claude/codex)
      parse_role_manager_next_step → "gui"
      build_role_executor_prompt
      _run_role_episode(gui_executor)
      build_role_auditor_prompt
      _run_role_episode(gui_auditor)
      _auditor_report_with_format_repair
      ManagedRound append + _record_round
      _human_gate("progress")
    _final_report + report.json
```

---

## 7. `_human_gate` 续跑语义（源码）

```1057:1088:src/lh_harness/manager.py
    if action == "stop":
        ...
        return True

    # continue: reopen / extend the budget when we were about to finish.
    if ctx.final_response:
        ctx.final_response = ""
        await _discard_final_response(ctx)
    if outcome == "completed":
        ctx.completion_satisfied = False
    if reached_max or outcome in ("completed", "blocked"):
        extra = int(decision.get("extra_rounds") or ctx.config.max_total_episodes or 1)
        ctx.round_budget = round_index + max(1, extra)
        _append_event(..., "human_continue_after_finish", ...)
    return False
```

要点：

1. **先写 final_response 再问人**（ending 场景）：操作员看到的是真实答复，不是空白。  
2. **continue 会丢掉刚写的 final_response**——因为 run 不再结束，答复会过期。  
3. **continue after completed** 会把 `completion_satisfied` 打回 `False`——必须再跑出干净完成。  
4. **延期**：`round_budget = round_index + extra`，不是简单 `+= max_total`。

无 hook 时：`progress` 返回 False（不停）；`completed/blocked/ask/max` 返回 True。

---

## 8. Format repair 完整路径

```1142:1209:src/lh_harness/manager.py
    raw_report = auditor_report_text_from_episode_result(primary_result)
    if not _should_repair_auditor_format(...):
        return _auditor_report_text(primary_result, ...), status
    repair_prompt = build_role_auditor_format_repair_prompt(...)
    repair_result = await _run_role_episode(format_repair_agent, ...)
    if repair_valid:
        corrected = EpisodeResult(..., actions_log=repair_raw_report, metadata=primary_result.metadata)
        return _auditor_report_text(corrected, ...), status
    return _auditor_report_text(repair_result, ...), status
```

- 修的是 **格式/控制头**，不是让模型改口「其实完成了」。  
- 接受 repair 时 **保留 primary metadata**（含 mutation 标志）——防止 format 修复洗掉只读违规。  
- 拒绝 repair 仍返回文本，交给后续 `parse_audit_report`；不会假 complete。

---

## 9. `_final_report` 字段字典

| 字段 | 含义 |
|------|------|
| `schema_version` | 2 |
| `status` | complete / cancelled / failed / blocked / incomplete |
| `completion_satisfied` | 门禁布尔 |
| `completion_authority` | 恒为 `manager_with_role_auditors` |
| `abort_reason` | user_cancelled / manager_blocked / max_rounds… / provider_* |
| `failure_reason` | 给 UI 的供应商原文 |
| `rounds` | 全量 `ManagedRound` asdict |
| `latest_auditor_report` | 最近一份报告文本 |
| `final_response` | 自然语言收尾（若已写） |

Supervisor 应优先信这些字段，而不是 worker exit code。

---

## 10. 调试断点

| 现象 | 看 |
|------|-----|
| 自称完成却继续跑 | `MANAGER_NEXT_DONE` + `_latest_auditor_is_clean_complete` 三条件 |
| Manager 看到轨迹 | `build_role_manager_prompt` 是否被改串了 actions_log |
| 轮次超预算 | `gate.round_budget` / `human_continue_after_finish` |
| 无 report.json | 是否调用了 `run` 而非裸 `_run_impl` |
| 角色超时 | 对应 `EpisodeBudget`；tee 是否保留 |
| continue 后仍显示旧答复 | `_discard_final_response` 是否跑到 |
| repair 洗掉 mutation | repair 是否错误清空了 metadata |

下一篇：[02-adapters-env-auditor.md](./02-adapters-env-auditor.md)
