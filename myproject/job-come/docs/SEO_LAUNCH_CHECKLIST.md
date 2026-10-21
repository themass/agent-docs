# 舟卡 JobCome — SEO 上线清单

代码侧（Agent 已完成）见 `frontend/web/lib/seo/site.ts`、各 `app/*/layout.tsx`、`sitemap.ts`、`robots.ts`、`public/llms.txt`。

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

8. **内容与外链**  
   - 公开落地页保持中文首屏说明（简历优化、模拟面试等自然出现，不堆砌）  
   - 博客/知乎/即刻等引流与品牌词「舟卡」「JobCome」  
   - SEO 无法替代产品与外链，百度对新建站尤其慢

### 不必做（除非有运营需求）

- 不必为登录/设置页做关键词（已 `noindex`）  
- 不必在 meta 里堆几十个关键词（已按页配置合理数量）
