import type { ReactNode } from "react";

import { LEGAL_DRAFT, LEGAL_UPDATED } from "@/lib/legal";

export type LegalSection = {
  title: string;
  paragraphs: ReactNode[];
};

/** One layout for every legal page, so they share heading rhythm and the draft notice. */
export function LegalDocument({
  title,
  intro,
  sections,
}: {
  title: string;
  intro?: ReactNode;
  sections: LegalSection[];
}) {
  return (
    <article className="mx-auto min-h-0 w-full max-w-4xl flex-1 overflow-y-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
        <p className="mt-1.5 text-xs text-ink-500">最后更新：{LEGAL_UPDATED}</p>
        {LEGAL_DRAFT ? (
          <p className="notice notice-warn mt-4 text-xs leading-relaxed" role="note">
            这是草稿，尚未经过法律审阅；标有“待确认”的条款还没有定稿，正式启用前不具备约束力。
          </p>
        ) : null}
        {intro ? <div className="mt-4 text-sm leading-relaxed text-ink-600">{intro}</div> : null}
      </header>
      <div className="space-y-6">
        {sections.map((section) => (
          <section key={section.title}>
            <h2 className="text-base font-semibold text-ink-900">{section.title}</h2>
            <div className="mt-2 space-y-2 text-sm leading-relaxed text-ink-700">
              {section.paragraphs.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}
