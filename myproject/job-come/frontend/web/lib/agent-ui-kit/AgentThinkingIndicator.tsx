"use client";

import { cn } from "./cn";
import { defaultAgentUiKitClassNames } from "./defaultClassNames";
import type { AgentThinkingIndicatorProps } from "./types";

function ThinkingDots({ className }: { className?: string }) {
  // `think-dot` (tailwind.config.ts) throws each dot up ~5px — stock
  // `animate-bounce` scales its motion off the element's own box, which at
  // dot size (3-4px) produces a sub-pixel wobble nobody can actually see.
  return (
    <span className={cn(className, "inline-flex items-end gap-[3px]")} aria-hidden>
      <span className="size-[5px] animate-think-dot rounded-full bg-current [animation-delay:0ms]" />
      <span className="size-[5px] animate-think-dot rounded-full bg-current [animation-delay:150ms]" />
      <span className="size-[5px] animate-think-dot rounded-full bg-current [animation-delay:300ms]" />
    </span>
  );
}

/**
 * Agent “working” status: static label + animated trailing dots.
 * Decoupled from product name — pass `label` from the host app.
 */
export function AgentThinkingIndicator({
  label,
  variant = "pill",
  avatar,
  className = "",
  classNames,
}: AgentThinkingIndicatorProps) {
  const styles = { ...defaultAgentUiKitClassNames, ...classNames };

  const text = (
    <span className="inline-flex items-baseline gap-0.5">
      <span>{label}</span>
      <ThinkingDots className={styles.thinkingDots} />
    </span>
  );

  if (variant === "inline") {
    return (
      <span
        className={cn(styles.thinkingInline, className)}
        role="status"
        aria-live="polite"
      >
        {avatar}
        {text}
      </span>
    );
  }

  return (
    <div
      className={cn(styles.thinkingPill, className)}
      role="status"
      aria-live="polite"
    >
      {avatar}
      {text}
    </div>
  );
}
