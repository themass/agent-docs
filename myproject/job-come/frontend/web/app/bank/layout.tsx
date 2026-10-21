import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "面试题库",
  description: "沉淀模拟面试与真实面试中的高频问题与参考答案，按岗位与主题复习，提升临场表达。",
  path: "/bank",
  keywords: ["面试题库", "面试真题", "结构化面试", "行为面试", "求职备考"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function BankLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
