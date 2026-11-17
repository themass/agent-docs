import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { ALL_GUIDES, guideBySlug, guideUrl } from "@/lib/seo/content";
import { SITE_URL, faqJsonLd, pageMetadata } from "@/lib/seo/site";

/**
 * One route for every guide. Adding an article is a `GUIDES` data edit in
 * `lib/seo/content.ts` — this file picks it up, prerenders it at build time, adds it to
 * the sitemap, and interlinks it. That is deliberate: the SEO bet here is volume of
 * genuinely useful pages, and the marginal cost of a page must be a data edit, not a
 * new route plus metadata plus JSON-LD each time.
 *
 * The whole page is server-rendered HTML on purpose. Guide readers arrive from search
 * with no brand context, and a client-rendered page hands a crawler an empty shell —
 * which is exactly how `/resume-agent` and friends read today.
 */

export function generateStaticParams() {
  return ALL_GUIDES.map((guide) => ({ slug: guide.slug }));
}

/** Unknown slugs 404 through the app shell instead of rendering an empty article. */
export const dynamicParams = false;

type Params = { params: Promise<{ slug: string }> };

function breadcrumbJsonLd(title: string, slug: string) {
  const base = `${SITE_URL}${guideUrl(slug)}`;
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "首页", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "指南", item: `${SITE_URL}/guides` },
      { "@type": "ListItem", position: 3, name: title, item: base },
    ],
  };
}

function articleJsonLd(guide: (typeof ALL_GUIDES)[number]) {
  const url = `${SITE_URL}${guideUrl(guide.slug)}`;
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    "@id": `${url}#article`,
    url,
    headline: guide.title,
    description: guide.description,
    inLanguage: "zh-CN",
    mainEntityOfPage: url,
    publisher: { "@id": `${SITE_URL}/#organization` },
  };
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const guide = guideBySlug.get(slug);
  if (!guide) return {};
  return pageMetadata({
    title: guide.title,
    description: guide.description,
    path: guideUrl(slug),
    keywords: guide.keywords,
  });
}

export default async function GuidePage({ params }: Params) {
  const { slug } = await params;
  const guide = guideBySlug.get(slug);
  if (!guide) return null;

  const related = (guide.related ?? [])
    .map((relatedSlug) => guideBySlug.get(relatedSlug))
    .filter((entry): entry is (typeof ALL_GUIDES)[number] => entry !== undefined);

  return (
    <article className="mx-auto flex max-w-2xl flex-col gap-8 py-2">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd(guide)) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd(guide.title, guide.slug)) }}
      />
      {guide.faq.length > 0 ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(guide.faq)) }}
        />
      ) : null}

      <PageHeader eyebrow="指南" title={guide.title} description={guide.lead} />

      <div className="space-y-8">
        {guide.sections.map((section) => (
          <section key={section.heading} className="card space-y-3 px-5 py-4">
            <h2 className="text-sm font-semibold text-ink-900">{section.heading}</h2>
            {(section.paragraphs ?? []).map((paragraph) => (
              <p key={paragraph.slice(0, 24)} className="text-sm leading-relaxed text-ink-600">
                {paragraph}
              </p>
            ))}
            {section.points ? (
              <ul className="space-y-1.5">
                {section.points.map((point) => (
                  <li key={point.slice(0, 24)} className="text-sm leading-relaxed text-ink-600">
                    {point}
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
      </div>

      {guide.faq.length > 0 ? (
        <section className="card space-y-3 px-5 py-4">
          <h2 className="text-sm font-semibold text-ink-900">常见问题</h2>
          <dl className="space-y-3">
            {guide.faq.map((item) => (
              <div key={item.q} className="space-y-0.5">
                <dt className="text-sm font-medium text-ink-800">{item.q}</dt>
                <dd className="text-sm leading-relaxed text-ink-600">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {related.length > 0 ? (
        <nav aria-label="相关指南" className="card space-y-2 px-5 py-4">
          <h2 className="text-sm font-semibold text-ink-900">相关指南</h2>
          <ul className="space-y-1.5">
            {related.map((entry) => (
              <li key={entry.slug}>
                <Link
                  href={guideUrl(entry.slug)}
                  className="text-sm text-brand-700 underline decoration-brand-300 underline-offset-2"
                >
                  {entry.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      <section className="card flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-800">把这份指南里的方法用在你的简历上</p>
          <p className="text-sm leading-relaxed text-ink-600">
            上传简历，助手按目标岗位逐条找出没有信息量的句子，追问到你补得出证据为止。
          </p>
        </div>
        <Link href="/resume-agent" className="btn btn-md btn-primary shrink-0">
          开始优化简历
        </Link>
      </section>
    </article>
  );
}
