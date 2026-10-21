import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "岗位匹配",
  description: "粘贴职位描述或链接，解析 JD 并评估与档案的匹配度，为定向申请与简历拔高提供依据。",
  path: "/jobs",
  keywords: ["JD匹配", "岗位分析", "求职匹配", "职位描述", "简历定向", "跳槽"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
