import { type Skill } from '@naviforge/skill-runtime'

/** 内置 Instruction 技能（MV3 不能加载任意远程 JS）。 */
export const BUNDLED_SKILLS: Skill[] = [
  {
    manifest: {
      id: 'catalog-crawl-sop',
      version: '0.2.0',
      description:
        '用途：站点目录标准 SOP（分类→分页列表→详情多跳→字段提取→校验）。触发：所有分类、每页、批量源地址、当前页每条详情、表格目录爬取。含：会话/cookie/验证码/限频、分页、parallel spawn、媒体/表格。非：单页介绍(page-read)、单条简述(list-then-detail)、页外竞品对比。',
      triggers: [
        '分类',
        '栏目',
        '爬取',
        '抓取',
        'catalog',
        'crawl',
        '源地址',
        '批量',
        '所有',
        '每个',
        '分页',
        '列表',
        '表格',
      ],
      permissions: {
        tools: [
          'dom_read',
          'dom_snapshot',
          'dom_extract_content',
          'dom_extract_dom',
          'dom_navigate',
          'dom_scroll',
          'dom_wait',
          'system_extract_page',
          'system_spawn_readonly_tasks',
          'fetch_text',
          'tabs_open',
          'network_read',
          'system_captcha_wait',
          'system_ask_user',
          'system_done',
          'skill_load',
        ],
      },
    },
    instructions: `# 站点目录爬取 SOP（浏览器 Agent 标准路径）

parallel-read / media-extract / pagination-list 是本 SOP 的**阶段手法**，不是独立任务类型。

## Phase 0 — 会话门控（先做）
- **登录/会话**：需要账号才能看列表或详情 → 停在登录页，system_ask_user 或请用户手动登录后 system_captcha_wait；禁止编造 cookie。
- **验证码/人机**：system_captcha_wait；不得绕过。
- **Cookie/加密/签名**：只使用浏览器已有会话；禁止 execute_js 伪造 token；播放器 inline 配置用 PAGE SIGNALS，不逆向破解。
- **限频/限流**：spawn 每批 ≤3；批次间可 dom_wait；失败项指数退避重试；禁止同一列表页高频 network_read/execute_js 空转。

## Phase 1 — 发现分类（Discover）
- 读导航/频道/tab → 各分类 URL（同源、非广告）。
- preflight catalog-crawl 会跑 CATALOG_DISCOVER；无 nav 时把**当前页**当作唯一 section。
- 记录 detailShape（列表项 URL 形状，如 vod/view/*、vod/play/*）。

## Phase 2 — 分页列表（Paginate + List）
- 每个分类：解析分页（页码、下一页、rel=next）；拉取任务要求的页数。
- 每页 extract 列表项 {title, url}，按 detailShape 过滤站外/推广链。
- **表格/表单列表**：dom_read list / 表头+行；筛选条件用 dom_type/dom_select 后重新 extract。

## Phase 3 — 详情解析（Resolve，可多跳）
列表 URL 往往不是最终字段页：
1. **一跳**：列表 → 播放/商品/文章页
2. **二跳**：详情页 → 播放页 / 下载页 / 弹层内 iframe
策略：先读当前 URL 的 PAGE SIGNALS；无目标字段再 navigate/spawn 下一跳（同 detailShape 或页面内 play 链接）。
**并行**：互不依赖详情 URL → system_spawn_readonly_tasks subtasks[] 每批 ≤3（mode:tab）；静态文档 → mode:fetch。


## Phase 4 — 媒体字段（任意格式 + 模型判断）

输出 schema（父/子 system_done 均遵守）：
\`\`\`json
{
  "title": "string",
  "listUrl": "列表或详情链接",
  "mediaUrl": "直链：m3u8 | mpd(dash) | mp4 | webm | …",
  "playPageUrl": "无直链时的播放/embed/内嵌页",
  "format": "hls|dash|mp4|webm|embed|unknown",
  "confidence": 0.0,
  "shortfall": "无直链原因：需点击播放、blob、DRM…"
}
\`\`\`

| 页面情况 | 填什么 |
|----------|--------|
| PAGE SIGNALS 有直链 | mediaUrl + format |
| 仅 iframe/内嵌播放器 | playPageUrl + shortfall |
| 需点播放后 network 才有 | 子任务 dom_click 播放 → network_read → mediaUrl |
| 多个 CDN 候选 | 结合 confidence 选主播放流并说明 |
| blob/MediaSource/DRM | 禁止逆向；shortfall + listUrl/playPageUrl |

preflight 预算内自动 multihop+PAGE SIGNALS；超出 24 条或 embed-only → spawn（见 Phase 3）。

## Phase 4b — 无限滚动
plan 标 infinite-scroll 时：dom_scroll 到底 → 重新 extract 列表 → 合并去重。

## Phase 4 — 字段提取（Extract）
| 字段类型 | 手段 |
|---------|------|
| 媒体（任意格式） | PAGE SIGNALS；hls/mp4/webm/dash；无直链 → playPageUrl + 模型判断 |
| 价格/SKU/元数据 | dom_read body、结构化 JSON |
| 表格 | 表头映射列名，行→对象数组 |
| 长正文 | dom_read body / fetch_text |

## Phase 5 — 校验（Validate）
- 去重（url 归一化）、必填字段缺失标 shortfall
- 抽样重放 1–2 条验证稳定性
- system_done：分类×页×条目 结构化输出；partial 须说明 truncatedReason

## 与 preflight 分工
- **多分类×多页**：preflight runCatalogCrawl 优先；你在其 partial 结果上补 Phase 3–5。
- **仅当前列表页+每条源地址**：preflight 用 (current) section + wantsMediaUrl；你按 Phase 2–5 补 spawn。


## 实现绑定（runtime）
- Phase 0: page-friction + PAGE_FRICTION + system_captcha_wait
- Phase 2: CATALOG_PAGE_URL_JS + CATALOG_TABLE_EXTRACT_JS
- Phase 3: resolveMediaWithHops（默认 2 跳）
- Phase 5: validateCatalogCrawlResult 去重/缺字段
- 限频: throttleCatalogNav ~450ms/导航

## 禁止
- 列表页 execute_js 挖媒体代替 Phase 3
- navigation:forbidden 时父 tab 串行点开（用 spawn）
- 未过 Phase 0 硬爬私密内容`,
  },
  {
    manifest: {
      id: 'page-friction',
      version: '0.1.0',
      description:
        '用途：任意页面的会话摩擦（登录/验证码/限频/地区/付费墙/cookie）。触发：PAGE FRICTION 阻塞、人机验证、429、登录墙。含：system_captcha_wait 真人 HITL、system_ask_user。非：自动打码、伪造 cookie、绕过加密。',
      triggers: [
        '登录',
        'login',
        '验证码',
        'captcha',
        '人机',
        '限频',
        'rate limit',
        'cookie',
        '付费',
        'paywall',
        'friction',
      ],
      permissions: {
        tools: [
          'dom_read',
          'dom_snapshot',
          'dom_click',
          'dom_wait',
          'system_ask_user',
          'system_captcha_wait',
          'system_done',
          'skill_load',
        ],
      },
    },
    instructions: `# 页面摩擦（通用 — 任意 URL）

runtime 在每次 navigate/read 后探测 PAGE FRICTION 并钉入 prompt。

## 摩擦类型 → 动作
| 类型 | 动作 |
|------|------|
| captcha / human_verify | **system_captcha_wait** — 用户浏览器手动完成（同 Skyvern/OpenHands 真人接管） |
| login / paywall | system_ask_user 请用户登录；禁止伪造 cookie/token |
| rate_limit | dom_wait ≥5s；降低 navigate 频率；可 ask_user |
| geo_block / access_denied | system_done 说明 ENV_BLOCKED |
| cookie_banner | dom_click 接受（非阻塞） |

## 与 catalog-crawl-sop
- catalog Phase 0 = 本 skill；不限于视频站。
- 加密播放器：只用 PAGE SIGNALS + 已有会话，不逆向。

## 禁止
- 自动 CAPTCHA 求解服务
- execute_js 注入凭证`,
  },
  {
    manifest: {
      id: 'document-download',
      version: '0.1.0',
      description:
        '用途：从当前页触发官方下载（单篇下载/导出/PDF）。触发：下载、保存文件、export。含：登录/VIP HITL、dom_wait download 监听 Chrome 下载。非：破解 DRM、批量爬全站、dom_read 循环。',
      triggers: [
        '下载',
        'download',
        '保存文件',
        '单篇下载',
        'export pdf',
        'save file',
      ],
      permissions: {
        tools: [
          'dom_snapshot',
          'dom_click',
          'dom_wait',
          'page_to_pdf',
          'workspace',
          'system_ask_user',
          'system_captcha_wait',
          'system_done',
          'skill_load',
        ],
      },
    },
    instructions: `# 文档下载（当前页）

## Phase 0 — 摩擦
- PAGE FRICTION 阻塞 → skill_load page-friction 或 system_ask_user / system_captcha_wait
- 登录/VIP：请用户浏览器完成一次，勿伪造 cookie

## Phase 1 — 找下载入口
1. dom_snapshot（compact）找「单篇下载」「下载」「Export」「PDF」按钮 index
2. 无按钮 → page_to_pdf 可见部分 + workspace_write 兜底

## Phase 2 — 触发并确认
1. dom_click 下载按钮
2. dom_wait { "kind": "download", "timeout_ms": 60000 }
3. system_done：文件名、是否完成、若失败说明原因

## 禁止
- dom_read body 循环读全文
- web_search / tabs_open 无关 URL
- 破解付费/DRM`,
  },
  {
    manifest: {
      id: 'auth-assisted',
      version: '0.1.0',
      description:
        '[已合并] 请 skill_load page-friction。本 id 仅兼容。',
      triggers: ['登录', 'login', 'sign in', '验证码', 'captcha', 'cookie', 'auth', '会话'],
      permissions: {
        tools: [
          'dom_read',
          'dom_snapshot',
          'dom_navigate',
          'dom_wait',
          'system_ask_user',
          'system_captcha_wait',
          'system_done',
          'skill_load',
        ],
      },
    },
    instructions: `# 登录与会话协助（catalog-crawl-sop Phase 0）

## 检测
- 密码输入框 + login/sign-in URL → 需要认证
- preflight AUTH_GATE 会标注 authBlocked

## 流程
1. dom_read 确认登录表单字段（用户名/密码/验证码）
2. **禁止** execute_js 注入 cookie 或伪造 token
3. system_ask_user：请用户在浏览器完成登录（或提供是否已有会话）
4. 验证码 → system_captcha_wait
5. 登录后 skill_load catalog-crawl-sop 从 Phase 1 继续

## 限频
- 登录重试间隔 ≥3s；失败 3 次停止并报告`,
  },
  {
    manifest: {
      id: 'parallel-read',
      version: '0.1.0',
      description:
        '[已合并] 请 skill_load catalog-crawl-sop（Phase 2–4）。本 id 仅兼容路由。',
      triggers: ['所有', '每个', '批量', '并行', '源地址', '多条', '详情页', 'parallel', 'batch', 'each url'],
      permissions: {
        tools: [
          'dom_read',
          'dom_extract_content',
          'dom_extract_dom',
          'system_extract_page',
          'system_spawn_readonly_tasks',
          'fetch_text',
          'tabs_open',
          'network_read',
          'system_done',
          'skill_load',
        ],
      },
    },
    instructions: `通用并行只读（Lead 编排 playbook）：

## 何时用本 skill
- 当前页是**列表/目录**，用户要**每条**的字段（价格、源地址、正文片段等），且字段在**详情 URL** 上。
- 父任务 navigation:forbidden：禁止父 tab 串行点开；用 spawn 后台 tab。
- 待处理 >3：多轮 spawn，每轮最多 3 条并行。

## 流程
1. **收集 URL**：dom_read list / system_extract_page / dom_extract_content → [{title, url}]，去重、过滤站外广告链。
2. **判断静态 vs 渲染**：
   - 静态文档/API/raw → subtasks mode:fetch + fetch_text urls
   - 需 JS/播放器/登录态 → mode:tab + tabs_open + dom_read + PAGE SIGNALS/network_read
3. **并行委派**：system_spawn_readonly_tasks({ subtasks:[{title,prompt,urls,mode}] })，每批 ≤3。
4. **汇总**：合并所有 children[].result → 父 Agent system_done（表格/JSON），标注 failed 项。

## subtask 模板
\`\`\`json
{
  "subtasks": [
    {
      "title": "item-1",
      "prompt": "Extract fields X,Y,Z; return JSON {title,x,y,z}.",
      "urls": ["https://example/detail/1"],
      "mode": "tab"
    }
  ]
}
\`\`\`

## 禁止
- 列表页 execute_js / network_read 空转代替 spawn
- 单条任务仍用父 dom_read（不必 spawn）
- 嵌套 spawn

## 垂直 skill 分工
- 媒体/流地址字段 → 可叠加 skill_load media-extract
- 仓库目录多文件 → skill_load repo-static-fetch`,
  },
  {
    manifest: {
      id: 'research-compare',
      version: '0.1.0',
      description:
        '用途：对比两个或多个项目/仓库/产品（含 GitHub）。触发：对比、区别、vs、两个项目、github。工具：web_search、tabs_open、dom_read、system_done。非：电商商品价格、当前页列表 topN。',
      triggers: ['对比', '区别', 'vs', '两个项目', 'github', 'gitlab', '仓库对比', 'compare'],
      permissions: {
        tools: ['web_search', 'tabs_open', 'tabs_switch', 'dom_read', 'dom_snapshot', 'system_done', 'system_ask_user', 'skill_load'],
      },
    },
    instructions: `页外对比（research）：

1. web_search 发现各项目官方页或 GitHub README URL（禁止只靠训练记忆）。
2. tabs_open 打开 2–3 个结果；在每个目标页 dom_read body 一次。
3. system_done 输出 Markdown 对照表：定位/目标用户/核心能力/技术栈/许可或活跃度/差异点。
4. 缺字段写「未找到」，不得编造。
5. 不要对无关壳页（聊天/空白）dom_snapshot 空转。`,
  },
  {
    manifest: {
      id: 'page-read',
      version: '0.2.0',
      description:
        '用途：介绍/总结当前页或当前项目（文档/README/产品页）。触发：介绍、总结、概括、本页、readme。工具：dom_read body、system_done。非：页外对比、GitHub 两项目区别、安装追问。',
      triggers: ['介绍', '总结', '概括', '是什么', 'readme', 'summarize'],
      permissions: { tools: ['dom_read_page', 'dom_snapshot', 'page_to_markdown', 'page_to_pdf', 'system_done', 'system_ask_user'] },
    },
    instructions: `读当前页并回答（READ）时：

## 观察
1. 若结构化页面证据已包含 read_page 结果，直接据此作答，禁止再 read_page。
2. 否则 dom_read_page 一次；不要用 extract_content / system_extract_page 代替。
3. 正文不足时再 dom_snapshot 补元信息（标题、规模指标等）；不要为 README 反复 dom_scroll。

## 追问
安装 / 怎么用：只回答用户的问题，禁止再套下面的五段介绍模板。
同类 / 类似项目 / 竞品：不要用本 skill；改用 web_search，再打开 2–3 个结果核实。

## system_done 模板（仅介绍/总结；按用户语言作答）

用 Markdown，缺信息写「未在正文中找到」，不得编造。

### 一句话
≤40 字：这是什么、解决什么问题。

### 适合谁
- 2–3 条 bullet，每句 ≤30 字

### 能做什么
- 3–5 条，按**使用场景**组织（不要按 README 目录顺序堆）
- 同义能力只写一次

### 技术与许可（有则写；可合并为一小段）
- 技术栈：单独短列表，不与「能做什么」混写
- 许可 / 社区：一行（如 License、stars/forks 量级）
- 代码仓库首页可在此补安装方式（Homebrew、Releases 等）

### 怎么开始
- 一行：安装命令、文档链接或官网

## 版式硬规则
- 禁止单段连续文字超过 120 字而不分段或列表
- 禁止同一事实重复两遍（如 star 数、许可写两次）
- 禁止功能点与技术名词混在同一段里关键词堆砌`,
  },
  {
    manifest: {
      id: 'form-fill',
      version: '0.1.0',
      description:
        '何时使用：网页有可见输入框/下拉/复选框且需填写并提交。用 DOM 工具定位字段、填值、提交并校验成功文案；不适用于登录绕过或验证码破解。',
      triggers: ['form', '填写', '输入', 'submit', '表单'],
      permissions: { tools: ['dom_snapshot', 'dom_type', 'dom_click', 'dom_select', 'dom_check', 'dom_press'] },
    },
    instructions: `填写并提交表单时：
1. snapshot，按 index 定位输入框/按钮/下拉框
2. dom_type 填各字段；下拉用 dom_select；复选框用 dom_check
3. dom_press Enter 或 dom_click 提交按钮
4. 验证成功文案后 system_done
不得编造字段值。`,
  },
  {
    manifest: {
      id: 'media-extract',
      version: '0.1.0',
      description:
        '[已合并] 请 skill_load catalog-crawl-sop（Phase 2–4）。本 id 仅兼容路由。',
      triggers: ['播放地址', '源地址', 'm3u8', 'mp4', 'stream', 'playback', '媒体'],
      permissions: {
        tools: ['dom_read', 'network_read', 'system_extract_page', 'system_done', 'skill_load'],
      },
    },
    instructions: `媒体/流地址提取（详情页）：

1. 优先读 PAGE SIGNALS 中 [resolved] playback / network m3u8（含 ?url= 代理）。
2. 其次 dom_read body 找 inline player 配置（var player_*、url 字段）。
3. 仍无则 network_read mode:media（子 agent 或当前页）。
4. system_done 返回 {title, playbackUrl, source}；不得编造。
5. **列表页批量**：不要在本页空转 — load parallel-read，spawn 打开各详情 URL。`,
  },
  {
    manifest: {
      id: 'media-hls',
      version: '0.1.0',
      description:
        '何时使用：需要发现页面 HLS/mp4 等媒体 URL。先 DOM 触发播放，再用网络层收集线索（不展开分片）；不处理 DRM、登录绕过或付费墙。',
      triggers: ['m3u8', 'hls', '播放', 'media', 'video'],
      permissions: {
        tools: ['dom_snapshot', 'dom_click', 'network_digest', 'network_list', 'network_wait'],
      },
    },
    instructions: `需要时先通过 DOM 触发播放。
用 network_media_hints 获取 m3u8/mp4 线索（仅线索，不展开分片列表）。
captureNetworkBodies 开启时，可对 JSON API 列表端点使用 network_get_body。
在 system_done 中报告流地址。不得暴露 cookie/Authorization。`,
  },
  {
    manifest: {
      id: 'repo-static-fetch',
      version: '0.1.0',
      description:
        '[已合并] 请 skill_load catalog-crawl-sop（Phase 2–4）。本 id 仅兼容路由。',
      triggers: ['raw', 'github', 'tree', '批量文档', 'fetch_text', 'api.github'],
      permissions: {
        tools: ['fetch_text', 'system_spawn_readonly_tasks', 'system_done', 'skill_load'],
      },
    },
    instructions: `静态 URL 批量拉取：

1. 从目录/listing 收集 HTTPS 文档或 API URL。
2. 优先父 Agent fetch_text({ urls:[...] })（≤10/次）。
3. 多组独立主题并行 → system_spawn_readonly_tasks，每 brief 含 fetch_text urls + 提取字段 + system_done。
4. 仅当响应需 JS 渲染才 tabs_open。`,
  },
  {
    manifest: {
      id: 'video-site-extract',
      version: '0.1.1',
      description:
        '用途：视频/媒体**列表页**提取可见条目或标记 topN。要每条**源地址/播放 URL**→ parallel-read+spawn；单播放页→media-extract。非：详情简述(list-then-detail)。',
      triggers: ['视频', '列表', 'm3u8', '源', 'kf0t0p', 'bilibili', '哔哩', 'extract', 'top'],
      permissions: {
        tools: [
          'dom_snapshot',
          'dom_extract_content',
          'dom_mark_items',
          'dom_mark_topn',
          'dom_execute_js',
          'dom_extract_dom',
          'dom_highlight',
          'dom_clear_highlights',
          'dom_click',
          'dom_scroll',
          'dom_wait',
          'network_digest',
          'network_list',
          'network_get_body',
          'network_media_hints',
          'system_extract_page',
        ],
      },
    },
    instructions: `视频/媒体列表页（通用）：

**仅列表可见信息**（标题+链接+封面）：dom_extract_content / dom_read list → system_done。
**每条要源地址/播放 URL**（在详情/播放页）：skill_load parallel-read → spawn 并行打开各详情 URL；详情页用 media-extract + PAGE SIGNALS。
**单条「讲了什么」**：list-then-detail。
**单播放页已在当前 tab**：media-extract。

标记：仅用户明确要求时 dom_mark_topn/dom_mark_items。
禁止：列表页 execute_js 空转；navigation:forbidden 时父 tab 串行点开详情。`,
  },
  {
    manifest: {
      id: 'list-then-detail',
      version: '0.1.1',
      description:
        '何时使用：用户问 topN 第 k 条「讲了什么/简述/简介/详情页」——先在列表页 extract，再打开该条详情页读内容后总结。不适用于「总结当前页」或只提取标题链接/视觉标记。',
      triggers: [
        '故事',
        '简述',
        '简介',
        '详情页',
        '讲了',
        'top1',
        '第一条',
      ],
      permissions: {
        tools: [
          'dom_snapshot',
          'dom_extract_content',
          'dom_click',
          'dom_navigate',
          'dom_scroll',
          'dom_wait',
          'dom_extract_dom',
          'system_extract_page',
        ],
      },
    },
    instructions: `列表 → 打开详情 → 简述：

不要用于「总结当前页 / 这篇文档」——那种任务直接 snapshot 后 system_done。
1. 若尚无列表证据：dom_extract_content({ n })（n 取任务里的 topN，默认 4）。记下目标条目的 index、title、url。
2. 打开详情（二选一，禁止空 navigate {}）：
   - 优先 dom_click({ index, revision }) 点该卡片；
   - 或 dom_navigate({ action: "url", url }) 用已提取的 pageUrl。
3. 打开后 dom_snapshot（必要时 scroll）；根据标题/简介/可见正文写 2–5 句简述。缺字段就说缺失，不得编造剧情。
4. system_done 给出：条目标题、url、简述。
不要回列表再 mark_topn；不要点站点导航（热门/首页）。`,
  },
  {
    manifest: {
      id: 'reusable-extractor-script',
      version: '0.1.0',
      description:
        '何时使用：要把当前页证据沉淀成可复用提取器。生成 Python/Shell/JS 脚本并 script_save；禁止嵌入 cookie、Authorization 或一次性签名 URL。',
      triggers: ['脚本', 'python', 'shell', '提取器', '重复使用', 'extractor'],
      permissions: {
        tools: ['dom_snapshot', 'dom_extract_dom', 'network_list', 'network_get_body', 'script_save'],
      },
    },
    instructions: `生成可复用提取脚本时：
1. 观察 DOM 与网络证据；优先稳定的公开 JSON/API 请求，少用脆弱 CSS 选择器。
2. 复杂提取用 Python；接受 URL 或页面 HTML 输入，输出 title/pageUrl/mediaUrls 的 JSON 行。
3. 不得嵌入 cookie、Authorization、DRM 绕过或一次性签名 URL。
4. 注释中写明超时、User-Agent、错误处理与依赖/用法。
5. script_save 保存；先返回 saved id，用户明确要求后再下载。`,
  },
  {
    manifest: {
      id: 'qa-smoke',
      version: '0.1.0',
      description:
        '何时使用：快速冒烟验收关键路径。流程：snapshot → 点击主 CTA → 验证预期文案 → 报告通过/失败。',
      triggers: ['smoke', 'qa', '测试', '验收'],
      permissions: { tools: ['dom_snapshot', 'dom_click', 'dom_type'] },
    },
    instructions: `快照 → 点击任务相关主 CTA → 确认预期文案 → 返回通过/失败。`,
  },
  {
    manifest: {
      id: 'ecommerce-compare',
      version: '0.1.0',
      description:
        '用途：电商商品列表比价（标题、价格、店铺）。触发：商品、价格、购物、比价。工具：dom_read list、dom_extract。非：开源项目、GitHub 仓库、两个库对比。',
      triggers: ['商品', '比价', '价格', '电商', '购物'],
      permissions: {
        tools: ['dom_snapshot', 'dom_extract_dom', 'dom_scroll', 'dom_wait', 'dom_extract_content', 'dom_mark_topn'],
      },
    },
    instructions: `商品调研时：
1. 仅提取可见列表证据：标题、价格、店铺、评分、公开 URL。
2. 用简洁表格对比，标出缺失字段。
3. 不得登录、加购、结账或填写支付信息。
4. 推广/赞助卡片与普通商品分开处理。`,
  },
  {
    manifest: {
      id: 'complex-form-draft',
      version: '0.1.0',
      description:
        '何时使用：复杂多步表单草稿。逐步 snapshot 并只填用户已提供字段；最终提交/验证/支付前必须 ask_user；不编造个人信息。',
      triggers: ['复杂表单', '申请', '报名', '注册', '多步骤表单', 'draft form'],
      permissions: {
        tools: ['dom_snapshot', 'dom_type', 'dom_select', 'dom_check', 'dom_press', 'dom_wait'],
      },
    },
    instructions: `复杂表单时：
1. 每步 snapshot，先识别必填项再输入。
2. 仅填写用户明确提供的值；不得编造个人、法律或财务信息。
3. 最终提交、验证、支付或对外分享前停止并 ask_user 确认。
4. 用户批准后验证确认页或成功提示。`,
  },
]
