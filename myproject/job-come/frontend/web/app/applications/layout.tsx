import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "投递看板",
  description: "用看板管理求职机会与投递状态，记录跟进日期，避免漏投、重复投或遗忘回访。",
  path: "/applications",
  keywords: ["求职看板", "投递管理", "机会漏斗", "求职跟进", "跳槽"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function ApplicationsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
