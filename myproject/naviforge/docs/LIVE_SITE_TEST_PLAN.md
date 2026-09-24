# NaviForge 测试集与线上网站验收计划

## 目标

测试不是证明某个 fixture 能通过，而是尽早发现真实网页中的错误：

- 把“稍后再看、收藏、分享”等控件文案当成内容标题
- 把导航、轮播、广告或整块列表容器当成内容卡片
- 提取成功后重复调用模型，造成重复动作和垃圾总结
- 标记框过大、滚动后漂移、结果列表无法定位原元素
- 懒加载、同源 iframe、开放 Shadow DOM、虚拟列表导致漏项
- Network debugger 不可用时，原本可用的 DOM 提取也失败
- 站点档案失效后没有回退到通用归纳

## 三层测试

### 第一层：每次提交必须通过

运行：

```bash
npm run check
npm run build -w @naviforge/extension
npx playwright test tests/e2e/content-extract.spec.ts
npx playwright test tests/e2e/extension-content.spec.ts
```

内容：

- 纯算法自检：URL 形状、字段分类、重复结构归纳、标题选择、档案回退
- 真实浏览器 fixture：视频、电影、商品、新闻、纯文本、懒加载、iframe、Shadow DOM
- 扩展测试：只读提取不修改页面、显式标记、结果定位、滚动跟随
- 每个线上故障先保存最小 Candidate 快照，再写回归测试

这层必须确定、快速、无网络，不允许 flaky。

### 第二层：每日线上巡检

使用独立 Chrome Profile、无账号、固定语言和视口。线上内容每天变化，不比较具体标题，
只比较质量不变量。失败保存：

- 页面 URL、标题、时间、区域和视口
- 脱敏后的 Candidate JSON
- 提取报告与站点档案
- 页面截图和标记截图
- console、扩展 trace、Network attach 状态

线上巡检不阻塞普通 PR，但连续两次同站失败须阻止发布。验证码、地区封锁、HTTP 429
单独归类为 `ENV_BLOCKED`，不能伪装成通过，也不能直接算产品回归。

### 第三层：发布前人工验收

使用正常浏览器窗口检查视觉和交互：

- 1280×720、1920×1080 两种视口
- 无账号；B 站和 YouTube 再补一次已登录状态
- 提取模式与显式标记模式分别执行
- 滚动、点击结果列表定位、切换标签和切换窗口
- 页面刷新后旧标记消失，结果不会指向错误元素

## 全局通过标准

每个线上页面请求前 5 条，除非页面不足：

- 标题有效率 100%：不得是控件文案、DOM 序列化文本、纯数字或空字符串
- URL 有效率 100%：可解析、去重、指向内容详情而非导航/登录/广告
- 重复率 0%
- 数量正确：返回 5 条，或明确报告 shortfall；禁止补造
- 页面副作用：纯提取模式 DOM 标记数始终为 0
- 标记准确：每条一个框，不得包住相邻卡片或整块列表
- 标记跟随：滚动 300px 后框仍与目标卡片重合
- 定位有效：侧栏点击 TOPn 后目标进入视口中央并闪烁
- 执行收敛：确定性 Top-N 成功后不再调用模型重复提取
- 最终总结：包含编号、真实标题、URL；不输出内部 candidates/profile/debug 文案
- 降级可用：Network attach 失败时，DOM 提取和标记仍可完成

## P0 线上目标网站

### 1. Bilibili 知识频道

URL：
`https://www.bilibili.com/c/knowledge/`

覆盖：

- 大型 SPA、顶部轮播、视频网格、悬浮“稍后再看”
- 追踪参数、卡片内多个链接、异步渲染

目标效果：

- 前 5 条均为视频真实标题和 `/video/` URL
- “稍后再看、收藏、分享、热门、首页”命中数为 0
- 轮播和整块 feed 容器不得被标记
- 显式标记后侧栏 TOP1–TOP5 可定位，滚动时边框跟随

### 2. YouTube 搜索结果

URL：
`https://www.youtube.com/results?search_query=browser+agent`

覆盖：

- Web Components、Shadow DOM 风格组件、SPA 导航、懒加载
- 视频链接、频道链接、菜单按钮和 Shorts 混合

目标效果：

- 前 5 条为视频标题和 `/watch` URL
- “Watch later、Save、Share、More actions”命中数为 0
- 尽量提取频道、观看量、发布时间、时长；缺失字段不得编造
- 下滚加载后能够继续提取且不重复

### 3. 豆瓣电影 Top 250

URL：
`https://movie.douban.com/top250`

覆盖：

- 传统服务端 HTML、电影列表、多个文本字段

目标效果：

- 前 10 条为电影标题和 `/subject/` URL
- rating、year 能被识别；导演/演员文本不能抢占标题
- 提取模式不标记；标记模式每部电影只框一个条目

### 4. GitHub Trending

URL：
`https://github.com/trending`

覆盖：

- 文本为主的重复列表、仓库链接、语言和 stars 字段

目标效果：

- 前 10 条标题为 `owner/repository`
- URL 指向仓库详情，不得命中导航、登录、Sponsor 按钮
- 没有图片时仍走结构归纳，不依赖 media

### 5. Hacker News

URL：
`https://news.ycombinator.com/`

覆盖：

- 极简表格 DOM、纯文本链接、标题与 metadata 分行

目标效果：

- 前 10 条为 story 标题和目标 URL
- next、login、comments、user 不得成为主标题
- 证明 fallback 不依赖卡片、图片或现代 CSS class

### 6. Steam 畅销商品搜索

URL：
`https://store.steampowered.com/search/?filter=topsellers`

覆盖：

- 商品列表、价格/折扣、图片、地区与年龄提示

目标效果：

- 前 8 条为游戏名称和 `/app/` URL
- 价格、折扣可选提取；年龄确认页应识别为 `ENV_BLOCKED`
- 导航和推荐横幅不得进入结果

### 7. BBC News

URL：
`https://www.bbc.com/news`

覆盖：

- 新闻卡片、主头条与普通列表混合、响应式布局

目标效果：

- 前 8 条为新闻标题和文章 URL
- 菜单、频道标签、Live 导航、广告不得成为结果
- 主头条尺寸更大不能导致整个区域被框选

## P1 扩展目标

- Reddit 列表：验证投票/分享/评论控件不会抢标题；若被地区或登录墙阻断则记
  `ENV_BLOCKED`
- IMDb Top 250：与豆瓣形成同类型跨站对照
- Amazon 搜索：仅做非阻塞 canary，专门检验反爬/验证码的诚实降级
- Wikipedia 分类页：检验密集文本链接与内容导航区分
- 一个真实开放 Shadow DOM 示例站点和一个同源 iframe 示例站点

## 用户需求测试集

每个 P0 网站至少执行以下任务：

1. `列出当前页面前5条内容的名称和链接，不要标记`
2. `标记top3`（短指令回归：必须直接标记 3 条并结束，不重复调用模型）
3. `标记当前页面前5条内容`
4. 点击侧栏 TOP1、TOP3、TOP5，确认定位与闪烁
5. 向下滚动 300px，再确认标记与元素重合
6. 请求超过当前可见数量，确认自动加载或明确 shortfall
7. 禁用 Network debugger，重复纯 DOM 提取
8. 给站点写入错误 profile，确认自动回退到通用归纳
9. 连续执行两次，确认无重复结果、无残留大框、无重复模型调用

## 结果分级

- `PASS`：全部质量不变量满足
- `REGRESSION`：页面可正常读取，但标题、URL、数量、标记或总结不符合要求
- `ENV_BLOCKED`：验证码、地区限制、429、登录墙或浏览器策略导致无法读取
- `SITE_CHANGED`：DOM 结构明显变化；保存新快照并判断通用算法还是 profile 需要调整

`ENV_BLOCKED` 和 `SITE_CHANGED` 都必须留证据，不能被统计为 PASS。

## 发布门禁

- 第一层测试必须 100% 通过
- P0 七站最近一次巡检至少六站 PASS
- Bilibili、YouTube、GitHub Trending、Hacker News 四个核心布局必须 PASS
- 不允许存在标题为控件文案、整块列表标记、重复模型提取这三类 P0 缺陷
- 任何真实站点回归都必须先沉淀 Candidate 快照测试，再修生产代码
