import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import {
  ABOUT_COMPANY_INTRO,
  ABOUT_COMPANY_NAME,
  ABOUT_CONTACT_EMAIL,
  ABOUT_CONTACT_EXTRA,
  DOCUMENT_DESCRIPTION,
  PRODUCT_NAME,
  PRODUCT_NAME_EN,
  PRODUCT_TAGLINE,
} from "@/lib/brand";

export const metadata: Metadata = {
  title: "关于",
  description: DOCUMENT_DESCRIPTION,
};

export default function AboutPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-2">
      <PageHeader
        eyebrow="关于"
        title={`${PRODUCT_NAME} · ${PRODUCT_NAME_EN}`}
        description={PRODUCT_TAGLINE}
      />

      <section className="card space-y-2 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">产品介绍</h2>
        <p className="text-sm leading-relaxed text-ink-600">{DOCUMENT_DESCRIPTION}</p>
      </section>

      <section className="card space-y-2 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">公司介绍</h2>
        <p className="text-sm font-medium text-ink-800">{ABOUT_COMPANY_NAME}</p>
        <p className="text-sm leading-relaxed text-ink-600">{ABOUT_COMPANY_INTRO}</p>
      </section>

      <section className="card space-y-2 px-5 py-4">
        <h2 className="text-sm font-semibold text-ink-900">联系信息</h2>
        <p className="text-sm text-ink-600">
          邮箱：<span className="font-medium text-ink-800">{ABOUT_CONTACT_EMAIL}</span>
        </p>
        {ABOUT_CONTACT_EXTRA ? (
          <p className="text-sm text-ink-600">{ABOUT_CONTACT_EXTRA}</p>
        ) : null}
        <p className="pt-1 text-xs text-ink-500">
          遇到问题或有建议？去{" "}
          <Link href="/feedback" className="font-medium text-brand-700 hover:text-brand-800">
            用户反馈
          </Link>{" "}
          里告诉我们。
        </p>
      </section>
    </div>
  );
}
