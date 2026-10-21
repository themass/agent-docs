import type { Metadata } from "next";

import { PageJsonLd } from "@/components/seo/PageJsonLd";
import { pageMetadata } from "@/lib/seo/site";

const SEO = {
  title: "跳槽战役看板",
  description: "管理本轮求职节奏：练手岗、主攻岗与跟进节点，让跳槽过程可追踪、可复盘。",
  path: "/campaign",
  keywords: ["跳槽计划", "求职看板", "求职节奏", "职业规划", "舟卡"],
};

export const metadata: Metadata = pageMetadata(SEO);

export default function CampaignLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageJsonLd path={SEO.path} name={SEO.title} description={SEO.description} />
      {children}
    </>
  );
}
