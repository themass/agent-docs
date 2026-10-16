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
          ? "border-t border-surface-border bg-surface-sunken px-2.5 pb-2.5 pt-2"
          : "border-t border-surface-border bg-surface px-3 pb-3 pt-2"
      }`}
    >
      <ComposerPrimitive.Root
        className={`overflow-visible rounded-2xl border border-surface-border bg-surface transition focus-within:border-brand-300 focus-within:ring-4 focus-within:ring-brand-500/10 ${
          isSidebar ? "shadow-card" : "shadow-raised"
        }`}
      >
        <div className="px-3 pt-2.5">
          <ComposerPrimitive.Input
            disabled={disabled}
            placeholder={busy ? "生成中…点击停止可中断" : placeholder}
            rows={1}
            className="scroll-area max-h-[28vh] min-h-[1.25rem] w-full resize-none bg-transparent py-0.5 text-base leading-relaxed text-ink-900 outline-none placeholder:text-ink-400 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        <div className="flex items-center justify-between gap-2 px-2 pb-2 pt-1">
          <div className="flex min-w-0 items-center gap-2">
            {isSidebar ? <TokenMeter context={context} busy={busy} /> : null}
            {onSwitchToLegacy ? (
              <button
                type="button"
                onClick={onSwitchToLegacy}
                className="truncate text-micro text-ink-500 underline-offset-2 hover:text-ink-600 hover:underline"
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
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white shadow-xs transition hover:bg-brand-700 disabled:pointer-events-none disabled:opacity-30"
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
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-danger-600 text-white shadow-xs hover:bg-danger-700"
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
        <p className="mt-2 px-1 text-micro leading-4 text-ink-500">
          Enter 发送 · Shift+Enter 换行 · Context {context.percent}%
          {onSwitchToLegacy ? (
            <>
              {" · "}
              <button
                type="button"
                onClick={onSwitchToLegacy}
                className="underline-offset-2 hover:text-ink-600 hover:underline"
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
