"use client";

import { AuiIf, ComposerPrimitive } from "@assistant-ui/react";

import { TokenMeter } from "@/components/agent/TokenMeter";
import type { AgentContextUsage } from "@/lib/types/agent";

type Props = {
  disabled?: boolean;
  busy?: boolean;
  context: AgentContextUsage;
  placeholder?: string;
  variant?: "default" | "sidebar";
  onSwitchToLegacy?: () => void;
};

/**
 * assistant-ui headless composer preview.
 *
 * Send / Stop / Enter-submit / IME / auto-resize come from ComposerPrimitive.
 * The external-store runtime forwards submit → `onNew` → `agent.sendMessage`.
 */
export function AgentAssistantComposer({
  disabled = false,
  busy = false,
  context,
  placeholder = "描述你的需求，或粘贴 JD…",
  variant = "default",
  onSwitchToLegacy,
}: Props) {
  const isSidebar = variant === "sidebar";

  return (
    <div
      className={`relative shrink-0 ${
        isSidebar
          ? "border-t border-slate-200/60 bg-[#f8f9fb] px-2.5 pb-2.5 pt-2"
          : "border-t border-slate-200/80 bg-white px-3 pb-3 pt-2"
      }`}
    >
      <ComposerPrimitive.Root
        className={`overflow-visible rounded-[1.15rem] border bg-white focus-within:border-slate-300 ${
          isSidebar
            ? "border-slate-200/80 shadow-[0_2px_16px_rgba(15,23,42,0.06)] focus-within:shadow-[0_4px_20px_rgba(15,23,42,0.08)]"
            : "border-slate-200/90 shadow-[0_4px_24px_rgba(15,23,42,0.08)] focus-within:shadow-[0_8px_32px_rgba(15,23,42,0.1)]"
        }`}
      >
        <div className="px-3 pt-2.5">
          <ComposerPrimitive.Input
            disabled={disabled}
            placeholder={busy ? "生成中…点击停止可中断" : placeholder}
            rows={1}
            className="max-h-[28vh] min-h-[1.25rem] w-full resize-none bg-transparent py-0.5 text-[14px] leading-5 text-slate-900 outline-none placeholder:text-slate-400/80 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        <div className="flex items-center justify-between gap-2 px-2 pb-2 pt-1">
          <div className="flex min-w-0 items-center gap-2">
            {isSidebar ? <TokenMeter context={context} busy={busy} /> : null}
            {onSwitchToLegacy ? (
              <button
                type="button"
                onClick={onSwitchToLegacy}
                className="truncate text-[10px] text-slate-400 underline-offset-2 hover:text-slate-600 hover:underline"
              >
                完整输入框
              </button>
            ) : null}
          </div>

          <div className="flex shrink-0 items-center gap-0.5">
            <AuiIf condition={(s) => !s.thread.isRunning}>
              <ComposerPrimitive.Send asChild>
                <button
                  type="button"
                  disabled={disabled}
                  className={`inline-flex size-9 shrink-0 items-center justify-center rounded-full text-white shadow-sm transition disabled:pointer-events-none disabled:opacity-30 ${
                    isSidebar ? "bg-slate-900 hover:opacity-90" : "bg-brand-600 hover:bg-brand-700"
                  }`}
                  title="发送 (Enter)"
                  aria-label="发送"
                >
                  <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M12 19V5m0 0l-6 6m6-6l6 6"
                    />
                  </svg>
                </button>
              </ComposerPrimitive.Send>
            </AuiIf>
            <AuiIf condition={(s) => s.thread.isRunning}>
              <ComposerPrimitive.Cancel asChild>
                <button
                  type="button"
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-600 text-white shadow-sm hover:bg-rose-700"
                  title="停止"
                  aria-label="停止"
                >
                  <svg className="size-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="7" y="7" width="10" height="10" rx="1" />
                  </svg>
                </button>
              </ComposerPrimitive.Cancel>
            </AuiIf>
          </div>
        </div>
      </ComposerPrimitive.Root>

      {!isSidebar ? (
        <p className="mt-2 px-1 text-[10px] leading-4 text-slate-400">
          Enter 发送 · Shift+Enter 换行 · Context {context.percent}%
          {onSwitchToLegacy ? (
            <>
              {" · "}
              <button
                type="button"
                onClick={onSwitchToLegacy}
                className="underline-offset-2 hover:text-slate-600 hover:underline"
              >
                完整输入框（附件/语音/拍照）
              </button>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
