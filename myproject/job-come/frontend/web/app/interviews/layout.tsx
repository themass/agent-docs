import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "面试归档",
  description: "记录真实面试过程与复盘要点，关联题库与档案，持续改进答题结构与案例表达。",
  path: "/interviews",
  keywords: ["面试复盘", "面试记录", "求职复盘", "模拟面试", "面试辅导"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function InterviewsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
