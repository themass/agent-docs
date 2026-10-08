import { type Skill } from '@naviforge/skill-runtime'

const OBSERVE_TOOLS = [
  'browser_observe',
  'browser_act',
  'browser_nav',
  'tabs',
  'skill_load',
  'system_done',
  'system_ask_user',
  'system_captcha_wait',
]

const HARVEST_TOOLS = [
  ...OBSERVE_TOOLS,
  'web_search',
  'fetch_text',
  'network',
]

const TRAVERSE_TOOLS = [
  ...OBSERVE_TOOLS,
  'browser_nav',
  'tabs',
  'fetch_text',
  'system_spawn_readonly_tasks',
]

const PERSIST_TOOLS = [...OBSERVE_TOOLS, 'workspace']
const RESEARCH_TOOLS = ['web_search', 'fetch_text', 'tabs', 'browser_observe', 'skill_load', 'system_done']
const FRICTION_TOOLS = ['browser_observe', 'browser_act', 'skill_load', 'system_done', 'system_ask_user', 'system_captcha_wait']

function alias(id: string, aliasOf: string, triggers: string[]): Skill {
  return {
    manifest: {
      id,
      version: '0.1.0',
      description: `Alias of ${aliasOf}. Use skill_load ${aliasOf}.`,
      aliasOf,
      l1: false,
      triggers,
    },
    instructions: `This id is an alias. Load \`${aliasOf}\` instead.`,
  }
}

const GENERIC_SKILLS: Skill[] = [
  {
    manifest: {
      id: 'observe',
      version: '1.0.0',
      description: '读懂当前页：介绍、总结、冒烟点主 CTA。非：页外多源对比、多页爬取。',
      triggers: ['介绍', '总结', '概括', '本页', 'readme', '是什么', 'smoke', 'qa', '验收'],
      permissions: { tools: OBSERVE_TOOLS },
    },
    instructions: `# observe

当前页只读。先 PAGE STATE，再 browser_observe action=read（mode=body）。证据够立刻 system_done。

- 结论先行，短 bullet；不要滚动收割正文。
- 冒烟：snapshot → 点主 CTA → 验证文案 → 报告通过/失败。
- 登录墙：改 load friction，不要空转 read。
- 非本 skill：页外对比（research）、列表翻详情/分页（traverse）、抽字段/媒体 URL（harvest）。`,
  },
  {
    manifest: {
      id: 'harvest',
      version: '1.0.0',
      description: '从当前上下文抽出结构化字段（含媒体 URL、表单值、比价表）。非：多页爬全站、页外竞品调研。',
      triggers: [
        '提取',
        '源地址',
        'm3u8',
        'mp4',
        'hls',
        '播放',
        'media',
        '表单',
        'form',
        '比价',
        '价格',
        '商品',
      ],
      permissions: { tools: HARVEST_TOOLS },
    },
    instructions: `# harvest

从**已有页面上下文**抽出结构化记录，不发明站点 SOP。

1. PAGE STATE / PAGE SIGNALS 优先。
2. 列表：browser_observe action=read mode=list（或 extract）。
3. 媒体 URL：先 DOM 触发播放（browser_act click），再 network action=read mode=media|hls。无直链则 shortfall，勿破解 DRM。
4. 表单：只填用户已给字段；提交前 system_ask_user。
5. 输出 JSON/表格后 system_done。禁止嵌入 cookie / Authorization / 一次性签名 URL。`,
  },
  {
    manifest: {
      id: 'traverse',
      version: '1.0.0',
      description: '跨页遍历：分页、列表→详情、批量只读。非：单页介绍、页外搜索对比。',
      triggers: ['爬取', '抓取', '分类', '分页', '批量', '所有', '每个', '详情页', '简述', 'catalog', 'crawl'],
      permissions: { tools: TRAVERSE_TOOLS },
    },
    instructions: `# traverse

多页/多 URL。父 Agent 规划；互不依赖的只读片用 system_spawn_readonly_tasks（每批 ≤3）。

1. 发现：导航/分类 URL，或当前页当作唯一 section。
2. 列表页 extract {title,url}；分页跟 rel=next / 页码。
3. 详情：spawn mode=tab（渲染页）或 fetch（静态 URL）。navigation:forbidden 时父 tab 禁止串行 navigate。
4. 缺字段写 shortfall，勿编造。
5. 会话墙先 friction。`,
  },
  {
    manifest: {
      id: 'friction',
      version: '1.0.0',
      description: '会话摩擦：登录、验证码、限频、付费墙、cookie。非：自动打码、伪造 cookie、绕过加密。',
      triggers: ['登录', 'login', '验证码', 'captcha', '人机', '付费墙', '429', '限频'],
      permissions: { tools: FRICTION_TOOLS },
    },
    instructions: `# friction

PAGE FRICTION 阻塞时用本 skill。

- 登录/VIP：**不要**自己填凭证、**不要**教用户怎么登录——直接 system_ask_user 请用户登录，等完成后继续。
- 人机：system_captcha_wait。
- 限频：等待 / 降并发 spawn；禁止高频空转。
- 不得自动打码、伪造 cookie、绕过 DRM/付费墙。
- 通过后回到原任务（observe / harvest / traverse / persist）。`,
  },
  {
    manifest: {
      id: 'persist',
      version: '1.0.0',
      description: '沉淀产物：官方下载、PDF、workspace 文件、可复用脚本。非：破解 DRM、批量爬全站。',
      triggers: ['下载', 'download', '保存', 'export', 'pdf', '脚本', 'python', 'scraper', '提取器'],
      permissions: { tools: PERSIST_TOOLS },
    },
    instructions: `# persist

把证据变成用户可拿走的文件。

- 官方下载：找下载/导出按钮 → browser_act click → wait kind=download。登录/VIP 先 friction。
- 可见页：browser_observe action=pdf。
- 脚本：采样 PAGE STATE（分类/分页 URL 模式）→ workspace action=script_save（Python/JS/shell）。禁止写入 cookie、Authorization、一次性签名 URL。
- 生成爬虫脚本时：读结构即可，不要 full-catalog 爬完再写。pages 默认 1 可配置。
- system_done 附 path + shortfall。`,
  },
  {
    manifest: {
      id: 'research',
      version: '1.0.0',
      description: '页外多源对比（产品/仓库/文档）。非：当前页列表 topN、电商比价。',
      triggers: ['对比', '区别', 'vs', '两个项目', 'github', '竞品'],
      permissions: { tools: RESEARCH_TOOLS },
    },
    instructions: `# research

当前 tab 可能是壳页，不要当证据空转 snapshot。

web_search → tabs action=open 2–3 源 → browser_observe read → 对比 → system_done。
静态 raw/API 用 fetch_text。不要把电商商品价或当前页 topN 当成调研。`,
  },
]

const ALIASES: Skill[] = [
  alias('page-read', 'observe', ['介绍', '总结', 'readme']),
  alias('qa-smoke', 'observe', ['smoke', 'qa']),
  alias('media-extract', 'harvest', ['源地址', 'm3u8', 'mp4']),
  alias('media-hls', 'harvest', ['hls', 'm3u8']),
  alias('video-site-extract', 'harvest', ['视频', '列表']),
  alias('form-fill', 'harvest', ['form', '表单']),
  alias('ecommerce-compare', 'harvest', ['比价', '商品']),
  alias('catalog-crawl-sop', 'traverse', ['分类', '爬取', 'catalog']),
  alias('parallel-read', 'traverse', ['批量', '并行']),
  alias('repo-static-fetch', 'traverse', ['raw', 'github']),
  alias('list-then-detail', 'traverse', ['简述', '详情页', '讲了']),
  alias('page-friction', 'friction', ['登录', '验证码', 'captcha']),
  alias('auth-assisted', 'friction', ['login', 'sign in']),
  alias('complex-form-draft', 'friction', ['复杂表单', '报名']),
  alias('document-download', 'persist', ['下载', 'download']),
  alias('reusable-extractor-script', 'persist', ['脚本', 'python']),
  alias('scraper-script-sop', 'persist', ['scraper', '爬虫']),
  alias('research-compare', 'research', ['对比', 'github']),
]

/** 内置能力技能（MV3 不能加载任意远程 JS）。别名不进 L1。 */
export const BUNDLED_SKILLS: Skill[] = [...GENERIC_SKILLS, ...ALIASES]
