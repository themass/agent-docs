import type { ReactNode } from "react";

/**
 * Empty states used to be a bare grey sentence, which reads as a dead end.
 * This gives them a surface, an icon slot and room for the next action, so an
 * empty page still tells the user what to do.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  compact = false,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={`card-sunken bg-sheen flex flex-col items-center justify-center text-center ${
        compact ? "px-5 py-8" : "px-6 py-14"
      }`}
    >
      {icon ? (
        <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-surface text-ink-400 shadow-xs ring-1 ring-inset ring-surface-border">
          {icon}
        </span>
      ) : null}
      <p className="text-sm font-medium text-ink-800">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-500">{description}</p>
      ) : null}
      {action ? <div className="mt-4 flex items-center gap-2">{action}</div> : null}
    </div>
  );
}
