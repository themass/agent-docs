"use client";

import { useEffect, useRef, useState } from "react";

import { useMockProgress } from "@/hooks/useMockProgress";
import {
  completeMockSession,
  skipMockQuestion,
  swapMockQuestion,
} from "@/lib/api/coach";
import { userFacingApiError } from "@/lib/api/user-error";
import {
  barText,
  formatElapsed,
  SKIP_MESSAGE,
  SWAP_MESSAGE,
} from "@/lib/mock-interview";

/** What the bar needs of the conversation beside it. */
type Conversation = {
  busy: boolean;
  sendMessage: (content: string) => Promise<void> | void;
};

type Props = {
  sessionId: string;
  conversation: Conversation;
  progress: ReturnType<typeof useMockProgress>;
  /** The candidate ended the interview from here. */
  onEnded: (sessionId: string) => void;
};

/**
 * The strip above the conversation while an interview is running: which question, which stage, how
 * long it has been, and the things the candidate can do with the question on the table.
 *
 * Skip and Swap change the session on the server and then say so to the interviewer in the chat, so
 * the next question comes without the candidate having to type it.
 */
export function MockBar({ sessionId, conversation, progress: reader, onEnded }: Props) {
  const { progress, refresh } = reader;
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // The progress changes when the interviewer registers a question, which happens inside its turn.
  // Ask again as soon as the turn is over.
  const wasBusy = useRef(conversation.busy);
  useEffect(() => {
    if (wasBusy.current && !conversation.busy) void refresh();
    wasBusy.current = conversation.busy;
  }, [conversation.busy, refresh]);

  if (!progress) {
    return <div className="card-sunken px-4 py-2 text-xs text-ink-500">正在读取面试进度…</div>;
  }

  const text = barText(progress);
  const started = progress.started_at ? Date.parse(progress.started_at) : Number.NaN;
  const elapsed = Number.isFinite(started) ? formatElapsed(now - started) : null;
  const canAct =
    !busy && !conversation.busy && !progress.candidate_qa && Boolean(progress.current_question_id);

  async function act(kind: "skip" | "swap") {
    if (!progress?.current_question_id) return;
    setBusy(true);
    setNotice(null);
    try {
      const call = kind === "skip" ? skipMockQuestion : swapMockQuestion;
      const result = await call(sessionId, progress.current_question_id);
      if (!result.accepted) {
        setNotice(result.reason ?? "这次操作没有生效。");
        return;
      }
      await refresh();
      await conversation.sendMessage(kind === "skip" ? SKIP_MESSAGE : SWAP_MESSAGE);
    } catch (err) {
      setNotice(userFacingApiError(err, "操作失败，请稍后重试"));
    } finally {
      setBusy(false);
    }
  }

  async function end() {
    setBusy(true);
    setNotice(null);
    try {
      await completeMockSession(sessionId);
      onEnded(sessionId);
    } catch (err) {
      setNotice(userFacingApiError(err, "结束失败，请稍后重试"));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <div className="card-sunken flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2 text-xs">
      <span className="font-semibold text-ink-900">{text.position}</span>
      {text.stage ? <span className="badge badge-brand">{text.stage}</span> : null}
      {elapsed ? <span className="tabular-nums text-ink-500">已用 {elapsed}</span> : null}
      {progress.skipped > 0 ? <span className="text-ink-500">已跳过 {progress.skipped} 题</span> : null}
      <span className="ml-auto flex flex-wrap items-center gap-2">
        {confirming ? (
          <>
            <span className="text-ink-600">现在结束面试？</span>
            <button type="button" disabled={busy} onClick={() => void end()} className="btn btn-sm btn-primary">
              确认结束
            </button>
            <button type="button" disabled={busy} onClick={() => setConfirming(false)} className="btn btn-sm btn-secondary">
              继续面试
            </button>
          </>
        ) : (
          <>
            <button type="button" disabled={!canAct} onClick={() => void act("skip")} className="btn btn-sm btn-secondary">
              跳过
            </button>
            <button
              type="button"
              disabled={!canAct || progress.swaps_left <= 0}
              onClick={() => void act("swap")}
              className="btn btn-sm btn-secondary"
            >
              换一题（剩 {progress.swaps_left}）
            </button>
            <button type="button" disabled={busy} onClick={() => setConfirming(true)} className="btn btn-sm btn-secondary">
              结束面试
            </button>
          </>
        )}
      </span>
      {notice ? (
        <p className="notice notice-danger w-full text-xs" role="alert">
          {notice}
        </p>
      ) : null}
    </div>
  );
}
