import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "简历优化",
  description:
    "上传简历，AI 解析为可编辑档案；舟卡协助改稿、拔高表述、导出 PDF/Word。面向互联网与知识工作者的求职准备工具。",
  path: "/resume-agent",
  keywords: [
    "简历优化",
    "AI改简历",
    "简历导出",
    "简历解析",
    "求职简历",
    "舟卡",
    "JobCome",
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
