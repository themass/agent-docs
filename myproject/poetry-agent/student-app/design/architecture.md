# 学生端整体架构与技术选型

- 日期:2026-11-06(任务 B)
- 依据:产品基线 `docs/specs/2026-11-05-product-goals-and-strategy.md`,并行约定 `docs/specs/2026-11-06-parallel-work-contract.md`。冲突时以基线为准。
- 范围:学生端的前端、后端(Java `vvv-student`)、agent 三部分的边界、数据流和选型。页面、接口、agent 细节见同目录其他文件。

## 1. 一张图

```
 ┌──────────────── 学生设备(浏览器 / 将来 Capacitor 壳)────────────────┐
 │ frontend (零依赖 ES 模块)                                            │
 │   views: 我的时空 · 时间轴(找诗/全貌) · 诗词页 · 五步课 · 家长入口     │
 │   state: router · store · lesson controller                          │
 │   runtime/scene-runtime  (五步状态机 · 降级 · 离线预取,唯一实现)     │
 │   runtime/platform-web   (音频 · 存储 · 加载,壳替换这一层)           │
 │   本地存储:学习进度 · 复述原文(只在本机) · 已下载 bundle              │
 └───────┬───────────────────────────────┬─────────────────────────────┘
         │ /api/student/v1  (Bearer)     │ /agent/v1/turn  (Bearer)
         ▼                               ▼
 ┌───────────────────────────┐   ┌────────────────────────────────────┐
 │ vvv-student (Java 模块)    │   │ student-app/agent (Python/FastAPI) │
 │  · 只读已发布内容分发       │   │  · 五步状态机(程序推进)            │
 │  · bundle / 素材登记分发    │◄──│  · 角色: 向导 诗人 讲解员           │
 │  · 匿名设备 + 学习记录      │   │  · 后台: 审校(规则) 评估(只指缺口)  │
 │  · 会话进度 / 缺口汇总      │   │  · LLM 只做措辞与有限追问           │
 └──────┬───────────────┬────┘   │  · 降级链 → 预写脚本 → 文字         │
        │ 注入 bean      │ SQL    └───────────────┬────────────────────┘
        ▼               ▼                        │ 可选: OpenAI 兼容网关
 vvv-poetry(只读)   MySQL 5.6 (student_* 表)      ▼  (无网关/无密钥 → 脚本模式)
 PoetryCatalog      poetry_script/asset(只读 PUBLISHED)
```

## 2. 边界与单向依赖

| 规则 | 含义 | 违反的后果 |
|---|---|---|
| 事实权威在 Java | 学生端看到的每一个事实,都经 Java 的发布闸门。agent 不连 MySQL。 | 草稿内容流到学生手里 |
| 学生端不读 DRAFT,不调用内容生产 agent | `vvv-student` 的所有查询带 `status='PUBLISHED'`;agent 只收到 Java 返回的已发布 bundle | 学生端变成内容生产端的旁路 |
| 内容只经 bundle | 前端的文案、台词、背景全部来自 bundle 和诗文包,源码里没有任何诗词内容 | 换壳或换内容要改代码 |
| 流程由程序推进 | 模型不决定下一步,最多 `suggest_step`,是否跳转由前端状态机决定 | 模型跳步、自作主张 |
| 文字永远是降级终点 | 图、音、动画、角色、agent、网络任一失效,五步仍能用文字走完 | 断网即白屏 |
| 学生数据最小化 | 只有匿名设备 id 和结构化事件;复述原话不上传 | 未成年人合规风险 |

依赖方向:`frontend → vvv-student → vvv-poetry`,`frontend → agent → vvv-student`。反向没有。`vvv-poetry` 不知道学生端存在;`vvv-link/common/roles` 不改。

## 3. 数据流(一次《春望》)

1. **进入**:前端启动 → `GET /student/v1/config` 取 CDN 基址、特性开关、最低支持的 schema 主版本。无设备凭证则 `POST /devices` 取得匿名设备 id 和设备密钥(只此一次返回,存本机)。
2. **找诗**:时间轴 `GET /student/v1/timeline?from&to` → Java 调 `PoetryCatalog.timeline`(只含已发布)+ 覆盖声明。
3. **进诗**:`GET /student/v1/works/{workId}/lesson` 返回「课程入口」:当前已发布脚本的 `bundle_hash` 与 `coverage_notice`;前端按 hash 取 `GET /student/v1/bundles/{hash}`(不可变,`Cache-Control: immutable`)和 `GET /student/v1/works/{workId}/pack`(诗文包:原文、拼音、注释、背景、背景↔诗句关联)。两者都进本地缓存。
4. **五步**:前端 `SceneMachine` 驱动界面。过程中把结构化事件(进入某步、停留秒数、跳过、点开某层、点某句)批量 `POST /devices/me/events`;断网则存本地队列,恢复后补发。
5. **追问与补讲**:前端 `POST /agent/v1/turn`(动作封闭枚举 + 当前步 + bundle_hash)。agent 用 `bundle_hash` 向 Java 取同一份 bundle(不信任客户端传来的内容),生成并审校后返回;任一环失败返回脚本台词,响应里 `source` 标明是 `script` 还是 `llm`。
6. **复述**:学生在「诵」步用自己的话讲;原文只在本机显示,发给 agent 评估时用于一次性计算,不落库不写日志;评估结果(哪几个要点缺)通过 `POST /devices/me/gaps` 记录为要点 id 列表。
7. **返回**:回到诗词页,多一个「已进入过」标记;时间轴上这首诗有标记。

## 4. 技术选型

### 4.1 前端:保留零依赖 ES 模块,不升级到 Vite+React / Next

| 维度 | 零依赖 ES 模块(选) | Vite + React | Next.js |
|---|---|---|---|
| Capacitor 壳 | 静态文件直接装进 `webDir`,无构建依赖 | 需要构建;产物同样是静态文件 | 要用静态导出,SSR 能力用不上,路由约束多 |
| 包体(弱网) | 自有代码约 60KB 量级,无框架运行时 | React+ReactDOM 约 45KB gzip 起,加路由/状态库更多 | 更大 |
| 离线 | Service Worker 缓存 + IndexedDB;壳里用原生存储;无 hydration | 同左 | SSR 与离线冲突,收益只在分享页 |
| 供应链与审核 | 无 npm 运行时依赖;内核已验证「只用可擦除 TS 语法」可直接在 WebView 跑 | 数百个传递依赖,每次升级要审 | 同左且更重 |
| 开发效率 | 手写路由/状态/视图;约 7 个视图,可控 | 组件与生态更好 | 同左 |
| 类型安全 | JSDoc 引用内核的 TS 类型,可用 `tsc --noEmit --checkJs` | 原生 TS | 原生 TS |
| 动画/角色 | 本阶段是 SVG/PNG 分层 + CSS,够用 | 同左 | 同左 |

**取舍**:现在的复杂度主要在「内容与降级」而不是「UI 状态管理」;现有内核已经是框架无关、无需打包即可在 WebView 运行,再加一层框架只会增加包体、依赖和审核面。代价是视图层要自己约束(统一 `view(ctx) → {el, destroy}` 约定,所有文本用 `textContent`,不拼 HTML)。

**升级触发条件**(出现任一就在 `decisions.md` 里重新决策,而不是边写边换):
1. 引入 Live2D / pixi / Three.js 等需要打包与代码拆分的依赖(`design/` 需要重评);
2. 视图数量超过约 15 个,或出现跨视图的复杂派生状态;
3. 需要对外分享页的 SSR(那是单独的轻量页面,不是整个应用换框架)。

升级时保持不变的部分:`runtime/` 内核、`/api/student/v1` 契约、bundle 契约、`lesson controller`、`agent client`。只有 `views/` 与 `ui/` 会被替换。

### 4.2 后端:新模块 `vvv-student`,而不是塞进 `vvv-poetry`

- 隔离:学生数据(`student_*` 表)与内容底座(`poetry_*`)隐私等级不同,代码、权限、将来的库都应分开(架构文档 §2.6 已定)。
- 依赖 `vvv-poetry` 的 `PoetryCatalog`(已发布读取的唯一实现),不复制发布闸门的 SQL。已发布「注释」没有现成读取接口,见 `docs/handoff/B-needs-from-java.md`;在此之前 `vvv-student` 自带一个**更严**的只读查询,并标注待删除。
- 与宿主风格一致:自动配置类 + `student.enabled=true` 才启用、MyBatis 注解 Mapper、record 模型、`Response(errno,data,error)` 外壳、进程内限流过滤器。不引入新依赖。

### 4.3 agent:Python 3.12 + FastAPI,放进 uv workspace

- 与平台现有 Python 栈一致(`agent-bff` 同款依赖:fastapi、httpx、pydantic、uvicorn)。
- 不引入 LangChain/DeerFlow:这里的流程是程序状态机,模型调用只有「改写措辞」一种形态,自写不到 200 行的客户端更可控。DeerFlow 属于内容生产侧。
- 模型网关:OpenAI 兼容,经 `POETRY_LLM_API_BASE/KEY/MODEL_PRIMARY/MODEL_FALLBACK` 四个变量;全部缺失或调用失败时降级为预写脚本,服务照常启动。

### 4.4 移动端就绪(对应 `frontend-and-mobile-strategy.md` 的 9 条纪律)

| 纪律 | 本实现 |
|---|---|
| 1 Bearer,无 Cookie | 所有请求 `credentials: 'omit'`,设备密钥放 `Authorization: Bearer`;存储经 `Storage` 接口,壳里换 Keychain/Keystore |
| 2 内容只经 bundle | 前端无任何诗词文案;演示数据走与线上相同的 `/api/student/v1`(由开发服务器返回夹具) |
| 3 平台能力注入 | 前端只通过 `platform` 对象访问存储、音频、加载、网络状态、减少动效;视图里没有直接的 `localStorage`/`Audio` |
| 4 离线优先 | 诗文包与 bundle 内容寻址缓存;事件本地队列;Service Worker 只在 Web 注册,壳里不注册 |
| 5 音频一等公民 | 音频走 `platform.audio`,字幕文本始终存在;本阶段无真实音频,走 `a-recite-demo-subtitle` 降级 |
| 6 录音只在本地 | 本阶段录音未接通(Web 版刻意不接),UI 在「诵」提供文字复述;复述原文不上传 |
| 7 性能预算 | 复用内核 `resolve()` 的设备上限;弱网/低内存/减少动效自动降到 L1;WebGL 一个上下文(本阶段 0 个) |
| 8 只热更数据 | bundle 与诗文包是数据;没有下发可执行代码 |
| 9 无障碍 | 触控目标 ≥44px、`prefers-reduced-motion`、语义标签、文本层始终存在 |

CORS 白名单(`student.cors.allowedOrigins`)预留 `capacitor://localhost`、`http://localhost`、`https://appid.localhost`。

## 5. 目录

```
student-app/
  frontend/    学生端页面(src/ 视图·状态·api·本地存储·样式;public/ 静态;legacy/ 旧内部预览页)
  agent/       student_agent 包 + data/(课程旁路文件、评测集)+ tests/
  runtime/     contracts(含诗文包/时间轴/设备事件契约与演示夹具)· scene-runtime · platform-web
  design/      本目录
  production/  任务 C(只读)
testserverV/vvv-student/   Java 新模块;SQL 在 src/main/resources/db/student/
```

## 6. 启动

```bash
make student-dev      # 前端(含 /api/student/v1 夹具)+ agent(脚本或 LLM 模式),一键;Ctrl-C 全部退出
make student-verify   # 构建与静态检查(不跑测试套件)
```

`student-dev` 默认**不连数据库、不连 Java**:前端开发服务器按 `runtime/contracts/demo/` 的夹具提供 `/api/student/v1/*`,响应头 `X-Student-Source: demo-fixture`,页面顶部显示「演示数据,未发布」横幅。设置 `STUDENT_API_BASE=http://host:port` 可把 `/api/student/v1` 代理到真实 Java。agent 若检测到 `.env` 中的网关配置完整则用 LLM 措辞,否则(或设置 `STUDENT_AGENT_MODE=script`)只走脚本。
