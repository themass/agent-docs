"use client";

import { useMemo, useState } from "react";

import type { ResumeDraft } from "@/lib/api/resume";
import { resolveTechniques, summarizeTechniques, TECHNIQUES } from "@/lib/elevation-techniques";

type ElevationEntry = {
  field_path?: string;
  source_text?: string;
  written_text?: string;
  needs_defense?: boolean;
  techniques?: unknown;
};

type Props = {
  draft: ResumeDraft | null;
};

/** Human-readable location for a diff, e.g. `第 1 段经历 · 第 3 条`. */
function describePath(path: string | undefined): string | null {
  if (!path) return null;
  const match = /(experience|project)_blocks\[(\d+)\]\.bullets\[(\d+)\]/.exec(path);
  if (!match) return path;
  const section = match[1] === "project" ? "项目" : "段经历";
  const unit = match[1] === "project" ? `第 ${Number(match[2]) + 1} 个${section}` : `第 ${Number(match[2]) + 1} ${section}`;
  return `${unit} · 第 ${Number(match[3]) + 1} 条`;
}

export function ElevationChangesPanel({ draft }: Props) {
  const entries = useMemo(
    () => (draft?.elevation_map ?? []) as ElevationEntry[],
    [draft?.elevation_map],
  );
  const summary = useMemo(() => summarizeTechniques(entries), [entries]);
  const [filter, setFilter] = useState<string | null>(null);

  const visible = useMemo(() => {
    if (!filter) return entries;
    return entries.filter((e) => resolveTechniques(e.techniques).some((t) => t.id === filter));
  }, [entries, filter]);

  if (!draft) {
    return (
      <div className="card-sunken bg-sheen px-6 py-12 text-center">
        <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-500">
          生成优化预览后，这里会逐条列出原文、优化后的写法，以及用到的强化手段。
        </p>
      </div>
    );
  }

  if (!entries.length) {
    return (
      <div className="card card-pad">
        <p className="text-sm font-semibold text-ink-900">当前档位未产生文本变更</p>
        <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
          保守档位会尽量保持原文；切换到「标准」或「强化」可以看到逐条改写。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <section className="card card-pad">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink-900">
            这一稿改了 {entries.length} 处
          </h3>
          <span className="text-xs text-ink-500">点击手段只看相关改动</span>
        </div>
        {summary.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setFilter(null)}
              aria-pressed={filter === null}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                filter === null
                  ? "bg-brand-600 text-white shadow-xs"
                  : "bg-ink-100 text-ink-600 hover:bg-ink-200 hover:text-ink-800"
              }`}
            >
              全部 <span className="tabular-nums opacity-70">{entries.length}</span>
            </button>
            {summary.map((t) => {
              const active = filter === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setFilter(active ? null : t.id)}
                  title={t.hint}
                  aria-pressed={active}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                    active
                      ? "bg-brand-600 text-white shadow-xs"
                      : "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100 hover:bg-brand-100"
                  }`}
                >
                  {t.label}{" "}
                  <span className="tabular-nums opacity-70">{t.count}</span>
                </button>
              );
            })}
          </div>
        ) : null}
        {filter ? (
          <p className="mt-2.5 max-w-prose text-xs leading-relaxed text-ink-500">
            {TECHNIQUES.find((t) => t.id === filter)?.hint}
          </p>
        ) : null}
      </section>

      <ul className="space-y-2.5">
        {visible.map((entry, idx) => {
          const techniques = resolveTechniques(entry.techniques);
          const where = describePath(entry.field_path);
          return (
            <li
              key={`${entry.field_path ?? idx}-${idx}`}
              className="card card-pad transition hover:shadow-raised"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                {where ? (
                  <span className="label-meta normal-case tracking-normal text-ink-500">
                    {where}
                  </span>
                ) : (
                  <span />
                )}
                {techniques.length ? (
                  <span className="flex flex-wrap gap-1">
                    {techniques.map((t) => (
                      <span key={t.id} title={t.hint} className="badge badge-brand">
                        {t.label}
                      </span>
                    ))}
                  </span>
                ) : null}
              </div>

              {/* Before / after, read top-to-bottom with an explicit arrow so the
                  direction of the change is unmistakable. */}
              <div className="mt-2.5">
                <div className="rounded-lg bg-ink-50 px-3 py-2.5">
                  <span className="label-meta block">原文</span>
                  <p className="mt-1 text-sm leading-relaxed text-ink-500 line-through decoration-ink-300 decoration-1">
                    {entry.source_text?.trim() || "（原简历此处为空）"}
                  </p>
                </div>
                <div className="flex justify-center py-0.5" aria-hidden="true">
                  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-ink-300" fill="currentColor">
                    <path d="M8 13.5 3.5 8.2l1.15-.98L7.2 10.2V2.5h1.6v7.7l2.55-2.98 1.15.98L8 13.5Z" />
                  </svg>
                </div>
                <div className="rounded-lg bg-brand-50/70 px-3 py-2.5 ring-1 ring-inset ring-brand-100">
                  <span className="label-meta block text-brand-500">优化后</span>
                  <p className="mt-1 text-sm leading-relaxed text-brand-900">
                    {entry.written_text?.trim() || "—"}
                  </p>
                </div>
              </div>

              {entry.needs_defense ? (
                <div className="notice notice-warn mt-2.5 text-xs">
                  <svg
                    viewBox="0 0 16 16"
                    aria-hidden="true"
                    className="mt-px h-3.5 w-3.5 shrink-0"
                    fill="currentColor"
                  >
                    <path d="M8 1.2 15 14H1L8 1.2Zm-.8 4.3v4.3h1.6V5.5H7.2Zm0 5.4v1.6h1.6v-1.6H7.2Z" />
                  </svg>
                  <span className="leading-relaxed">
                    面试会被追问这条，提前准备好具体过程和数据来源。
                  </span>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      {!visible.length ? (
        <div className="card-sunken py-10 text-center">
          <p className="text-sm text-ink-500">没有用到这个手段的改动。</p>
        </div>
      ) : null}
    </div>
  );
}
