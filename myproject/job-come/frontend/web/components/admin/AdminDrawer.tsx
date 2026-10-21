"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

const DEFAULT_WIDTH = 512; // 32rem, same as the old `w-[min(32rem,92vw)]` default.
const MIN_WIDTH = 360;
const MAX_VIEWPORT_RATIO = 0.92; // same ceiling the old Tailwind class enforced.
const STORAGE_KEY = "jc_admin_drawer_width";

function clampWidth(width: number): number {
  const max = typeof window === "undefined" ? width : window.innerWidth * MAX_VIEWPORT_RATIO;
  return Math.min(max, Math.max(MIN_WIDTH, width));
}

/**
 * Shared right-side drawer shell for the admin surface — same overlay +
 * slide-in panel pattern as `AgentHistoryDrawer`, so admin and product UI
 * don't grow two different drawer idioms.
 *
 * Width is user-resizable (drag the left edge) and persisted across every
 * admin drawer instance (users / sessions / llm / feedback all render this
 * same component), because an operator reading a long trace payload or a
 * resume diff needs more room than the 512px default gives on a wide
 * monitor, and re-dragging it open on every page is the kind of friction
 * that should only happen once.
 */
export function AdminDrawer({
  open,
  title,
  subtitle,
  onClose,
  children,
  defaultWidth = DEFAULT_WIDTH,
  layer = 0,
}: {
  open: boolean;
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  defaultWidth?: number;
  /**
   * Stacking level for a drawer opened *from inside* another drawer (the user
   * directory opens a profile this way). Without it both drawers carry the same
   * z-index and the inner one only lands on top because it happens to come later
   * in the DOM — which silently breaks the moment someone reorders the JSX or
   * renders the inner drawer through a portal. `1` is "one above the base
   * drawer".
   */
  layer?: number;
}) {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);

  useEffect(() => {
    try {
      const saved = Number(localStorage.getItem(STORAGE_KEY));
      if (saved >= MIN_WIDTH) setWidth(clampWidth(saved));
    } catch {
      /* ignore */
    }
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    // Drawer is anchored to the right edge of the viewport, so the handle
    // sits at `innerWidth - width`: dragging the pointer left grows the
    // panel, dragging right shrinks it.
    const next = clampWidth(window.innerWidth - e.clientX);
    setWidth(next);
  }, []);

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current) return;
      dragging.current = false;
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      try {
        localStorage.setItem(STORAGE_KEY, String(width));
      } catch {
        /* ignore */
      }
    },
    [width],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 flex justify-end" style={{ zIndex: 10100 + layer * 10 }}>
      <button
        type="button"
        className="flex-1 animate-fade-in bg-ink-900/25"
        onClick={onClose}
        aria-label="关闭"
      />
      <aside
        role="dialog"
        aria-modal="true"
        style={{ width, maxWidth: "92vw" }}
        className="relative flex h-full shrink-0 animate-fade-in flex-col border-l border-surface-border bg-surface shadow-pop"
      >
        {/* Drag handle on the left edge. Same idiom as `ResizableSplitPane`'s
            separator: a thin visual line that widens and tints brand color
            on hover/active so the resize affordance is discoverable without
            a label cluttering the header. */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="调整抽屉宽度"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          tabIndex={0}
          className="group absolute inset-y-0 left-0 z-10 -ml-1.5 w-3 shrink-0 cursor-col-resize touch-none bg-transparent"
        >
          <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-surface-border transition group-hover:w-0.5 group-hover:bg-brand-400 group-active:bg-brand-500" />
          <div className="absolute left-1/2 top-1/2 h-8 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-surface-border-strong opacity-0 transition group-hover:opacity-100" />
        </div>

        <div className="flex shrink-0 items-start justify-between gap-2 border-b border-surface-border px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900">{title}</p>
            {subtitle ? <p className="mt-0.5 truncate text-xs text-ink-500">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="btn btn-sm btn-ghost w-7 shrink-0 px-0">
            ×
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{children}</div>
      </aside>
    </div>
  );
}
