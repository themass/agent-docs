import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "模拟面试",
  description: "与舟卡进行模拟面试练习，积累题库、复盘表现，提升面试表达与答题结构。",
  path: "/coach-agent",
  keywords: ["模拟面试", "面试题库", "面试辅导", "AI面试", "求职面试", "行为面试"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function CoachAgentLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
