# DISCUSSION：同类产品对比与我们在 Google 上「出不来」的原因

- **状态**：调研结论，未冻结（不构成功能需求；行动项待确认后写入 PRD/路线图）
- **最后更新**：2026-11-17
- **方法**：全部结论基于 2026-11-17 对 8 个对象 + 我们线上站的直接抓取实测（`curl` 原始 HTML、`sitemap.xml`、`robots.txt`、HTTP 头），不是看宣传页。抓不到的地方明说抓不到。
- **抓取清单**：`github.com/wyh0626/resume-optimizer`、`zhuanlan.zhihu.com/p/23068283985`、`qiuzhifangzhou.com/resume`、`magicv.art/zh`、`www.wondercv.com`、`lp.mentorx.net/resume`、`aicatgo.com/enhance`、`cv.mianlingai.com`，以及我们自己的 `jc.sspacee.com`。

## 0. 结论

**「排名很靠前 vs 我们都出不来」这件事，主要不是排名问题，是可见性问题。** 三个层次的原因，按可修复成本排序：

1. **我们几乎肯定从未向搜索引擎提交过站点。** 线上 10 个可索引页面的 HTML 里，GSC / 百度搜索资源平台的验证标签一个都没有。`SEO_LAUNCH_CHECKLIST.md` 里这两项标的是「必做」，实测证明没做。没提交 + 没有任何外部链接 + 页面本身没内容 = Google 没有任何理由来抓我们。
2. **即使被抓到，9/10 页面给爬虫的是空壳。** 实测：8 个路由的爬虫可见正文字数 70–200 字、h1 大多为 0（内容在登录后由客户端渲染）。只有 `/resume-format` 有 1423 字和一个 h1。根路径 `/` 更糟：HTTP 200 + `<meta http-equiv="refresh" content="1;url=/resume-agent">`，可见正文 60 字，且被 CDN 以 `s-maxage=31536000`（一年）缓存。任何指向我们域名的外链，权重经过根路径时几乎传递不下去。
3. **竞品靠的是页面数量工厂，不是单页优化。** WonderCV 一个站 25,481 个 URL（其中 14,590 个「校招」长尾页），mentorx.net 1,240 篇，智灵简历 64 个精编 SSR 页 + 结构化数据。我们 sitemap 里一共 10 个 URL，全是产品工作台。这不是同一场竞争。

对照组也实测了：**求职方舟**元数据齐全但是纯 SPA（爬虫可见 0 字），它也没有 Google 可见度——这直接证明「加 meta、加 sitemap」本身不产生排名，**服务端渲染 + 内容页数**才是。

---

## 1. 我们自己的实测（2026-11-17，jc.sspacee.com）

| 项 | 实测值 |
|---|---|
| sitemap | 10 个 URL，全部产品路由，无内容页 |
| 爬虫可见正文 | 8/10 路由 70–200 字；`/resume-format` 1,423 字（唯一有 h1 的页） |
| 根路径 `/` | HTTP 200 + `meta refresh 1;url=/resume-agent`，可见 60 字，`s-maxage=31536000` |
| 搜索引擎验证标签 | **0 个**（GSC、百度、Bing 都没有）⇒ 基本可断定从未提交 |
| 分析/统计代码 | 无任何埋点 |
| OG 图 | 无 |
| 域名 | apex `sspacee.com` 301 → `jc.sspacee.com`；http/https 双开不跳转（见 OPS-DEPLOYMENT §1.1，是有意的） |
| 关键词架构 | 代码层面是认真的：每路由独立 keyword 域、格式类关键词只放在真正做转换的 `/resume-format`（`lib/seo/site.ts` 注释写明了理由） |

代码里的关键词架构比多数竞品讲究。**问题全在执行层**：正确的元数据贴在空壳页面上，等于没有。

## 2. 竞品档案

### 2.1 WonderCV（wondercv.com）—— 页面数量工厂的天花板

- Nuxt SSR，首页爬虫可见 **41,000 字**。
- `sitemap.xml` 是 sitemapindex，**15 个子文件 / 25,481 个 URL**：`xiaozhao`（校招）14,590、`template` 4,128、`blog` 2,315、`mianshi` 775、`sample` 733、`mianjing` 430……这是典型的「岗位 × 城市 × 专业」程序化长尾页海。
- 9 个免费工具页（正字器、字数统计之类）作为引流钩子。
- JSON-LD：`WebSite`+`SearchAction`、`Organization`、`FAQPage`；每 URL 独立 https canonical；robots 里专门写了 AI 爬虫（GPTBot 等）策略。
- 备案 2017 年（站龄 8 年+）、外链来自招聘站页脚合作、知乎机构号/小红书/微博/抖音矩阵。
- 商业化：会员 ¥189 起/月。

**对我们的意义**：它证明这条内容工厂路在国内简历市场能撑起主要流量。但 25k 页的量级不是我们要抄的对象，要抄的是「模板页 / 样本页 / 面试题库页 / 岗位长尾页」这四类页型。

### 2.2 智灵简历（cv.mianlingai.com）—— 最接近我们、最值得直接对标

- **64 URL 的类型化 sitemap**：25 篇 guide + 17 个模板页 + 9 个样本页 + 工具页，每页 SSR、约 3,000 字、带 `BreadcrumbList`。
- `SoftwareApplication` JSON-LD 且 **`"price":"0"`**，配 `FAQPage`；title 直接打「免费 AI 简历生成器 | 永久免费 · 无水印 · 3分钟」。
- 专业版 ¥0 永久 + 向上销售到模拟面试（独立子域 mj.mianlingai.com）——**它的 upsell 恰好是我们的主场**。
- `/sponsors` 捐赠墙、开源仓库 wearzdk/lite-cv-ai、京ICP备2025138436号-1（2025 年新站——**它用一年时间把 64 页做起来了，这就是可行性证明**）。

**对我们的意义**：这是「一个小团队能在一年内复制」的档位。它的页面模板（guide/模板/样本三件套 + 面包屑 + 价格 schema）可以直接作为我们内容页的原型。

### 2.3 求职方舟（qiuzhifangzhou.com）—— 反面教材

纯 Vue SPA：爬虫可见 **0 字、0 个 h1**；16 URL 的 sitemap 全是空壳；连 `robots.txt` 都没有。全站唯一有正文的是 VitePress 文档 `/doc/about/`（3,458 字）。它说明：**只做元数据不做渲染 = 零可见度**。产品本身是校招垂直 + 浏览器插件分发。

### 2.4 魔方简历（magicv.art）—— GitHub 路线的天花板

开源 11,453★，免费/本地优先，本地生成不上云（这是它对隐私敏感用户的杀伤点）。SEO 反而很弱：sitemap 只有 2 个 URL，`/zh` 仅 742 字，无 JSON-LD，SPA catch-all 造成软性重复页，只有 hreflang 是对的。**它的全部流量来自 GitHub 星标 + HelloGitHub/Trendshift 收录 + Offerin 联盟分销，不是搜索。**

### 2.5 wyh0626/resume-optimizer —— 零产品站的 Agent 分发

没有网站、没有 SEO，一个 `SKILL.md`：**578★、skills.sh 上 466 次安装**，分发方式是被装进 20+ 个 Agent CLI（Claude Code、Codex、Cursor…）。它的 prompt 工程值得直接吸收：硬规则「不编造成果」、每条经历「业务目标→动作→可感知结果」三段链、7 段固定输出契约。

### 2.6 mentorx（lp.mentorx.net）—— 真正的资产在另一个域名

落地页本身是 27 字的 SPA，且 canonical 有 bug（所有路由都指向 `/general`）。**真正的 SEO 资产是 www.mentorx.net：1,240 个 URL、首页 6,750 字、4 组 JSON-LD、robots 明确 Allow GPTBot/OAI-SearchBot。** 转化路径 = 落地页放微信二维码私域加人，不挂价格。这是一家 K12 公司用内容站给简历工具导流的模式。

### 2.7 aicatgo.com/enhance

v0 生成的一次性玩具：单个 textarea，61 字可见内容，无 sitemap / robots / canonical。在搜索里完全隐形，**任何一页像样的内容都能打败它**。放进清单只为了说明「上线一个 AI 简历页」的门槛有多低——门槛低不等于能被找到。

### 2.8 知乎专栏 p/23068283985

**未能读取**：直抓 403，搜索引擎检索不到该篇。结论缺失，不作为任何判断的依据。

## 3. 产品对比：我们的优劣势

| 维度 | 我们（舟卡） | 最强竞品位置 | 差距判断 |
|---|---|---|---|
| Agent 对话式整理职业档案 | **主场**。多轮 intake、evidence、确认门控改写 | 无一家做到真正的对话式档案演进（aicatgo 是单轮玩具，其余是模板填充） | **优势** |
| 岗位匹配 + JD 对齐 | 有，且是流程的一部分 | WonderCV 有职位库联动 | 持平，但对方有 14,590 个岗位页做承接 |
| 模拟面试 + 复盘 | 产品内闭环 | 智灵把它做成了**独立子域 upsell**；mentorx 只做卖点 | 我们有功能，他们把它变成了第二个流量入口 |
| 导出质量（PDF/DOCX、中文字体） | 工程投入扎实 | 各家都宣称好 | 难以外显，需靠样本页证据化 |
| 模板数量 | 少 | WonderCV 4,128 个模板页 | **大差距**，但模板页是内容页不是工程量（一套渲染 + N 份数据） |
| 免费额度感知 | 无「免费」叙事 | 智灵标题直接写「永久免费 · 无水印」，price=0 schema | **叙事差距**，成本近零 |
| 本地/隐私优先 | 云端 | 魔方简历本地生成 | 不同人群，不必跟 |
| 分发 | 几乎没有 | GitHub（魔方）、skills.sh（resume-optimizer）、插件（方舟）、社媒矩阵+招聘站外链（WonderCV）、私域微信（mentorx） | **全线空白**，这是「出不来」的外链侧原因 |

一句话：**产品纵深不落后，落后在「把纵深拆成可被搜索的东西」和「让域名获得信任」两件事上。**

## 4. 他们排前的三个机制（我们全缺）

1. **可渲染的内容页数。** WonderCV 25k / mentorx.net 1,240 / 智灵 64，全部 SSR。我们 10 个 URL 里 1 个有正文。Google 排序的前提是页面上有可排的东西。
2. **站点信任信号。** 备案年限（2017 vs 我们无备案叙事）、GSC 提交 + sitemap 主动推送（智灵、WonderCV 均有验证痕迹，我们 0 标签）、外链（招聘站页脚、GitHub、捐赠墙、联盟）。
3. **点击率包装。** 「免费 / 无水印 / 3 分钟」「¥0 永久」写进 title，`FAQPage` + 带价格的 `SoftwareApplication` 拿富摘要。我们的 title 是品牌名（`舟卡 · JobCome`），在结果页里对陌生人零信息量。

## 5. 行动清单（映射到 SEO_LAUNCH_CHECKLIST.md）

`SEO_LAUNCH_CHECKLIST.md` 的诊断是对的（「爬虫抓它们拿到的是 meta + 空壳」），但它的两项「必做」没执行，且低估了内容页的量级要求。建议的优先级：

**P0 · 一两天内，零产品改动**
- GSC（DNS 验证「网域」资源，一次覆盖 http+https，见 OPS-DEPLOYMENT §1.1）+ 百度搜索资源平台提交 sitemap。做完这一步才算开始参赛。
- 加分析（至少 Plausible/GA 一个），否则永远在盲飞。
- 修根路径：`/` 从 meta-refresh 改为真 308（或让 `/` 本身就是可索引的内容页——见 P1），并去掉一年期 `s-maxage`。
- 给 `/resume-format` 补 OG 图和 `FAQPage`（它已经是我们唯一有正文的页，先把它武装起来）。

**P1 · 一周，一个模板 + 数据**
- 把 `/` 做成真正面向陌生访客的着陆页（SSR，~3,000 字量级，title 打「免费 AI 简历优化」而非品牌名），工作台入口下移——这是所有外链权重的落点。
- 照智灵的三件套开内容路由：guide（10–20 篇）/ 模板页 / 样本页，SSR + 面包屑 + `BreadcrumbList`/`FAQPage`，sitemap 从 10 → 50+。
- title 与价格叙事：把「免费」「无水印」写进可索引页 title；若 free tier 属实，`SoftwareApplication` 带上 `"price":"0"`。

**P2 · 持续，选一条分发线**
- Agent 生态：把我们最有价值的 prompt 资产做成 `SKILL.md` 发 skills.sh（resume-optimizer 用 578★ 证明了这条路，成本极低且与我们的技术栈天然契合）。
- 模拟面试作为独立可索引入口学智灵（它验证了这是我们人群的付费点）。
- 外链最小闭环：开源一个组件或工具页 + 向导航站/HelloGitHub 提交。

**不做的**：25k 页程序化站群（WonderCV 量级）、本地优先（魔方路线）、微信私域（mentorx 路线，除非经营策略变）。

## 6. 未验证项（诚实记录）

- **收录量**：Bing `site:` 查询撞验证码、DuckDuckGo 端点反爬、crt.sh 返回空、Wayback CDX 为空——**全部不可信，故不下「未被收录」的断言**，只能说「无证据表明被收录」。P0 的 GSC 提交后这个问题自然有答案。
- 知乎文章正文未能读取（403 且检索不到）。
- 各竞品后台数据（真实流量、关键词排名）不可得；本文的页面数/字数/结构化数据均为前台实测，「谁排前面」的体感与实测机制一致但未逐词验证。
- 竞品价格随活动变动，以文中抓取时点为准。
