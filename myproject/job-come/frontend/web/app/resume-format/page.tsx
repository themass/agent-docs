import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { PRODUCT_NAME } from "@/lib/brand";
import {
  faqJsonLd,
  pageMetadata,
  SITE_KEYWORDS_FORMAT_EN,
  SITE_KEYWORDS_FORMAT_ZH,
} from "@/lib/seo/site";

/**
 * The site's only indexable content page for the file-format capability.
 *
 * It exists because every other route is a client-rendered workbench behind auth: a
 * crawler fetching `/resume-agent` gets metadata and an empty shell, and `/` only
 * redirects there. Keywords cannot rank a page with no body text, so this page carries
 * the body text — rendered on the server, reachable without logging in.
 *
 * Every capability claim below is checked against the backend: `document_extractor`
 * reads PDF / DOCX / TXT natively and routes images and scanned PDFs through vision,
 * and `resume_render_engine` writes PDF / DOCX / HTML from three templates. `.doc`
 * (the pre-2007 binary format) is classified but extracts to an empty string, so it is
 * listed as unsupported rather than quietly omitted.
 */
const SEO = {
  title: "简历格式转换与排版",
  description:
    "简历 PDF 转 Word、Word 转 PDF，上传后可直接改内容与调整排版，再导出 PDF 或 Word。支持 PDF、Word、图片、纯文本，三套中英文版式。",
  path: "/resume-format",
  keywords: [...SITE_KEYWORDS_FORMAT_ZH, ...SITE_KEYWORDS_FORMAT_EN, "舟卡", "JobCome"],
};

export const metadata: Metadata = pageMetadata(SEO);

const INPUT_FORMATS = [
  { ext: "PDF", note: "直接读取文字；扫描件与图片型 PDF 走 OCR 识别" },
  { ext: "Word（.docx）", note: "直接读取正文、段落与列表" },
  { ext: "图片（JPG / PNG 等）", note: "拍照或截图的简历，走 OCR 识别" },
  { ext: "纯文本（.txt）", note: "直接读取" },
];

const OUTPUT_FORMATS = [
  { ext: "PDF", note: "投递用主力格式，版式与预览完全一致" },
  { ext: "Word（.docx）", note: "可继续手改；也是 ATS 简历系统最稳的格式" },
  { ext: "HTML", note: "网页版，便于在线分享" },
];

const TEMPLATES = [
  { name: "中文单页", note: "最常见的国内投递版式，一页讲完" },
  { name: "英文两页", note: "外企与海外岗位的常规长度" },
  { name: "中英双语", note: "同一份内容两种语言，一次导出" },
];

const STEPS = [
  {
    title: "上传原文件",
    body: "PDF、Word、图片、纯文本都可以。系统把它解析成结构化档案——每段经历、每条成果各自成项，而不是一团文字。",
  },
  {
    title: "改内容、调版式",
    body: "在档案里直接改写表述，或让 AI 按目标岗位重新组织。版式从三套模板里选，字号、间距与分页由模板统一控制，不用自己对齐。",
  },
  {
    title: "导出 PDF 或 Word",
    body: "同一份档案可以反复导出不同格式和不同版式，内容只维护一份。上传 PDF 导出 Word、上传 Word 导出 PDF，都在这一步完成。",
  },
];

const FAQ = [
  {
    q: "简历 PDF 怎么转成 Word？",
    a: "上传 PDF 简历，系统解析出内容后，在导出时选择 Word（.docx）即可下载。中间可以先修改内容和版式，不是只能原样转换。",
  },
  {
    q: "Word 简历怎么转成 PDF？",
    a: "上传 .docx 文件，导出时选择 PDF。导出的 PDF 与网页预览完全一致，不会出现本地 Word 转出来字体跑版的情况。",
  },
  {
    q: "转换后会保留原来的版式吗？",
    a: "不会，这一点和纯转换工具不同。我们把内容重新排进统一模板，所以原文件的字体、颜色、分栏不会带过来，换来的是排版一致、分页干净。如果你需要的是逐像素还原原版式，专门的 PDF 转换工具更合适。",
  },
  {
    q: "可以直接编辑 PDF 简历吗？",
    a: "不是在 PDF 上直接涂改，而是把 PDF 解析成可编辑的结构化档案，你改完档案再导出新的 PDF。对简历这种需要反复改措辞的文件，这种方式比在 PDF 里抠字更好用。",
  },
  {
    q: "简历格式乱了怎么调整？",
    a: "换模板即可。字号、行距、页边距、分页位置都由模板统一控制，不需要逐段手动对齐。目前有中文单页、英文两页、中英双语三套。",
  },
  {
    q: "支持 .doc 格式吗？",
    a: "暂不支持 .doc（Word 2003 及更早的二进制格式）。用 Word 另存为 .docx 后上传即可，或者直接导出成 PDF 再上传。",
  },
];

export default function ResumeFormatPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-2">
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(FAQ)) }}
      />

      <PageHeader
        eyebrow="格式转换"
        title="简历格式转换与排版"
        description={`简历 PDF 转 Word、Word 转 PDF，中间还能改内容、换版式。${PRODUCT_NAME}把简历当成一份可编辑的档案，而不是一个只能原样搬运的文件。`}
      />

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">支持的格式</h2>
        <div className="space-y-3">
          <div>
            <p className="label-meta mb-1.5">可以上传</p>
            <ul className="space-y-1">
              {INPUT_FORMATS.map((f) => (
                <li key={f.ext} className="text-sm leading-relaxed text-ink-600">
                  <span className="font-medium text-ink-800">{f.ext}</span>
                  <span className="text-ink-500">　·　{f.note}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="label-meta mb-1.5">可以导出</p>
            <ul className="space-y-1">
              {OUTPUT_FORMATS.map((f) => (
                <li key={f.ext} className="text-sm leading-relaxed text-ink-600">
                  <span className="font-medium text-ink-800">{f.ext}</span>
                  <span className="text-ink-500">　·　{f.note}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="pt-1 text-xs leading-relaxed text-ink-500">
          所以「PDF 转 Word」「Word 转 PDF」「图片简历转 Word」这些组合都成立——
          上传什么格式和导出什么格式是两件独立的事。
        </p>
      </section>

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">三步完成</h2>
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

      <section className="card space-y-3 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">可选版式</h2>
        <ul className="space-y-1.5">
          {TEMPLATES.map((t) => (
            <li key={t.name} className="text-sm leading-relaxed text-ink-600">
              <span className="font-medium text-ink-800">{t.name}</span>
              <span className="text-ink-500">　·　{t.note}</span>
            </li>
          ))}
        </ul>
        <p className="pt-1 text-xs leading-relaxed text-ink-500">
          换模板不会改动内容，内容只维护一份；同一份档案可以反复导出不同版式。
        </p>
      </section>

      <section className="card space-y-2 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">和纯转换工具的区别</h2>
        <p className="text-sm leading-relaxed text-ink-600">
          纯转换工具的目标是还原——把 PDF 的每一个字、每一条线原样搬进 Word。
          文件格式变了，内容和排版一个字不动。
        </p>
        <p className="text-sm leading-relaxed text-ink-600">
          我们的目标是这份简历投出去能用。上传后内容会被拆成结构化档案，
          你可以改写表述、按目标岗位重新组织，再用统一模板重新排版。
          代价是原文件的字体、分栏不会带过来；换来的是版式一致、分页干净、随时能改。
        </p>
        <p className="text-sm leading-relaxed text-ink-600">
          <span className="font-medium text-ink-800">怎么选：</span>
          只想换个文件格式、版式一个像素都不能动，用专门的转换工具；
          想顺手把简历改好再换格式，用这里。
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
          <p className="text-sm font-medium text-ink-800">上传一份简历试试</p>
          <p className="text-sm leading-relaxed text-ink-600">
            PDF、Word、图片都可以，解析完就能改、能换版式、能导出。
          </p>
        </div>
        <Link href="/resume-agent" className="btn btn-md btn-primary shrink-0">
          开始优化简历
        </Link>
      </section>
    </div>
  );
}
