"use client";

import { useEffect, useRef, useState } from "react";

import type { AgentContextUsage } from "@/lib/types/agent";

const BUCKET_COLORS: Record<string, string> = {
  system_prompt: "bg-slate-400",
  tool_definitions: "bg-orange-500",
  rules: "bg-emerald-500",
  skills: "bg-violet-500",
  mcp_dynamic: "bg-fuchsia-500",
  conversation: "bg-pink-500",
  summarized: "bg-rose-600",
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function ContextRing({ ratio, size = 16 }: { ratio: number; size?: number }) {
  const stroke = 2;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.min(1, Math.max(0, ratio)));
  const color =
    ratio >= 0.9 ? "stroke-amber-500" : ratio >= 0.75 ? "stroke-yellow-500" : "stroke-slate-700";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90 shrink-0" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="stroke-slate-200" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" className={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset} />
    </svg>
  );
}

type Props = {
  context: AgentContextUsage;
  busy?: boolean;
};

export function TokenMeter({ context, busy = false }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const ratio = context.limit_tokens > 0 ? context.used_tokens / context.limit_tokens : 0;

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className="inline-flex size-7 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
        aria-expanded={open}
        aria-label={`Context ${context.percent}%`}
        title={`Context ${context.percent}%`}
        onClick={() => setOpen((v) => !v)}
      >
        <ContextRing ratio={busy && context.used_tokens === 0 ? 0.08 : ratio} size={16} />
      </button>

      {open ? (
        <div className="absolute bottom-full right-0 z-50 mb-1.5 w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-zinc-700/80 bg-zinc-900 text-zinc-100 shadow-2xl">
          <div className="flex items-center justify-between gap-2 border-b border-zinc-700/70 px-3 py-2">
            <p className="text-[11px] font-medium text-zinc-50">Context Usage</p>
            <button type="button" className="text-zinc-400 hover:text-zinc-100" onClick={() => setOpen(false)} aria-label="关闭">×</button>
          </div>
          <div className="space-y-2 px-3 py-2.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-zinc-300">{context.percent}% Full{context.estimated ? " · est." : ""}</span>
              <span className="font-mono tabular-nums text-zinc-400">
                ~{formatTokens(context.used_tokens)} / {formatTokens(context.limit_tokens)}
              </span>
            </div>
            <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
              {context.buckets.map((bucket) => (
                <div
                  key={bucket.id}
                  className={BUCKET_COLORS[bucket.id] ?? "bg-slate-500"}
                  style={{ width: `${Math.max(1, (bucket.tokens / context.used_tokens) * 100)}%` }}
                  title={`${bucket.label}: ${formatTokens(bucket.tokens)}`}
                />
              ))}
            </div>
            <ul className="max-h-52 space-y-1 overflow-y-auto text-[11px] text-zinc-300">
              {context.buckets.map((bucket) => (
                <li key={bucket.id} className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className={`size-1.5 shrink-0 rounded-sm ${BUCKET_COLORS[bucket.id] ?? "bg-slate-500"}`} />
                    <span className="truncate">{bucket.label}</span>
                  </span>
                  <span className="font-mono tabular-nums text-zinc-400">{formatTokens(bucket.tokens)}</span>
                </li>
              ))}
              <li className="flex items-center justify-between gap-2 border-t border-zinc-800 pt-1">
                <span className="text-zinc-400">Turns</span>
                <span className="font-mono tabular-nums text-zinc-400">{context.turns}</span>
              </li>
              {context.actual ? (
                <li className="flex items-center justify-between gap-2 text-zinc-500">
                  <span>API usage</span>
                  <span className="font-mono tabular-nums">{formatTokens(context.actual.total_tokens)}</span>
                </li>
              ) : null}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}
