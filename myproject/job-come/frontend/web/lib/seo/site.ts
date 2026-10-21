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

/** Indexable product pages (no auth / settings / admin). */
export const PUBLIC_SITEMAP_PATHS = [
  { path: "/resume-agent", priority: 1.0, changeFrequency: "weekly" as const },
  { path: "/jobs", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/coach-agent", priority: 0.85, changeFrequency: "weekly" as const },
  { path: "/apply-agent", priority: 0.8, changeFrequency: "monthly" as const },
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

export function webPageJsonLd(path: string, name: string, description: string) {
  const url = `${SITE_URL}${path}`;
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
        inLanguage: ["zh-CN", "en-US"],
      },
    ],
  };
}
