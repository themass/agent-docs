"use client";

import type { ResumeDraft } from "@/lib/api/resume";

type ElevationEntry = {
  field_path?: string;
  source_text?: string;
  written_text?: string;
  needs_defense?: boolean;
};

type Props = {
  draft: ResumeDraft | null;
};

export function ElevationChangesPanel({ draft }: Props) {
  const entries = (draft?.elevation_map ?? []) as ElevationEntry[];

  if (!draft) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        生成优化预览后，这里将展示原文与优化后的差异。
      </div>
    );
  }

  if (!entries.length) {
    return (
      <div className="rounded-xl border border-surface-border bg-white px-4 py-6 text-sm text-slate-600">
        <p className="font-medium text-slate-800">当前档位未产生文本变更</p>
        <p className="mt-1 text-slate-500">
          保守档位可能保持原文；可尝试「标准」或「强化」档位查看差异。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">优化变更 ({entries.length})</h3>
        <span className="text-xs text-slate-400">对比原文 → 优化后</span>
      </div>
      <ul className="max-h-[min(50vh,480px)] space-y-2 overflow-y-auto pr-1">
        {entries.map((entry, idx) => (
          <li
            key={`${entry.field_path ?? idx}-${idx}`}
            className="rounded-xl border border-surface-border bg-white p-3 text-sm shadow-sm"
          >
            {entry.field_path ? (
              <p className="mb-2 font-mono text-[10px] text-slate-400">{entry.field_path}</p>
            ) : null}
            <div className="space-y-2">
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600 line-through decoration-slate-300">
                {entry.source_text ?? "—"}
              </div>
              <div className="rounded-lg bg-brand-50 px-3 py-2 text-brand-900 ring-1 ring-brand-100">
                {entry.written_text ?? "—"}
              </div>
            </div>
            {entry.needs_defense ? (
              <p className="mt-2 text-xs text-amber-700">需在面试中准备圆场说明</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
