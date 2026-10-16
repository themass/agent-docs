"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_STORAGE_KEY = "jc-agent-panel-width";
const DEFAULT_WIDTH = 420;
const MIN_WIDTH = 300;
const MAX_RATIO = 0.62;

function clampWidth(width: number, containerWidth: number): number {
  const max = Math.max(MIN_WIDTH, containerWidth * MAX_RATIO);
  return Math.min(max, Math.max(MIN_WIDTH, width));
}

type Props = {
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
  storageKey?: string;
  defaultWidth?: number;
  separatorLabel?: string;
  /** When false, left pane manages its own scroll (sticky footers). */
  leftScrollable?: boolean;
};

export function ResizableSplitPane({
  left,
  right,
  className = "",
  storageKey = DEFAULT_STORAGE_KEY,
  defaultWidth = DEFAULT_WIDTH,
  separatorLabel = "调整面板宽度",
  leftScrollable = true,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [panelWidth, setPanelWidth] = useState(defaultWidth);
  const dragging = useRef(false);

  useEffect(() => {
    try {
      const saved = Number(localStorage.getItem(storageKey));
      if (saved >= MIN_WIDTH) setPanelWidth(saved);
    } catch {
      /* ignore */
    }
  }, [storageKey]);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !rootRef.current) return;
    const rect = rootRef.current.getBoundingClientRect();
    const fromRight = rect.right - e.clientX;
    const next = clampWidth(fromRight, rect.width);
    setPanelWidth(next);
  }, []);

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current) return;
      dragging.current = false;
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      try {
        localStorage.setItem(storageKey, String(panelWidth));
      } catch {
        /* ignore */
      }
    },
    [panelWidth, storageKey],
  );

  return (
    <div
      ref={rootRef}
      className={`flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-2xl border border-surface-border bg-surface shadow-panel ${className}`}
    >
      <section
        className={`scroll-area min-h-0 min-w-0 flex-1 bg-surface-sunken ${
          leftScrollable ? "overflow-y-auto overflow-x-hidden" : "overflow-hidden"
        }`}
      >
        {left}
      </section>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={separatorLabel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        tabIndex={0}
        className="group relative z-10 -mx-1 w-3 shrink-0 cursor-col-resize touch-none bg-transparent"
      >
        <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-surface-border transition group-hover:w-0.5 group-hover:bg-brand-400 group-active:bg-brand-500" />
        <div className="absolute left-1/2 top-1/2 h-8 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-surface-border-strong opacity-0 transition group-hover:opacity-100" />
      </div>

      <aside
        className="flex min-h-0 shrink-0 flex-col border-l border-surface-border bg-surface"
        style={{ width: panelWidth }}
      >
        {right}
      </aside>
    </div>
  );
}
