# Poetry Studio(内容编辑工作台)

React 19 + Vite 8 + TypeScript 7。编辑侧 Web 工作台,**只通过 `agent-bff` 的 BFF API(契约 `docs/handoff/A-contract.md` §7)取数与写入**。

- 不直连 MySQL、Java、MCP、worker、DeerFlow。
- 前端不持有任何服务端令牌(`POETRY_*_TOKEN` 一律不出现)。唯一的凭据是用户登录后得到的会话令牌,只放在 `sessionStorage`。
- **没有任何“发布”按钮**。Agent 与 Studio 只产生并审核 DRAFT;发布权在人和 Java 发布闸门。
- 不引入 UI 库与路由库(自写极小 hash 路由)。

## 启动

```bash
cd content-agent/frontend
npm install
npm run dev          # http://localhost:5190
npm run build        # tsc 类型检查 + vite 生产构建 -> dist/
npm run typecheck    # 仅类型检查
npm test             # vitest(jsdom + testing-library);开发期间不运行,统一测试阶段再跑
```

需要 BFF 在运行(默认 `http://localhost:8100`)。本地离线演示可用 `scripts/content-agent/dev-offline.sh`(起 Mock、控制桥、worker、BFF,可选 Studio)。BFF 的 CORS 白名单默认含 `http://localhost:5190`。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `VITE_AGENT_BFF_URL` | `http://localhost:8100` | BFF 地址。构建期注入,会进入前端包,**不要放密钥** |

不读取也不需要 `.env` 里的任何密钥。

## 登录与账号

启动时先请求 `GET /api/poetry/v1/agent/auth/me`,按 BFF 的 `auth_mode` 分三种情况:

| `/auth/me` 结果 | 行为 |
|---|---|
| 200,`auth_mode="off"` | **离线演示模式**。页首显示醒目横幅(文案取自响应的 `warning`);保留“占位身份选择器”(id + 角色,存 `localStorage`);请求体带 `actor`。服务端无法证明你是谁 |
| 200,`auth_mode="required"` | 已登录。顶部显示姓名与中文角色名,有“退出登录” |
| 401 `AUTH_REQUIRED` | 显示登录页 |

要点:

- 登录:`POST /auth/login`,体 `{user_id, password}`。成功后令牌与到期时间写入 **`sessionStorage`**(关闭标签页即失效),**绝不写 `localStorage`**,不进日志与界面。
- 之后所有请求带 `Authorization: Bearer <token>`。任何 401 `AUTH_REQUIRED` 都会清令牌并回登录页,**当前 hash 路由保留**,登录后原地返回。
- 到期前不做静默续期;到期即回登录页并提示“登录已过期”。
- `LOGIN_FAILED` 一律提示“账号或密码不正确”(不区分原因);`LOGIN_LOCKED`(429)读 `Retry-After` 秒数并倒计时;`AUTH_NOT_CONFIGURED`(503)提示联系管理员;`AUTH_DISABLED`(409)说明是离线演示并可重新检查。登录失败后清空密码框,不回显。
- `required` 模式下请求体**不带** `actor`(服务端以令牌为准);所有“能不能评审/应用/核验”的前端预检改用 `/auth/me` 或登录响应里的角色。`off` 模式才带 `actor`。出处核查页的署名在 `required` 模式下取自登录身份且只读。
- SSE:`EventSource` 不能带请求头,所以每次(重)连接前先 `POST /auth/events-ticket/{run_id}`(带 Bearer)取一次性票据,再连 `GET /runs/{run_id}/events?ticket=…`。每次重连都重新取票;`off` 模式返回空票据,此时不加 `ticket` 参数。票据不写日志、不进界面。

**账号怎么来**:账号由运维用命令行创建,**Studio 不提供注册**:

```bash
python -m agent_bff.users add --file <账号文件> --id <id> --role <角色>   # 密码交互输入
```

账号文件放在**仓库之外**。角色:`CONTENT_EDITOR` 内容编辑 / `HISTORICAL_REVIEWER` 史料审核人 / `PLATFORM_ADMIN` 平台管理员 / `RELEASE_MANAGER` 发布管理。

## 页面与 BFF 契约对应

顶部导航 7 个入口(hash 路由 `#/…`):

| 页面 | 路由 | 使用的 BFF 端点(前缀 `/api/poetry/v1/agent`) |
|---|---|---|
| ① 工作台 | `#/workbench` | `GET /tasks`(筛选:作品/状态/类型,分页)、`POST /tasks`、`GET /works` |
| ② 任务与运行 / 任务详情 | `#/tasks`、`#/tasks/{task_id}?run=` | `GET /tasks/{id}`、`GET /tasks/{id}/runs`、`POST /tasks/{id}/run`(`{runtime:"STUB"}` 为确定性重试)、`POST /runs/{id}/cancel`、`GET /runs/{id}`、`GET /runs/{id}/budget`、`GET /runs/{id}/events`(SSE)、`POST /auth/events-ticket/{run_id}`、`GET /proposals?run_id=` |
| ③ 提案审核 | `#/proposals`、`#/proposals/{id}` | `GET /proposals`、`GET /proposals/{id}`、`GET /proposals/{id}/diff`、`POST /proposals/{id}/review`、`POST /proposals/{id}/apply` |
| ④ 缺口与覆盖 | `#/coverage?work=` | `GET /works/{id}/coverage`、`GET /works/{id}/gap-report` |
| ⑤ 出处核查 | `#/sources?source=` | `GET /sources`、`PUT /sources/citations/{claim_id}/{source_id}/locator`、`POST /sources/{id}/verification`、`GET /health/ready` |
| ⑥ 作品内容 | `#/content?work=` | `GET /works/{id}/overview` |
| ⑦ 发布前检查 | `#/precheck?work=` | `GET /works/{id}/precheck` |

另:外壳页脚读 `GET /health/ready`(BFF 可达、worker 与 reviewer 通道是否配置);`GET /auth/me`、`POST /auth/login`。Studio **不调用** `POST /runs/{id}/proposals`(提案只由 worker 写入)。

每个页面都有 loading / empty / error(带重试)三态;写操作失败会就地显示服务端错误码与 details。错误体统一 `{error:{code,message,details}}`。

### 提案审核的规则

- 可执行项(`executable=true`)必须**逐项**批准或驳回,才能**整体批准**;整体驳回不要求逐项。服务端 `ITEM_DECISIONS_REQUIRED` 再校验一次。
- 只有 `CONTENT_EDITOR` / `HISTORICAL_REVIEWER` 能评审;`CONTENT_EDITOR` / `HISTORICAL_REVIEWER` / `RELEASE_MANAGER` 能应用。角色不够时按钮与单选**禁用并写明原因**(服务端为准)。
- 应用按钮的文案是“写入草稿(不是发布)”。没有被批准的可执行项时显示 `NOTHING_TO_APPLY` 提示,提案只作为编辑记录留存。

### 视觉契约(DESIGN.md §4)

史实=靛青下划线;解释=青绿左线;演绎=朱砂底+“演绎”前缀;未考=灰虚线,文案“不可考/待核”。PUBLISHED(实线粗框)与 DRAFT(虚线框+斜纹)永久区分,且同时有文字和字形。状态不只靠颜色。动效只用 `--ease-ink`,`prefers-reduced-motion` 下全部关闭。样式在 `src/styles/tokens.css`(复制自 `docs/design/tokens.css`,不改)之上的 `src/styles/studio.css`。

## 键盘操作

- 页首“跳到主要内容”链接;landmark:banner / navigation“主导航” / main / contentinfo;换页后焦点落到页面 `h1`,并更新 `document.title`。
- 列表项都是真实链接(任务、提案、来源):`Tab` 聚焦,`Enter` 进入。
- 对话框(取消运行、评审、应用、核验/驳回、切换占位身份):打开后焦点进入,`Tab`/`Shift+Tab` 在内部循环,`Esc` 关闭并还原焦点到触发按钮;提交中不可关闭。
- 被规则挡住的按钮用 `aria-disabled`,**仍可聚焦**,原因文字通过 `aria-describedby` 关联,读屏用户能读到为什么不能点。
- 表单错误与字段用 `aria-describedby` / `aria-invalid` 关联,提交失败时焦点移到第一个错误字段。
- `aria-live`:全局播报区(状态变化、写入结果),流状态行(连接/重连/回退轮询),评审进度。
- 登录页:`Tab` 在账号与密码间切换,`Enter` 提交。

## 目录

```
src/
  api/        types.ts(契约类型) client.ts(请求/错误/鉴权头) events.ts(SSE 重连+回退轮询) session.ts(令牌)
  lib/        actor.tsx(AuthProvider) router.ts review-rules.ts permissions.ts validation.ts trust.ts event-view.ts …
  components/ 外壳、对话框、登录页、通用 UI、错误边界、播报
  pages/      七个页面及其子组件
  styles/     tokens.css(不改) studio.css
  test/       setup.ts helpers.tsx(fetch 与假 EventSource)
```

## 已知缺口

- **测试只写未跑**(开发期约定)。`npm run build` 与 `tsc --noEmit` 已通过;`vitest` 套件尚未执行,首次运行可能有需要微调的断言。
- 未在真实浏览器与真实 BFF/Mock 上联调,没有做屏幕阅读器实测,也没有截图验收。
- SSE 的 `Last-Event-ID` 请求头浏览器 `EventSource` 无法自带:原生自动重连会带,但带票据的连接一律改为手动重建并用 `?after_event_id=` 续传。事件按 `event_id` 去重,即使服务端重放也不会重复显示。
- 回退为轮询时只刷新 run 状态与预算,**看不到事件明细**(BFF 没有事件的 JSON 列表端点)。
- 署名预检沿用后端规则(子串匹配 `agent|bot|deerflow|system|mcp|llm|ai`),含 `ai` 的真实姓名(如 Kai)也会被挡,界面报错时已说明。
- 发布前检查里 R1–R12 的中文释义是编辑辅助,规则名与判定以 BFF 返回为准。
- 覆盖看板的“可核查 claim”含义是“至少有一条 locator 为真实值的 claim 数”,与来源是否已核验无关。
- 令牌失效或到期时整棵页面树会被登录页替换,未提交的表单草稿会丢失(hash 路由保留)。
- 离线演示模式的占位身份没有任何真实性保证,仅用于本地演示。
