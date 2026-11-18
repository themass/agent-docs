# QA 用户全旅程验证结果（liguoqing19861028@163.com）

- **时间**：2026-11-15（Asia/Shanghai）
- **站点**：https://jc.sspacee.com
- **账号**：`liguoqing19861028@163.com`（`usr_ebidh236m6tgbrvn` / UI 显示 Themass@5296）
- **证据**：`/tmp/jc-validation/2026-11-15-journey/`
- **结论**：**模拟面试可走通；简历侧边栏改档失败（工具超时未落库）；导出后端成功但浏览器未收到下载；指标 `in_flight` 全程粘住。**

## 1. 跑了什么

| 阶段 | 档案 / 对象 | 结果 |
|---|---|---|
| 登录 | — | OK |
| 优化预览 | `prof_gpbkp67hao2yenvj`（新档案，有快手等经历） | tracks `zh-CN=ready`（`rdft_u8izsyoddvhz7m99`） |
| 导出前质检 | 同上 | 模型核查曾 **unavailable / 超时**，UI 写「这次没有完成检查」但**不阻断导出**（设计如此） |
| 侧边栏 agent 改简历 | `agsn_n48fh8flue5ruru0` / 关键词 `JOURNEY-EDIT-…` | **失败落库**：agent 明确说「档案修改工具连续超时…因此这版没有保存」；工具轨迹里 `jc_profile_patch` 红叉 |
| 导出 PDF | `expj_zpt9jxmtofi5cl86` | **库内 `status=done`**；自动化未收到 browser `download` 事件（UI/下载触发问题或链到新标签） |
| 模拟面试 | 切到 `prof_guvztbh80h5wg3p5` + `job_3dz3pa1btvwrieym` | **`mock_vccadr3kzc76e6b7` `level=mid` `status=completed`** |

新档案 `prof_gpbkp67hao2yenvj` **没有岗位**；旧档案才有「示例桁架科技 · 后端研发工程师」。若不切档案，模拟面试会卡在「先选择岗位」。

## 2. 和你「侧边栏一直失败」的对应关系

这轮**复现了你的感觉**，不是脚本误报：

1. Agent **会回话**，甚至给出改写稿。
2. 但 **`jc_profile_patch` 连续超时** → 档案未改 → 用户体感就是「改简历失败」。
3. 同时导出质检在抢模型（`export_review … stage=model status=unavailable`），和侧边栏改档叠在一起，更容易拖垮工具调用。
4. 指标上 `agent_turns_in_flight` 全程 **3.0～4.0 不回零**（基线已粘），说明有回合泄漏，会让「运行中」状态更脏。

Round3 里「API SSE 短句成功」仍然成立；**带工具的改档路径才是坏的**。

## 3. 持续监控（每 ~20s 采样）

采样文件：`metrics/series.jsonl`（约 44 点）。

| 指标 | 开始 | 结束 | 备注 |
|---|---|---|---|
| `llm_calls` | 17 | 30（瞬时到 31） | Δ≈+13，含 coach / writer / flash / reviewer |
| `agent_turns` | 6 | 11 | resume-coach success +1；coach-mock success +4 |
| `agent_turns{error}` | 1 | 1 | 旧错误未清 |
| `agent_turns_in_flight` | 3.0 | 3.0（峰值 4.0） | **整段旅程从未回到 0** |
| `llm_calls{error}` | 0 | 0 | 网关计数无 error 标签增长 |

终态角色拆分（snapshot）：

- `resume-coach`：success 6 / error 1  
- `coach-mock`：success 4  

## 4. 截图要点

| 文件 | 看见什么 |
|---|---|
| `screenshots/v2-04-sidebar-done.png` | 仍在思考；`jc_profile_patch` 失败标记 |
| `screenshots/v2-06-export-done.png` | Agent 已承认「修改工具连续超时…没有保存」；页面被带回核对步 |
| `screenshots/v2-10-ended.png` | 面试对话含 JOURNEY-MOCK；UI 仍闪「进行中/面试官正在准备」，但库已 completed |
| `screenshots/v2-08-before-start.png` 等 | 岗位选中、中级、开始本轮 |

## 5. 失败清单（本轮未改代码）

1. **P0 — `jc_profile_patch` 超时 / 侧边栏改档不落库**（用户可感知的「一直失败」）。
2. **P1 — `agent_turns_in_flight` 粘住 ≥3**（监控失真，和 Round3 一致）。
3. **P2 — 导出质检 model stage 常 unavailable/超时**（不挡下载，但体验差）。
4. **P2 — 浏览器自动化未拿到 PDF download**（库已 `done`；需查 UI 是链还是 blob）。
5. **产品陷阱 — 新上传档案无岗位时模拟面试不可开**（须切回有 JD 的档案或先存岗位）。

## 6. Go / No-Go（针对本旅程）

- **模拟面试路径**：可继续用（本场 mid completed）。  
- **简历「聊着改 → 保存」**：当前 **不能当可用能力**。  
- **导出**：后端能出 PDF job；前端下载体验需再盯一眼。  
- **监控面板 / inflight**：仍不可信（Round3 结论不变）。
