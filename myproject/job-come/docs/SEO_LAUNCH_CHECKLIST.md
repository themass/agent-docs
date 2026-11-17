# 舟卡 JobCome — SEO 上线清单

- **状态**：P0/P1 代码侧已完成（提交 1c99768），**站长平台验证与提交仍需人工**
- **最后更新**：2026-11-17

代码侧：`frontend/web/lib/seo/`、`app/guides/`、`app/sitemap.ts`、`app/robots.ts`、
`app/opengraph-image.tsx`、`public/llms.txt`。竞品调研与结论见
[`discussions/DISCUSSION-COMPETITOR-SEO-2026-11-17.md`](discussions/DISCUSSION-COMPETITOR-SEO-2026-11-17.md)。

## 结构性现状（2026-11-17 更新）

旧版清单说「只有两个页面有正文、`/` 只是 redirect」——这两条已经解决：

- `/` 现在是真着陆页（SSR，约 2,400 可见字，FAQPage 结构化数据，一天缓存）。
  旧的 meta-refresh 软跳转连同 `s-maxage=31536000` 一年缓存一起去掉了。
- `/guides` 内容工厂已上线 4 篇指南（数据驱动：`lib/seo/content.ts` 加一条 = 新页面 +
  路由 + sitemap + JSON-LD + 互链自动生成）。首页与全站 footer 都有入口。
- 产品路由（`/resume-agent` 等）仍是登录后的客户端工作台，爬虫看到空壳——这是有意保留的，
  承载排名的是着陆页 + 指南 + `/resume-format`，产品页只承接转化。

**我们的问题从来不是排名，是可见性：从未向任何搜索引擎提交过。** 下面「你需要做的」是当前唯一阻塞。

## 你需要做的（Agent 做不了：账号是你的）

### 1. Google Search Console —— 用 DNS 验证「网域」资源

1. <https://search.google.com/search-console/about> 添加资源，类型选**网域**（不是网址前缀）
2. 它会给一条 TXT 记录（形如 `google-site-verification=...`），加到 **DNSPod**
   （sspacee.com 的 DNS 在那儿，ns 为 `f1g1ns1/2.dnspod.net`）。主机记录填 `@`。
3. 网域资源一次覆盖 http + https + www + 裸域，以后加子域不用重新验证
4. 验证通过后：提交 sitemap `http://jc.sspacee.com/sitemap.xml`

（若同时想用 meta 标签方式：把 token 填 `NEXT_PUBLIC_GSC_SITE_VERIFICATION` 并重新部署，
标签自动注入；DNS 与 meta 二选一即可，推荐 DNS。）

### 2. 百度搜索资源平台

1. <https://ziyuan.baidu.com/> 注册并验证站点（可用 HTML 标签方式：
   token 填 `NEXT_PUBLIC_BAIDU_SITE_VERIFICATION` → 重新部署 → 回平台点验证）
2. 提交 sitemap；开通「快速反馈索引」和「主动推送」（普通推送需要 token，之后我可以写脚本接）
3. 注意：无 ICP 备案 + 境外服务器，百度收录通常 1–3 个月起步，这不是代码问题

### 3. （可选）Bing / Yandex

Bing 会收录 GSC 提交的站点，可以先不做；要做就同样 token 进 `NEXT_PUBLIC_BING_SITE_VERIFICATION`。

### 4. 分析埋点（可选，10 分钟）

Plausible / Umami 之类自托管分析：把脚本地址填 `NEXT_PUBLIC_ANALYTICS_SRC`
和 `NEXT_PUBLIC_ANALYTICS_DOMAIN`，重新部署即生效；不填则页面上没有任何第三方脚本。
（AdSense 走独立的 consent 门，与分析互不影响。）

### 5. 验证后必做

以上任何 `.env` 改动都是**构建期**变量：填完必须重新跑 `deploy.sh`（不能 `--skip-frontend`），
重启不生效——见 [`operations/OPS-DEPLOYMENT.md`](operations/OPS-DEPLOYMENT.md) §3。

## 已完成（无需人工）

- ✅ `/` 真着陆页 + 价格如实标注（免费额度直接从后端常量镜像，`lib/seo/pricing.ts`，
  价格变了改一处、公开文案不会说谎）
- ✅ OG 分享图（`app/opengraph-image.tsx`，全站默认 1200×630）
- ✅ FAQPage：`/`、`/resume-format`、全部指南均带，且答案同时是页面可见文字（合规要求）
- ✅ robots.txt 为 GPTBot / OAI-SearchBot / PerplexityBot / ClaudeBot 单开规则段
- ✅ sitemap 16 条，`/` 居首（此前因 redirect 被整体排除）
- ✅ 验证 meta 通道：GSC/百度/Bing/Yandex 的标签从环境变量自动注入，token 不落库
- ✅ 守卫测试 `tests/seo-content.test.ts`：钉死「`/` 从 sitemap 消失」「数据有页但没进
  sitemap」两类已踩过的坑（含变异用例）

## 内容量产（真正决定排名的部分）

首批 4 篇指南（诊断 12 问 / 量化降级 / 外包·跳槽·空窗 / 面试三层追问）吸收了
resume-optimizer 的方法论，全部免登录 SSR。下一批候选，按预估价值：

1. **岗位长尾**——「后端工程师简历怎么写」等，每篇必须像现有 4 篇一样有具体判断标准，
   批量灌水会被百度和 Google 一起降权
2. **`/resume-template` 模板效果图页**——「简历模板」词量大意图明确，需要先把三套版式
   截图生成流水线做出来（参考 magic-resume 的 playwright 截图思路，见
   [`discussions/DISCUSSION-ABSORB-2026-11-17.md`](discussions/DISCUSSION-ABSORB-2026-11-17.md)）
3. 外链与品牌：知乎/即刻/小红书引流「舟卡」「JobCome」；百度对新站就是慢，别指望代码解决这件事

## 不必做

- 登录/设置页关键词（已 `noindex`）；meta 关键词堆砌（已按页配置）
- 产品工作台路由的 SSR 改造——不值得，流量应由内容页承接后引导转化
