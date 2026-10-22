import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata, SITE_KEYWORDS_FORMAT_EN, SITE_KEYWORDS_FORMAT_ZH } from "@/lib/seo/site";

const SEO = {
  title: "简历优化",
  // The format vocabulary is spelled out here rather than only in `keywords`: Google has
  // ignored the keywords meta since 2009, so the description and the page body are the
  // only parts of this file that can actually rank for 简历 PDF 转 Word.
  description:
    "上传 PDF / Word / 图片简历，AI 解析为可编辑档案；改稿、重排版式，一键导出 PDF 或 Word。支持简历 PDF 转 Word、Word 转 PDF 与格式调整。",
  path: "/resume-agent",
  keywords: [
    "简历优化",
    "AI改简历",
    "简历导出",
    "简历解析",
    "求职简历",
    "舟卡",
    "JobCome",
    ...SITE_KEYWORDS_FORMAT_ZH,
    ...SITE_KEYWORDS_FORMAT_EN,
  ],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function ResumeAgentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="jc-workbench-page flex min-h-0 flex-1 flex-col">
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </div>
  );
}
