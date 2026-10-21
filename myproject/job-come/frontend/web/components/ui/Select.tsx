import type { SelectHTMLAttributes } from "react";

/**
 * Every `<select>` in the app used to be a bare `<select className="field">`:
 * the browser's own dropdown arrow sits inside the same box as the text but
 * is drawn by the OS/browser, not by this design system, so it never matches
 * `.field`'s border radius, focus ring, or icon weight — on macOS Chrome it
 * renders as a visibly separate, slightly-misaligned mini-box glued to the
 * right edge. Native selects also cannot have their *control* width set
 * independently of their *text* width without extra markup, so every call
 * site that wanted a narrower select (`AgentSessionPicker`, the admin LLM
 * filter) ended up fighting `.field`'s `w-full` with ad-hoc `max-w-full`/
 * `w-auto` overrides instead of just sizing the wrapper.
 *
 * This wraps the native `<select>` (full native keyboard nav, screen reader
 * behavior, and OS-native option list — not reimplemented) in a positioned
 * wrapper that draws one consistent chevron on top, and hides the browser's
 * own arrow via `appearance-none`. Sizing now works the ordinary way: put a
 * width/max-width class on `className` (applies to the wrapper), not on the
 * `<select>` itself.
 *
 * Right padding for the chevron is an inline style, not a Tailwind class:
 * two `pr-*` utility classes (the base one here and a caller's override in
 * `selectClassName`) land in the same Tailwind-generated stylesheet with no
 * source-order guarantee between them, so a caller override could silently
 * lose to this component's default depending on build output order. A
 * `style` prop always wins over any class, so compact variants (`h-7` chips
 * like `AgentReplyLocaleSelect`) can shrink everything else through
 * `selectClassName` without the chevron gutter fighting them.
 */
export function Select({
  className = "",
  selectClassName = "",
  style,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  /** Extra classes on the wrapper (width, margin) — this is what sizes the control. */
  className?: string;
  /** Extra classes on the native `<select>` itself (rarely needed). */
  selectClassName?: string;
}) {
  return (
    <span className={`relative inline-block ${className}`}>
      <select
        {...props}
        style={{ paddingRight: "1.75rem", ...style }}
        className={`field w-full appearance-none bg-none ${selectClassName}`}
      />
      <svg
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </span>
  );
}
