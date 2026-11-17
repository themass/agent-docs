import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { TrackLink } from "@/components/analytics/TrackLink";
import { ANALYTICS_EVENT } from "@/lib/analytics";
import {
  DOCUMENT_DESCRIPTION,
  PRODUCT_NAME,
  PRODUCT_NAME_EN,
} from "@/lib/brand";
import {
  FREE_DOWNLOADS_PER_ACCOUNT_TEXT,
  FREE_MOCK_RUNS_PER_MONTH_TEXT,
  MEMBERSHIP_PRICE_TEXT,
} from "@/lib/seo/pricing";
import { GUIDES } from "@/lib/seo/content";
import { faqJsonLd, pageMetadata, SITE_KEYWORDS_ZH } from "@/lib/seo/site";

/**
 * `/` used to be `redirect("/resume-agent")`. Because the route is statically
 * prerendered, Next compiled that into an HTML `<meta http-equiv="refresh">` served
 * with HTTP 200 and `s-maxage=31536000` — a soft redirect. A crawler is told to index
 * an empty page, and any inbound link to the domain root passes almost nothing on.
 *
 * So `/` is a real server-rendered landing page now: it is the only page an
 * unfamiliar visitor — or a search engine — sees, which makes it the only page where
 * "what is this, what does it cost, why trust it" can be answered. The workbench
 * stayed where it was, one click away.
 *
 * `revalidate` bounds staleness. A static page cached with `s-maxage=31536000` does
 * not refresh at the CDN for a year after a redeploy, so copy changes would silently
 * never ship; one day is short enough to be invisible to a reader and cheap to serve.
 */
export const revalidate = 86400;

const SEO = {
  // `title.absolute` bypasses the site-wide `%s · 舟卡` template: on the entry page the
  // keyword phrase has to lead, and the brand already closes the string.
  title: "免费 AI 简历优化 · 简历诊断、按岗位改写与模拟面试",
  description:
    "上传简历，AI 诊断内容问题并按目标岗位改写：补齐量化结果、对齐 JD 关键词，再做模拟面试与复盘。注册即可使用，含 1 次免费下载与每月 1 次免费模拟面试。",
  path: "/",
  keywords: [...SITE_KEYWORDS_ZH],
};

export const metadata: Metadata = {
  ...pageMetadata(SEO),
  title: { absolute: SEO.title },
};

const STEPS = [
  {
    title: "上传现有简历",
    body: "PDF、Word（.docx）、图片、纯文本都可以。系统把它解析成一份结构化档案：每段经历、每条成果各自成项，而不是一团没法编辑的文字。扫描件和拍照的简历走 OCR 识别。",
  },
  {
    title: "对话补齐，不靠脑补",
    body: "助手按缺口逐项追问，把「负责订单系统」问到能说清的程度：当时的业务目标是什么、你具体做了什么、结果用什么数字或变化证明。每条补充都要你在界面上确认后才写进档案：没有经你确认的话，不会变成简历上的一句话。",
  },
  {
    title: "按目标岗位改写、导出",
    body: "贴一段 JD，系统对照档案给出匹配度和差距，再据此调整关键词、项目重点和职业叙事。改完从三套版式里选一套，导出 PDF 或 Word。",
  },
];

const CAPABILITIES = [
  {
    name: "简历诊断与改写",
    body: "不是套模板，而是找出会让简历被刷掉的具体问题：时间线矛盾、只有职责没有结果、术语前后不一致、缺乏量化的表述。每条改写都要求「动作 + 产物 + 结果」，缺数据时明确标成待补，不替你编。",
    href: "/resume-agent",
    linkText: "开始优化简历",
  },
  {
    name: "格式转换与排版",
    body: "读 PDF / Word / 图片 / 纯文本，写 PDF / Word / HTML。上传什么格式和导出什么格式是两件独立的事，内容只维护一份。",
    href: "/resume-format",
    linkText: "看支持的格式",
  },
  {
    name: "岗位匹配",
    body: "解析 JD，评估它和你档案的匹配度，指出差距在哪：是缺关键词、缺某类经历，还是经历有但没写出来。",
    href: "/jobs",
    linkText: "看岗位匹配",
  },
  {
    name: "模拟面试与复盘",
    body: "按你的简历和目标岗位出题，面试结束生成评分报告，把回答里的问题归档，之后可以回看。题库会沉淀下来。",
    href: "/coach-agent",
    linkText: "开始模拟面试",
  },
  {
    name: "投递与面试记录",
    body: "投递记录、真实面试归档、复盘笔记放在一处。换工作是一连串决定，记录下来才能看清哪一步真的有效。",
    href: "/applications",
    linkText: "看投递记录",
  },
  {
    name: "按岗位留存的导出记录",
    body: "每次优化导出的文件都记下版本、当时针对的岗位和改写力度，可以按岗位回看、重新下载，也能对比同一份简历投不同岗位时的差别。",
    href: "/resume-versions",
    linkText: "看导出记录",
  },
];

const PRICING = [
  {
    tier: "注册即可用",
    price: "0 元",
    items: [
      "上传解析、结构化档案、对话优化、岗位匹配全部可用",
      FREE_DOWNLOADS_PER_ACCOUNT_TEXT,
      `模拟面试每月 ${FREE_MOCK_RUNS_PER_MONTH_TEXT}`,
      "对话产生的修改一律需要你自己确认才写入档案",
    ],
    note: "免费档导出的文件带一行很小的来源署名，这是免费的服务方式，不是砍掉功能。",
  },
  {
    tier: "会员",
    price: MEMBERSHIP_PRICE_TEXT,
    items: ["不限次数下载，导出文件无署名", "模拟面试不限次数", "换工作周期内连续使用更划算"],
    note: "按月计费，到期不自动续费；退款规则见「会员与退款」。",
  },
];

const FAQ = [
  {
    q: "AI 会替我编造经历或数据吗？",
    a: "不会。系统的改写只能来自你已经确认过的内容：缺指标时它会写成「量化数据待补」并留下填写提示，而不是生成一个看起来合理的数字。所有写入档案的修改都需要你在界面上确认，未经确认的内容不会进入档案。",
  },
  {
    q: "免费的和会员有什么区别？",
    a: "功能上没有阉割：解析、优化、岗位匹配、模拟面试免费档都能用。区别只有三点：免费档每个账号可免费下载 1 次、导出文件带一行很小的来源署名、模拟面试每月 1 次。",
  },
  {
    q: "它和简历模板网站有什么不同？",
    a: "模板网站解决的是「长得像一份简历」，我们解决的是「这份简历凭什么让人愿意约面」。模板网站不需要知道你的经历，所以它无法指出「负责用户模块开发和维护」这句没有信息量，也无法追问出能填进去的结果。模板我们也有，三套，但它只是最后一步。",
  },
  {
    q: "我的简历内容安全吗？",
    a: "内容用于生成你自己的档案和报告，不公开、不售卖。你可以查阅、更正和删除其中的信息，也可以注销账号，细节写在隐私政策里。",
  },
  {
    q: "适合已经工作几年的人吗？",
    a: "产品是为有真实工作经历的人设计的：多段经历、需要按岗位取舍、要把做过的事讲出含金量。应届生找第一份实习也能用，但题库和岗位匹配主要面向有工作经验的知识工作者。",
  },
  {
    q: "外包经历、跳槽频繁、有空窗期会被怎么看？",
    a: "这三条在国内投递里确实会被额外审视，而问题通常不在经历本身，在于没有解释。外包经历要写清项目价值和职责边界，而不是放大公司标签；频繁跳槽要用一句话交代选择逻辑；空窗期简短说明即可，不必长篇自辩。系统会在诊断时把这类风险单独列出来。",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-2">
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(FAQ)) }}
      />

      <PageHeader
        eyebrow={`${PRODUCT_NAME} · ${PRODUCT_NAME_EN}`}
        title="把简历改成这个岗位愿意约面的版本"
        description="上传简历，AI 找出会让它被刷掉的问题，按目标岗位重新组织表达，再陪你面一遍。不是套模板，是把你做过的事讲清楚。"
        actions={
          <TrackLink
            href="/resume-agent"
            event={ANALYTICS_EVENT.HOME_START}
            className="btn btn-md btn-primary shrink-0"
          >
            上传简历开始
          </TrackLink>
        }
      />

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">怎么用</h2>
        <ol className="space-y-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                {i + 1}
              </span>
              <div className="min-w-0 space-y-0.5">
                <p className="text-sm font-medium text-ink-800">{step.title}</p>
                <p className="text-sm leading-relaxed text-ink-600">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-ink-900">里面有什么</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {CAPABILITIES.map((c) => (
            <div key={c.name} className="card flex flex-col gap-2 px-5 py-4">
              <h3 className="text-sm font-medium text-ink-800">{c.name}</h3>
              <p className="flex-1 text-sm leading-relaxed text-ink-600">{c.body}</p>
              <Link href={c.href} className="text-sm font-medium text-brand-700 hover:underline">
                {c.linkText} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-ink-900">简历指南</h2>
        <p className="text-sm leading-relaxed text-ink-600">
          工具之外，把这些年看得最多的几类问题写成了可以直接照着改的条目。不用注册。
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {GUIDES.map((guide) => (
            <Link
              key={guide.slug}
              href={`/guides/${guide.slug}`}
              className="card flex flex-col gap-1.5 px-5 py-4 transition hover:border-brand-300"
            >
              <h3 className="text-sm font-medium text-ink-800">{guide.title}</h3>
              <p className="flex-1 text-sm leading-relaxed text-ink-600">{guide.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">价格</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {PRICING.map((p) => (
            <div key={p.tier} className="space-y-2 rounded-lg border border-surface-border p-4">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-semibold text-ink-900">{p.tier}</p>
                <p className="text-sm font-semibold text-brand-700">{p.price}</p>
              </div>
              <ul className="space-y-1">
                {p.items.map((item) => (
                  <li key={item} className="text-sm leading-relaxed text-ink-600">
                    {item}
                  </li>
                ))}
              </ul>
              <p className="pt-1 text-xs leading-relaxed text-ink-500">{p.note}</p>
            </div>
          ))}
        </div>
        <p className="text-xs leading-relaxed text-ink-500">
          不用先付费再决定要不要用：解析和优化是免费功能，先看看它对这份简历能做什么。
        </p>
      </section>

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">常见问题</h2>
        <dl className="space-y-3">
          {FAQ.map((item) => (
            <div key={item.q} className="space-y-0.5">
              <dt className="text-sm font-medium text-ink-800">{item.q}</dt>
              <dd className="text-sm leading-relaxed text-ink-600">{item.a}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-800">从一份简历开始</p>
          <p className="text-sm leading-relaxed text-ink-600">{DOCUMENT_DESCRIPTION}</p>
        </div>
        <TrackLink
          href="/resume-agent"
          event={ANALYTICS_EVENT.HOME_START}
          className="btn btn-md btn-primary shrink-0"
        >
          上传简历开始
        </TrackLink>
      </section>
    </div>
  );
}
