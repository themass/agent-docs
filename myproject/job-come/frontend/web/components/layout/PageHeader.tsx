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
    // On a phone the page's content is the point, so the header keeps to a title and two lines
    // of description. The eyebrow and the full description come back from sm up.
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div className="min-w-0 max-w-prose">
        {eyebrow ? <p className="label-meta mb-1.5 hidden sm:block">{eyebrow}</p> : null}
        <h1 className="text-xl font-semibold tracking-tight text-ink-900 sm:text-2xl">{title}</h1>
        {description ? (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-600 sm:mt-1.5 sm:line-clamp-none sm:text-sm">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
