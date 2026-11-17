import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { GUIDES } from "@/lib/seo/content";
import { pageMetadata } from "@/lib/seo/site";

/**
 * Table of contents for `/guides/*`.
 *
 * It exists mainly so the guide pages are not orphans: a page nothing links to is a
 * page the crawler has to guess at, and search engines follow links rather than
 * scanning directories. Every guide links back here and to its related guides, so the
 * cluster interlinks without any page depending on the footer.
 */

const SEO = {
  title: "简历优化指南：诊断、改写、面试准备",
  description:
    "针对具体问题的简历写作与面试准备指南：为什么简历总被刷掉、没有数字怎么量化改写、外包经历与空窗期怎么写、模拟面试怎么准备。",
  path: "/guides",
  keywords: ["简历指南", "简历怎么写", "简历优化方法", "面试准备"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function GuidesIndexPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-2">
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />

      <PageHeader
        eyebrow="指南"
        title="简历优化指南"
        description="不讲泛泛的求职鸡汤，只写能直接照着改的具体问题：每一条都对应筛选时真实存在的判断标准。"
      />

      <nav aria-label="指南列表" className="space-y-3">
        {GUIDES.map((guide) => (
          <Link
            key={guide.slug}
            href={`/guides/${guide.slug}`}
            className="card block px-5 py-4 transition hover:border-brand-300"
          >
            <h2 className="text-sm font-semibold text-ink-900">{guide.title}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-600">{guide.description}</p>
          </Link>
        ))}
      </nav>

      <section className="card flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-800">想让工具按岗位逐条审计你的简历？</p>
          <p className="text-sm leading-relaxed text-ink-600">
            上传简历后，助手会指出具体哪一句没有信息量，并追问到你补得出证据为止。
          </p>
        </div>
        <Link href="/resume-agent" className="btn btn-md btn-primary shrink-0">
          开始优化简历
        </Link>
      </section>
    </div>
  );
}
