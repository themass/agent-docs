import type { Metadata } from "next";

import {
  DOCUMENT_DESCRIPTION,
  DOCUMENT_TITLE,
  PRODUCT_NAME,
  PRODUCT_NAME_EN,
  ZHOUKA_NAME,
} from "@/lib/brand";

/** Canonical site origin — set in production (e.g. https://www.jobcome.com). */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ?? "http://localhost:3000";

/** Primary keywords (zh-CN). Baidu still weighs `keywords`; Google largely ignores them. */
export const SITE_KEYWORDS_ZH = [
  "舟卡",
  "JobCome",
  "简历优化",
  "AI简历",
  "简历解析",
  // Two format terms earn a site-wide slot because they are resume-scoped and the home
  // page is where the capability is first claimed; the rest of the format vocabulary
  // lives in `SITE_KEYWORDS_FORMAT_ZH`, on the one page that performs the conversion.
  "简历排版",
  "简历格式转换",
  "求职",
  "跳槽",
  "模拟面试",
  "面试辅导",
  "岗位匹配",
  "JD匹配",
  "职业规划",
  "知识工作者",
] as const;

export const SITE_KEYWORDS_EN = [
  "JobCome",
  "resume optimizer",
  "AI resume",
  "mock interview",
  "job search",
  "career coach",
] as const;

/**
 * Document-format intent — only for pages that actually convert or re-typeset a file.
 *
 * The capability is real: `document_extractor` reads PDF / DOCX / DOC / TXT / image and
 * `resume_render_engine` writes PDF / DOCX / HTML, so "upload a PDF, download a Word" is
 * a thing this product does. What it does *not* do is layout-faithful conversion — the
 * content is re-typeset into one of our templates. So the bare tool terms sit here
 * alongside the resume-scoped long tail, and the long tail is the half with a real
 * chance: someone searching `简历pdf转word` wants a cleaner layout, which is what they
 * get, while someone searching `pdf转word` wants their original page back and bounces.
 *
 * Kept out of `SITE_KEYWORDS_ZH` on purpose: the site-wide list reaches every route, and
 * the interview-bank and application-tracker pages have nothing to do with file formats.
 */
export const SITE_KEYWORDS_FORMAT_ZH = [
  "pdf转换word",
  "pdf转word",
  "word转换pdf",
  "word转pdf",
  "pdf编辑",
  "pdf格式调整",
  "word格式调整",
  "简历pdf转word",
  "简历word转pdf",
  "简历格式转换",
  "简历格式调整",
  "简历排版",
  "简历导出word",
  "简历导出pdf",
  "简历模板",
] as const;

export const SITE_KEYWORDS_FORMAT_EN = [
  "resume pdf to word",
  "resume word to pdf",
  "resume formatting",
  "resume template",
] as const;

/** Indexable product pages (no auth / settings / admin). */
export const PUBLIC_SITEMAP_PATHS = [
  // `/resume-format` outranks the product routes here because it is the only entry with
  // server-rendered body text: the rest are client workbenches that a crawler sees as an
  // empty shell, and a page with no content cannot rank however high we rate it.
  { path: "/resume-format", priority: 1.0, changeFrequency: "monthly" as const },
  { path: "/resume-agent", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/jobs", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/coach-agent", priority: 0.85, changeFrequency: "weekly" as const },
  { path: "/apply-agent", priority: 0.8, changeFrequency: "monthly" as const },
  { path: "/about", priority: 0.75, changeFrequency: "yearly" as const },
  { path: "/campaign", priority: 0.75, changeFrequency: "monthly" as const },
  { path: "/bank", priority: 0.7, changeFrequency: "monthly" as const },
  { path: "/applications", priority: 0.65, changeFrequency: "monthly" as const },
  { path: "/interviews", priority: 0.65, changeFrequency: "monthly" as const },
] as const;

const NOINDEX_PREFIXES = ["/auth/", "/settings/", "/admin/", "/mock"] as const;

export function shouldNoIndexPath(pathname: string): boolean {
  return NOINDEX_PREFIXES.some((p) => pathname.startsWith(p));
}

export type PageSeoInput = {
  title: string;
  description: string;
  path: string;
  keywords?: string[];
  noIndex?: boolean;
};

export function pageMetadata(input: PageSeoInput): Metadata {
  const url = `${SITE_URL}${input.path}`;
  const keywords = input.keywords ?? [...SITE_KEYWORDS_ZH, ...SITE_KEYWORDS_EN];
  return {
    title: input.title,
    description: input.description,
    keywords: [...keywords],
    alternates: { canonical: url },
    robots: input.noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
    openGraph: {
      title: `${input.title} · ${PRODUCT_NAME}`,
      description: input.description,
      url,
      siteName: PRODUCT_NAME_EN,
      locale: "zh_CN",
      type: "website",
    },
  };
}

export function webPageJsonLd(path: string, name: string, description: string) {  const url = `${SITE_URL}${path}`;
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    url,
    name,
    description,
    inLanguage: "zh-CN",
    isPartOf: { "@id": `${SITE_URL}/#website` },
  };
}

/**
 * FAQ structured data — the one schema type that still earns an expanded search result.
 *
 * Worth the markup only when the questions are phrased the way people actually search
 * (`简历 PDF 怎么转成 Word？`), because the question string is what gets matched. Answers
 * must also exist as visible text on the page: markup that is not in the body is a
 * structured-data violation, not a shortcut.
 */
export function faqJsonLd(items: ReadonlyArray<{ q: string; a: string }>) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}

export function rootJsonLd() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        url: SITE_URL,
        name: DOCUMENT_TITLE,
        description: DOCUMENT_DESCRIPTION,
        inLanguage: "zh-CN",
        publisher: { "@id": `${SITE_URL}/#organization` },
      },
      {
        "@type": "Organization",
        "@id": `${SITE_URL}/#organization`,
        name: PRODUCT_NAME,
        alternateName: [PRODUCT_NAME_EN, ZHOUKA_NAME],
        url: SITE_URL,
        description: DOCUMENT_DESCRIPTION,
      },
      {
        "@type": "SoftwareApplication",
        name: PRODUCT_NAME,
        alternateName: PRODUCT_NAME_EN,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        offers: { "@type": "Offer", price: "0", priceCurrency: "CNY" },
        description: DOCUMENT_DESCRIPTION,
        // Structured data is read where `keywords` is not, so the file-format capability
        // is stated as a feature rather than left to the meta tag. Each line matches
        // something the backend actually does — the reader list in `document_extractor`
        // and the writer list in `resume_render_engine`.
        featureList: [
          "上传 PDF / Word / 图片简历并解析为结构化档案",
          "AI 改写简历表述，按岗位重新组织内容",
          "调整简历排版格式，一键导出 PDF 或 Word",
          "简历 PDF 转 Word、Word 转 PDF 格式转换",
          "岗位 JD 匹配与模拟面试",
        ],
        inLanguage: ["zh-CN", "en-US"],
      },
    ],
  };
}
