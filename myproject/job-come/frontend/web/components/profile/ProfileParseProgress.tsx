"use client";

import type { ChangeEvent } from "react";

import type { ProfileSource } from "@/lib/api/profile";
import { parseProgressState, parseWaitSeconds } from "@/lib/profile-parse";

type Props = {
  source?: ProfileSource;
  replacing?: boolean;
  error?: string | null;
  onFileSelected: (event: ChangeEvent<HTMLInputElement>) => void;
};

const ACCEPTED_RESUME_TYPES = ".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp";

/**
 * Shows truthful, phase-based progress while a resume is processed in the background.
 * This deliberately avoids a percentage: the backend can choose a different extraction route.
 */
export function ProfileParseProgress({ source, replacing = false, error, onFileSelected }: Props) {
  const progress = parseProgressState(source?.parse_phase);
  const waitSeconds = parseWaitSeconds(source);

  return (
    <section
      className="card overflow-hidden"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="简历正在处理中"
    >
      <div className="h-0.5 bg-brand-100" aria-hidden>
        <div className="h-full w-2/3 origin-left animate-[parse-progress_2.4s_ease-in-out_infinite] bg-brand-600 motion-reduce:animate-none" />
      </div>

      <div className="card-pad">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 gap-3">
            <span className="relative mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
              <span
                className="absolute h-5 w-5 animate-ping rounded-full bg-brand-200/70 motion-reduce:animate-none"
                aria-hidden
              />
              <svg className="relative h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 3.75h6.5L19 8.25v12A.75.75 0 0118.25 21h-10.5a.75.75 0 01-.75-.75v-15A1.5 1.5 0 018.5 3.75z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M14 3.75v4.5h5M9.5 14h5m-5 3h3.5" />
              </svg>
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <h2 className="text-base font-semibold tracking-tight text-ink-900">
                  正在为你整理职业档案
                </h2>
                <span className="badge badge-brand">
                  <span
                    className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-600 motion-reduce:animate-none"
                    aria-hidden
                  />
                  后台处理中
                </span>
              </div>
              <p className="mt-1.5 text-sm text-ink-600">
                正在处理：
                <span className="font-medium text-ink-900">{progress.currentLabel}</span>
              </p>
              {source?.file_name ? (
                <p className="mt-1 truncate text-xs text-ink-500" title={source.file_name}>
                  {source.file_name}
                </p>
              ) : null}
            </div>
          </div>

          <label className="btn btn-sm btn-secondary shrink-0 cursor-pointer">
            {replacing ? "上传中…" : "重新上传"}
            <input
              type="file"
              className="sr-only"
              accept={ACCEPTED_RESUME_TYPES}
              disabled={replacing}
              onChange={onFileSelected}
            />
          </label>
        </div>

        {/* Phase list. State is encoded by fill + icon, not colour alone. */}
        <ol className="mt-5 grid grid-cols-2 gap-x-3 gap-y-2.5 sm:grid-cols-4" aria-label="简历处理步骤">
          {progress.steps.map((step, index) => {
            const isCurrent = index === progress.currentStep;
            const isComplete = index < progress.currentStep;
            return (
              <li key={step.label} className="flex min-w-0 items-center gap-2">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-micro font-bold ${
                    isComplete
                      ? "bg-brand-600 text-white"
                      : isCurrent
                        ? "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-300"
                        : "bg-ink-100 text-ink-500"
                  }`}
                  aria-hidden
                >
                  {isComplete ? (
                    "✓"
                  ) : isCurrent ? (
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-600 motion-reduce:animate-none" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={`min-w-0 text-xs ${
                    isCurrent
                      ? "font-medium text-ink-900"
                      : isComplete
                        ? "text-ink-600"
                        : "text-ink-500"
                  }`}
                >
                  {step.label}
                </span>
              </li>
            );
          })}
        </ol>

        <div className="mt-5 space-y-2 border-t border-surface-border pt-3.5 text-xs text-ink-500">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
            <p>
              {waitSeconds != null && waitSeconds >= 120
                ? "本次处理时间较长，正在等待解析结果；完成或失败后会自动更新。"
                : "正在按文档内容选择解析方式；文字版简历无需图片识别。完成后请核对可编辑草稿。"}
            </p>
            {waitSeconds != null && waitSeconds >= 10 ? (
              <p className="tabular-nums text-ink-500">已处理约 {waitSeconds} 秒</p>
            ) : null}
          </div>

        </div>
        {error ? (
          <div className="notice notice-danger mt-3" role="alert">
            <span>{error}</span>
          </div>
        ) : null}
      </div>
    </section>
  );
}
