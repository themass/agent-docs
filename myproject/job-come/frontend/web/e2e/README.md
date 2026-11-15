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
- **跨用户隔离用例需要第二个账号**：`JC_E2E_EMAIL_B`（默认
  `e2e-probe-b-20261115@example.com`）和 `JC_E2E_PASSWORD_B`。缺 B 密码时
  `m-cross-user.spec.ts` 整组 skip，不会假通过。
- 失败会留下截图、录屏和 trace：`test-results/<用例名>/`，用 `npx playwright show-trace` 打开。

## 覆盖的用例

| 文件 | 用例 | 为什么是它 |
|---|---|---|
| `a-auth.spec.ts` | A-02 / A-02b / A-03 / A-08 | 登录表单可用；错误密码给出中文可读文案，不泄漏堆栈；未登录访问业务页要跳登录 |
| `b-profile.spec.ts` | B-04 / B-07 / B-08 / B-08b | 短文本被拒而非编造；新档案是草稿态；**空档案不能被确认** |
| `b-upload.spec.ts` | B-01 / B-02 / B-03 / B-04b | 上传 PDF 与 DOCX 都能建档案并产生解析来源；不支持的类型不返回 5xx；足量文本能解析 |
| `d-export.spec.ts` | D-01 ×3 | 三种格式都能生成并**真的下载到有效文件**（校验 magic 头） |
| `ef-mock.spec.ts` | E-01 / E-04 / F-01 / F-02 | JD 能解析成结构；匹配不阻断；目标岗模式未绑岗位必须被拒 |
| `f-mock-flow.spec.ts` | F-01 / F-03 / F-04 / F-06 / F-07 / F-08 | **开一场→看进度→结束→报告存在**；结束后状态必须离开 active；**答案记在被问的那道题上** |
| `g-interview.spec.ts` | G-01 / G-02 / I-01 / I-02 | 面试记录**写进去能读回来**；会员状态可读；无效兑换码给出可读文案 |
| `h-agent.spec.ts` | H-06 / H-01 / H-02 | 等待期只有一个「思考中」；纯对话能拿到回复；**带工具的改档能生成确认卡片** |
| `j-feedback.spec.ts` | J-01 / J-02 / J-03 | 通知可读；反馈提交后**列表能读回同一条** |
| `k-admin.spec.ts` | K-02 / K-06 / K-07 / K-12 / K-13 / K-14 | 面板有真实数字；核心方法耗时不是 0.00003s；跨进程标识为 true；inflight 回零；列表按时间倒序且不含 payload |
| `k-admin-pages.spec.ts` | K-17 ~ K-21 / K-19 | 五个后台页各自渲染**且数据接口成功**；trace 导出是合法 NDJSON |
| `c-resume.spec.ts` | C-01 / C-01b / C-02 / C-05 / C-07 / C-10 | 两档都能生成；**不同档位产出必须不同**（否则档位是装饰）；覆盖度/岗位标准/结构都在响应里 |
| `c-rail.spec.ts` | C-08 / C-08b | 收起后是 ~44px 竖条且能展开回去；**运行中收起不中断回合**，展开后仍拿到回复 |
| `c-options.spec.ts` | C-03 / C-03b / C-04 | 指标句式只有空位、**永不预填数值**；角度最多 2 个且写入生效；证据答案能回显 |
| `c-focus.spec.ts` | C-09 / C-09b | 结构化视图有 `data-path` 锚点；悬停证据缺口时文档会高亮或滚动 |
| `l-perf.spec.ts` | L-02 / L-05 / L-06 | 列表 < 3s；面板 < 3s；首屏 < 8s；连续请求不累积变慢 |
| `m-isolation.spec.ts` | M-05 / M-06 / M-08 | 未登录被拒；监控端点不含用户数据；错误响应不泄漏堆栈或内部路径 |
| `m-cross-user.spec.ts` | M-01 / M-01b / M-02 / M-04 | **用 B 账号的独立 cookie 去读 A 的档案/会话/简历版本**，必须被拒或拿到空列表 |

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

详细清单见 [`../../docs/operations/QA-FULL-VERIFICATION.md`](../../docs/operations/QA-FULL-VERIFICATION.md)。
当前 32 个用例，尚未覆盖的主要是：

| 缺口 | 原因 |
|---|---|
| C-03b / C-09b 联动验证 | 测试档案当前没有证据缺口，用例会 skip 并注明原因 |
| B-03 图片 OCR | 需要一个真实图片样本；PDF/DOCX 已覆盖 |
| F-05 跳过/换题成功路径 | 只在"不存在的题"上验证了不返回 5xx；成功路径需要一场进行中的面试 |

## 跨用户隔离用例怎么才算有效

`m-cross-user.spec.ts` 用 `playwright.request.newContext()` 建一个**独立 cookie jar**，
以 B 的身份登录，再去读 A 的资源。

如果复用 page 的 cookie，断言会全部"通过"但毫无意义——那用的是 A 自己的会话，
拒绝和空结果都会因为错误的原因成立。这条写在这里，是因为它是最容易被写假的一类测试：
200 也可能是对的（空列表），所以断言分两支——要么被拒（4xx），
要么 200 但载荷确实是空的。

优先覆盖**踩过的坑**，而不是铺满一个看起来完整的矩阵。
