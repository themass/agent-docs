import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { PRODUCT_NAME } from "@/lib/brand";
import {
  SITE_KEYWORDS_FORMAT_ZH,
  faqJsonLd,
  pageMetadata,
} from "@/lib/seo/site";

/**
 * The page that answers 「简历模板」.
 *
 * High volume, high intent, and until now unanswered — the product has had three real
 * templates all along and only ever described them in a sentence. This page shows them.
 *
 * The images are **renders of the product's own templates**, produced by
 * `scripts/render-template-previews.py` through `ResumeRenderEngine.render_html` — the
 * same code path that produces an exported PDF. That is deliberate: a hand-drawn mockup
 * would be a picture of a template we do not have, and the first export would not match
 * it. Re-run the script and commit when a template's layout changes.
 *
 * What this page must not claim: that the templates are free of the paywall. The free
 * tier is a real download allowance, stated honestly below, not "永久免费无水印".
 */

const SEO = {
  title: "简历模板：三套中文/英文版式与适用场景",
  description:
    "三套简历模板的实际渲染效果：中文单页、英文两页、中英双语。每套说明适用场景与分页规则，内容与版式分离，换模板不动内容，导出 PDF 或 Word。",
  path: "/resume-template",
  keywords: [...SITE_KEYWORDS_FORMAT_ZH],
};

export const metadata: Metadata = pageMetadata(SEO);

const TEMPLATES = [
  {
    id: "zh-one-page",
    name: "中文单页",
    scene: "国内投递的默认选择。一到两段完整经历加一段项目，一页讲完。",
    detail:
      "字号与行距按「一页内放下一段完整的项目叙事」定，而不是按页码硬压。内容超过一页时它会如实分成两页——把字缩小到看不清去凑一页，比多一页更伤。",
    best: "互联网、国企、事业单位的社招与校招",
  },
  {
    id: "en-two-page",
    name: "英文两页",
    scene: "外企、海外岗位与大厂英文轨。两页是这些渠道的常规长度。",
    detail:
      "行动词开头、过去式与现在时按时态规则处理，日期用英文月份缩写。版面按英文的长度重新计算，不是把中文内容直接翻译进中文版式。",
    best: "外企、海外投递、英文面试流程",
  },
  {
    id: "zh-en-bilingual",
    name: "中英双语",
    scene: "同一份内容两种语言，一次导出两份可分别投递的简历。",
    detail:
      "两个语言轨共用一份档案：改中文不会让英文停在旧版本。导出时按语言分段，中文在前英文在后，中间分页。",
    best: "既投国内又投外企、需要两种语言同时就绪",
  },
] as const;

const FAQ = [
  {
    q: "简历模板是免费的吗？",
    a: `注册后可以完整使用解析和优化功能，每个账号有 1 次免费下载；之后的导出需要会员（25 元 / 30 天）。免费下载的文件带一行来源水印。模板本身不是付费项，限制在下载次数上。`,
  },
  {
    q: "换模板会改我的内容吗？",
    a: "不会。内容只维护一份，版式是独立的一层：字号、行距、页边距、分页位置由模板统一控制，换模板只改变排版，不改一个字。所以你可以在同一份内容上反复试三套版式，挑最合适的再导出。",
  },
  {
    q: "模板能导出成 Word 吗？",
    a: "可以。三套版式都支持 PDF、Word（.docx）和 HTML 三种导出。Word 版本按同一套分页规则生成，改完还能在 Word 里继续编辑再投递。",
  },
  {
    q: "为什么不做几十套模板？",
    a: "模板多了选择成本反而更高，而筛选者看的是内容不是版式。三套覆盖了国内投递、海外投递和双语三种场景；真正拉开差距的是经历怎么写，那一步在内容优化里，不在模板里。",
  },
  {
    q: "上传的简历会套用这些模板吗？",
    a: "会，但会先解析成结构化档案。也就是说原文件的字体、颜色、分栏不会带过来，内容会重新排进你选的模板。如果你需要逐像素还原原版式，专门的 PDF 转换工具更合适。",
  },
] as const;

export default function ResumeTemplatePage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 py-2">
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(FAQ)) }}
      />

      <PageHeader
        eyebrow="模板"
        title="三套简历模板，以及各自适合什么岗位"
        description={`下面是 ${PRODUCT_NAME} 现有的三套版式，图片是用产品真实的渲染引擎生成的——不是你看到的示意图，是导出 PDF 时的同一段代码。`}
      />

      <section className="space-y-6">
        {TEMPLATES.map((template, index) => (
          <article key={template.id} className="card overflow-hidden">
            <div className="border-b border-surface-border bg-surface-muted px-4 py-2.5">
              <h2 className="text-sm font-semibold text-ink-900">{template.name}</h2>
              <p className="mt-0.5 text-xs text-ink-600">适合：{template.best}</p>
            </div>
            <div className="grid gap-4 p-4 sm:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
              <Image
                src={`/templates/${template.id}.png`}
                alt={`${template.name}简历模板的实际渲染效果`}
                width={794}
                height={1123}
                className="w-full rounded border border-surface-border"
                sizes="(max-width: 640px) 100vw, 240px"
                // The first template is the LCP element on this page, and Next's default
                // `lazy` deferred it until after layout — measured LCP 3.4s. Priority on
                // that one image only; the other two are genuinely below the fold and
                // stay lazy so they do not compete with it for bandwidth.
                priority={index === 0}
              />
              <div className="space-y-2">
                <p className="text-sm leading-relaxed text-ink-700">{template.scene}</p>
                <p className="text-sm leading-relaxed text-ink-600">{template.detail}</p>
              </div>
            </div>
          </article>
        ))}
      </section>

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">如何选</h2>
        <ul className="space-y-1.5">
          <li className="text-sm leading-relaxed text-ink-600">
            <span className="font-medium text-ink-800">只投国内：</span>
            用中文单页。大多数国内筛选者默认一页，超过一页的部分经常不被看到。
          </li>
          <li className="text-sm leading-relaxed text-ink-600">
            <span className="font-medium text-ink-800">有海外或外企目标：</span>
            英文两页，并单独检查英文版里的行动词和时态，不要直接把中文翻译过去。
          </li>
          <li className="text-sm leading-relaxed text-ink-600">
            <span className="font-medium text-ink-800">两边都投：</span>
            中英双语。好处是两种语言共用一份档案，不会改了一边忘了另一边。
          </li>
        </ul>
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
          <p className="text-sm font-medium text-ink-800">选好版式，内容才是关键</p>
          <p className="text-sm leading-relaxed text-ink-600">
            模板解决「看起来专业」，解不了「经历没写清楚」。上传一份简历，先看看内容上缺什么。
          </p>
        </div>
        <Link href="/resume-agent" className="btn btn-md btn-primary shrink-0">
          开始优化简历
        </Link>
      </section>
    </div>
  );
}
