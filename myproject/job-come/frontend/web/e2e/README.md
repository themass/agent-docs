# 浏览器端到端验证

对着**一个正在运行的环境**跑真实浏览器：本地栈，或生产站。这些用例登录真实账号，
所以不要指到数据要紧的库上做破坏性操作。

## 跑法

```bash
cd frontend/web
npx playwright install chromium        # 首次
JC_E2E_PASSWORD='<测试账号密码>' \
JC_BASE_URL=https://jc.sspacee.com \
npx playwright test --reporter=list
```

- `JC_E2E_EMAIL` 默认 `metrics-probe-20261114@example.com`。
- 没有 `JC_E2E_PASSWORD` 时，需要登录的用例会 skip 并注明原因，不会假通过。
- 失败会留下截图、录屏和 trace：`test-results/<用例名>/`，用 `npx playwright show-trace` 打开。

## 覆盖的用例

| 文件 | 用例 | 为什么是它 |
|---|---|---|
| `a-auth.spec.ts` | A-02 / A-02b / A-03 / A-08 | 登录表单可用；错误密码给出中文可读文案，不泄漏堆栈；未登录访问业务页要跳登录 |
| `h-agent.spec.ts` | H-06 / H-01 / H-02 | 等待期只有一个「思考中」；纯对话能拿到回复；**带工具的改档能生成确认卡片** |
| `k-admin.spec.ts` | K-02 / K-06 / K-07 / K-12 / K-13 / K-14 | 面板有真实数字；核心方法耗时不是 0.00003s；跨进程标识为 true；inflight 回零；列表按时间倒序且不含 payload |
| `d-export.spec.ts` | D-01 ×3 | 三种格式都能生成并**真的下载到有效文件**（校验 magic 头） |

## 这些用例针对的是真实缺陷

不是"页面能打开"，而是每一处都对应一次线上事故：

- **H-02**：`jc_profile_patch` 曾因会话行锁（`FOR UPDATE` 阻塞外键的 `FOR KEY SHARE`）
  每次都 120 秒超时，确认卡片从不出现。现在断言卡片必须出现、且不出现"超时"字样。
- **H-06**：一个回合曾显示两个「舟卡思考中」。断言是**在整个等待过程中反复采样**，
  因为重复只在某一个瞬间可见，等固定时间后再断言会漏掉。
- **K-06**：`stream_message` 曾被记成 0.00003 秒（async generator 只计了构造）。
  断言这个数字必须大于 0.5 秒。
- **K-14**：列表曾把 1.35MB 的 payload 列一起取回给一个不显示它们的表格。
  断言响应里**没有**那三个字段。
- **D-01**：曾误判为"浏览器收不到下载"——实际是页面渲染链接让用户点击，
  本就不会触发 download 事件。断言改成**文件真的能取到且文件头有效**。

## 还没覆盖

A/B/C/E/F/G/I/J/L/M 各组见
[`../../docs/operations/QA-FULL-VERIFICATION.md`](../../docs/operations/QA-FULL-VERIFICATION.md)。
当前只把那几组里**发生过真实缺陷**的部分写成了自动化用例——优先覆盖踩过的坑，
而不是铺满一个看起来完整的矩阵。
