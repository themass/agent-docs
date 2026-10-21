import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "定向申请",
  description:
    "按目标岗位整理 JD、匹配档案并生成定向申请材料，舟卡协助润色求职信与要点，提高投递针对性。",
  path: "/apply-agent",
  keywords: ["定向申请", "求职信", "岗位申请", "简历定向", "JD", "舟卡"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function ApplyAgentLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
