"use client";

import { useEffect, useRef, useState } from "react";

import { PREVIEW_STAGES, type PreviewProgress } from "@/lib/preview-progress";

const ELEVATE_PREVIEW_TIMEOUT_MS = 255 * 1000;

type Props = {
  progress?: PreviewProgress;
  className?: string;
  startedAt?: number | null;
  onRetry?: () => void;
};

/**
 * Shown while `elevate/preview` is in flight. Indeterminate progress + soft ripples so
 * the empty structured tab does not read as a hang.
 */
export function ElevatePreviewGenerating({ className = "", startedAt = null, onRetry, progress = {} }: Props) {
  const mountAt = useRef(Date.now());
  const effectiveStart = startedAt ?? mountAt.current;

  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const tick = () => {
      setElapsedSec(Math.max(0, Math.floor((Date.now() - effectiveStart) / 1000)));
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [effectiveStart]);

  const completed = PREVIEW_STAGES.filter((stage) => progress[stage.id] === "done").length;
  const verySlow = elapsedSec >= 255;

  return (
    <section
      className={`elevate-generating card-sunken relative min-h-[min(72vh,640px)] overflow-hidden text-center ${className}`}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="正在生成优化预览"
    >
      <div className="elevate-generating-ripples" aria-hidden>
        <span />
        <span />
        <span />
        <span />
        <span />
        <span className="elevate-generating-glow" />
      </div>

      <div className="relative z-10 border-b border-brand-100/80 bg-surface/40 backdrop-blur-[2px]">
        <div className="h-1.5 bg-brand-50" aria-hidden>
          <div className="elevate-generating-bar h-full bg-brand-500 motion-reduce:animate-none" />
        </div>
      </div>

      <div className="relative z-10 flex min-h-[min(68vh,600px)] flex-col items-center justify-center gap-4 px-6 py-12 sm:py-16">
        <span className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50/90 text-brand-600 ring-1 ring-inset ring-brand-100 backdrop-blur-sm">
          <span
            className="absolute inset-0 animate-ping rounded-2xl bg-brand-200/50 motion-reduce:animate-none"
            aria-hidden
          />
          <svg
            viewBox="0 0 24 24"
            aria-hidden
            className="relative h-6 w-6 animate-spin motion-reduce:animate-none"
            fill="none"
          >
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.22" strokeWidth="3" />
            <path
              d="M21 12a9 9 0 0 0-9-9"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </svg>
        </span>

        <div className="w-full max-w-md">
          <p className="text-sm font-semibold text-ink-900">正在生成优化预览</p>
          <p className="mt-1 text-xs tabular-nums text-brand-700">
            已等待 {elapsedSec} 秒
            {` · 已完成 ${completed}/${PREVIEW_STAGES.length} 项`}
          </p>

          <ul className="mt-4 space-y-1.5 text-left">
            {PREVIEW_STAGES.map((stage) => {
              const done = progress[stage.id] === "done";
              const active = progress[stage.id] === "running";
              return (
                <li
                  key={stage.label}
                  className={`flex items-start gap-2 rounded-lg px-2.5 py-1.5 text-xs leading-relaxed transition-colors ${
                    active
                      ? "bg-brand-50/90 font-medium text-brand-900 ring-1 ring-inset ring-brand-100"
                      : done
                        ? "text-ink-600"
                        : "text-ink-400"
                  }`}
                >
                  <span className="mt-0.5 shrink-0 tabular-nums" aria-hidden>
                    {done ? "✓" : active ? "…" : "·"}
                  </span>
                  <span>{stage.label}</span>
                </li>
              );
            })}
          </ul>

          {verySlow && onRetry ? (
            <p className="mt-3 text-xs leading-relaxed text-ink-500">
              若超过本次任务时限仍无结果，可
              <button
                type="button"
                onClick={onRetry}
                className="mx-1 font-medium text-brand-700 underline-offset-2 hover:underline"
              >
                重新生成
              </button>
              一次。
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export { ELEVATE_PREVIEW_TIMEOUT_MS };
