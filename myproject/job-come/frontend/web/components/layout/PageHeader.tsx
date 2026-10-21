import type { ReactNode } from "react";

/**
 * Every top-level page previously hand-rolled `h1 + p`, each with slightly
 * different sizes and spacing. One component keeps the page-entry rhythm
 * identical across the app, which is most of what makes a tool read as
 * designed rather than assembled.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
}: {
  title: string;
  description?: ReactNode;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 max-w-prose">
        {eyebrow ? <p className="label-meta mb-1.5">{eyebrow}</p> : null}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {description ? (
          <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
