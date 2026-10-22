# 舟卡 JobCome — SEO 上线清单

代码侧（Agent 已完成）见 `frontend/web/lib/seo/site.ts`、各 `app/*/layout.tsx`、`sitemap.ts`、`robots.ts`、`public/llms.txt`。

## 已知的结构性限制：只有两个页面有正文

除 `/resume-format` 和 `/about` 外，所有可索引路由都是 `"use client"` 工作台，
且内容在登录后才渲染；`/` 只是 redirect。**爬虫抓它们拿到的是 meta + 空壳。**

`keywords` meta 排不动没有正文的页面（Google 自 2009 年起完全忽略该字段，
百度权重也极低），所以真正承载关键词的是 `/resume-format` 的正文与 FAQ 结构化数据。
下面「内容」一节的优先级因此高于任何 meta 调整。

## 你需要做的

### 必做（上线前）

1. **配置正式域名**  
   在部署环境设置 `NEXT_PUBLIC_SITE_URL=https://你的域名`（参考 `frontend/web/.env.example`）。  
   未设置时 sitemap/canonical 会指向 `http://localhost:3000`。

2. **Google Search Console**  
   - 添加资源并验证所有权（DNS 或 HTML 文件）  
   - 提交 `https://你的域名/sitemap.xml`  
   - 关注「页面索引」「核心网页指标」

3. **百度搜索资源平台**  
   - [https://ziyuan.baidu.com/](https://ziyuan.baidu.com/) 验证站点  
   - 提交 sitemap、开启 HTTPS、按需做移动适配  
   - 国内备案（ICP）若用大陆服务器，通常影响百度收录与稳定性

4. **HTTPS 与跳转**  
   - 全站 HTTPS  
   - `www` / 裸域 301 统一到一处（与 `NEXT_PUBLIC_SITE_URL` 一致）

### 建议做（上线后 1–2 周）

5. **分享图**  
   准备 1200×630 的 OG 图，放到 `public/og.png` 并在 `app/layout.tsx` 的 `openGraph.images` 引用（当前未配图，社交分享为纯文字）。

6. **站长验证码（可选）**  
   若用 meta 验证，在 `layout.tsx` 增加 `verification: { google: '...', other: { 'baidu-site-verification': '...' } }`。

7. **定期审计**  
   用已安装的 claude-seo（`~/.cursor/skills/seo`）对生产 URL 做 `/seo audit` 思路的技术检查；或 Cursor 项目 skill：`.cursor/skills/jobcome-seo`。

## 内容（真正决定排名的部分）

关键词已按页配置完毕，继续加词的边际收益接近零。有收益的是**增加有正文的页面**。

### 已有

- `/resume-format` — 简历格式转换与排版。覆盖 `pdf转word` / `word转pdf` /
  `pdf编辑` / `pdf格式调整` / `word格式调整` 及简历限定长尾，带 `FAQPage` 结构化数据。

### 候选（按预估价值排序，均需服务端渲染、免登录）

1. **`/resume-template`** — 三套版式的实际效果图与适用场景。
   「简历模板」搜索量大且意图明确，而我们真有模板；现在只有文字描述、没有截图。
2. **`/resume-guide`** — 简历怎么写：每条经历写什么、成果怎么量化。
   这是产品的核心主张，目前完全没有对外表述。
3. **岗位类长尾** — 「后端工程师简历怎么写」等。量产页需先有 1 条写好的样板，
   否则就是薄内容，百度与 Google 都会降权。

### 外链与品牌

- 知乎 / 即刻 / 小红书引流，品牌词「舟卡」「JobCome」  
- SEO 无法替代产品与外链；百度对新站收录尤其慢（通常 1–3 个月）

### 不必做（除非有运营需求）

- 不必为登录/设置页做关键词（已 `noindex`）  
- 不必在 meta 里堆几十个关键词（已按页配置合理数量）
