# Cursor 测试结果 — 2026-11-19-R3 复验

## 结论

针对 R3 报告里的两个 P0（`0db95b2`：experiences id-merge + ingest_fast 去掉 `thinking`），**生产复验通过**：

| 旅程 | 结果 |
|---|---|
| Phase R（R1–R6） | R1–R4/R6 **PASS**；R5 **N/A** |
| Phase M（M1–M8） | **全 PASS**（M2/M4 首轮启发式漏检后复测 PASS） |
| Phase X | **全 PASS** |

- 代码 tip（本地）：`c5c83ee`（含 `0db95b2 fix(jc): R3 P0`）
- **不再需要 SQL 种子 Job**：正式 `POST /jobs/.../parse` → **200**，公司=`示例科技`
- 新缺陷：**无**；原 P0-1 / P0-P1-2 **关闭**
- 证据：`/tmp/jc-validation/2026-11-19-r3/prod-r3b/`

---

## 环境基线

| 检查 | 结果 |
|---|---|
| HEALTH | 200 |
| SIGN（无 cookie） | 200 |
| JD parse | **200** `job_r0i2kyc5r3mvzd3x` / 示例科技 |
| 相对 R3 首轮 | 修复 commit `0db95b2` 已部署生产 |

---

## 总表（生产）

| # | 复验 | 相对 R3 首轮 |
|---|---|---|
| R1 P99→110ms 且其它硬事实仍在 | **PASS** | 首轮 FAIL → 关闭 |
| R2 拒绝 | PASS | 仍绿 |
| R3 version 冲突 | PASS | 仍绿（`confirmation_stale`） |
| R4 禁虚构 | PASS | 仍绿 |
| R5 失败可观测 | N/A | 同首轮 |
| R6 刷新对账 | PASS | 仍绿 |
| M1 最短完整场 | **PASS** | 首轮靠 SQL 种子 → 现走正式 parse |
| M2 弱答追问 | **PASS** | 复测确认有追问 |
| M3 跳过 | PASS | |
| M4 答非所问拉回 | **PASS** | 复测确认拉回 |
| M5 注入 | PASS | |
| M6 幂等 | PASS | |
| M7 再开 | PASS | |
| M8 报告只读 | PASS | |
| X1 / X2 | PASS | |

---

## 关键回归点

### R1（原 P0/P1-2）

确认后档案：

- P99 → `订单查询 P99 从 820ms 降到 110ms`
- 日均 3000 万、**管理 5 人团队** 仍在  

证据：`prod-r3b/phase-r.json` → `R1.after`。

### JD parse（原 P0-1）

```text
POST /api/v1/jobs/profiles/{id}/parse → 200
company=示例科技 title=后端工程师 id=job_r0i2kyc5r3mvzd3x
```

M1 开场：`你好，我是示例科技后端工程师的面试官…`；报告 `ready`。  
场次：`mock_87wyseal9agi9nl0` / agent `agsn_kvrkqf0dgwo11228`。

### M2 / M4 说明

首轮脚本只扫当次 SSE `tokens_text`，弱答后模型已在追问（含「哪一个 / 哪些因素」）却被判 FAIL。复测改为结合历史 assistant 文案后 **PASS**。人读项（报告是否低分 / 是否点名未答到点）仍建议抽看，不挡本轮门禁。

---

## 账号清单（请清理）

| 项 | 值 |
|---|---|
| email | `cursor-r3b-1795047652-a@sspacee.com` |
| user | `usr_pv1pfysz1mgmcfiz` |
| profile | `prof_9f4zfqu6qra21kmq` |
| job（正式 parse） | `job_r0i2kyc5r3mvzd3x` |
| resume-coach | `agsn_ogdrzhvq063s0p1z` |
| M1 mock | `mock_87wyseal9agi9nl0` |

密码：`/tmp/jc-validation/2026-11-19-r3/prod-r3b/accounts.secret`。

---

## 产物

| 路径 | 内容 |
|---|---|
| `…/prod-r3b/phase-r.json` | R1–R6 |
| `…/prod-r3b/phase-mx.json` | M/X（含 M2/M4 复测） |
| `…/prod-r3b/jd-probe.json` | JD parse 200 证据 |
| `…/prod-r3b/setup.json` | 账号与对象 id |
