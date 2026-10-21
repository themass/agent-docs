"use client";

import { useEffect, useState } from "react";
import { REVIEW_STAGES, type ReviewProgress } from "@/lib/review-progress";

type Props = { progress: ReviewProgress; startedAt: number | null; busy: boolean; onSkip?: () => void };
export function ExportReviewProgress({ progress, startedAt, busy, onSkip }: Props) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const tick = () => setElapsed(startedAt ? Math.max(0, Math.floor((Date.now() - startedAt) / 1000)) : 0);
    tick();
    if (!busy) return;
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [startedAt, busy]);
  const done = REVIEW_STAGES.filter(s => progress[s.id] === "done").length;
  const unavailable = progress.model === "unavailable";
  return <div className="mt-3 rounded-xl bg-surface-sunken p-3.5 ring-1 ring-inset ring-surface-border" aria-busy={busy}>
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
      <p className="tabular-nums text-ink-600" role="status" aria-live="polite">
        已完成 {done}/{REVIEW_STAGES.length} 项 · {elapsed} 秒{unavailable ? " · 模型核对未完成" : ""}
      </p>
      {busy && onSkip ? <button type="button" onClick={onSkip} className="text-brand-700 hover:underline">停止等待，稍后再检查</button> : null}
    </div>
    <div role="progressbar" aria-label="优化稿内容检查进度" aria-valuemin={0} aria-valuemax={REVIEW_STAGES.length}
      aria-valuenow={done} aria-valuetext={`已完成 ${done}/${REVIEW_STAGES.length} 项`}
      className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-ink-200/60">
      <div className="h-full rounded-full bg-brand-500 transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${done / REVIEW_STAGES.length * 100}%` }} />
    </div>
    <ol className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {REVIEW_STAGES.map((stage, index) => {
        const status = progress[stage.id];
        const active = busy && status === "running";
        return <li key={stage.id} className={`flex items-start gap-1.5 text-xs leading-relaxed ${active ? "font-medium text-brand-700" : status === "unavailable" ? "text-warn-700" : status === "done" ? "text-ink-700" : "text-ink-400"}`}>
          <span aria-hidden className={`mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${active ? "animate-pulse bg-brand-100 motion-reduce:animate-none" : "bg-ink-100"}`}>{status === "done" ? "✓" : status === "unavailable" ? "!" : index + 1}</span>
          <span>{stage.label}<span className="block text-micro font-normal">{status === "done" ? "已完成" : status === "unavailable" ? "未完成" : active ? "进行中…" : busy ? "等待中" : "未完成"}</span></span>
        </li>;
      })}
    </ol>
  </div>;
}
