"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getMockProgress,
  skipMockQuestion,
  swapMockQuestion,
  type MockActionResult,
  type MockProgress as Progress,
  type MockSession,
} from "@/lib/api/coach";
import { userFacingApiError } from "@/lib/api/user-error";

const POLL_MS = 20_000;

type Props = {
  session: MockSession;
  active: boolean;
};

/**
 * Where the live session stands, and the two things the candidate can do with the question on the
 * table. Skip and swap change the session on the server; the interviewer reads that on its next
 * turn, so the candidate says "下一题" in the chat to move on.
 */
export function MockProgress({ session, active }: Props) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProgress(await getMockProgress(session.id));
    } catch (err) {
      setError(userFacingApiError(err, "读取进度失败"));
    }
  }, [session.id]);

  useEffect(() => {
    if (!active) return;
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const stemOf = (id: string | null) =>
    session.questions.find((q) => q.id === id)?.stem ?? null;

  async function act(kind: "skip" | "swap") {
    if (!progress?.current_question_id) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const call = kind === "skip" ? skipMockQuestion : swapMockQuestion;
      const result: MockActionResult = await call(session.id, progress.current_question_id);
      if (!result.accepted) {
        setError(result.reason ?? "这次操作没有生效。");
      } else {
        setNotice(
          kind === "skip"
            ? "已跳过这题（计为未答）。在对话里说「下一题」继续。"
            : `已换题（剩余 ${result.swaps_left ?? 0} 次）。在对话里说「下一题」继续。`,
        );
      }
      await refresh();
    } catch (err) {
      setError(userFacingApiError(err, "操作失败，请稍后重试"));
    } finally {
      setBusy(false);
    }
  }

  if (!progress) return null;
  const onTable = stemOf(progress.current_question_id);

  return (
    <div className="card-sunken mt-4 space-y-3 px-4 py-3">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-600">
        <span>
          主问题 {progress.asked_main} / {progress.main_limit}
        </span>
        {progress.must_have.length > 0 ? (
          <span>
            必备项 {progress.covered.length} / {progress.must_have.length} 已覆盖
          </span>
        ) : null}
        {progress.skipped > 0 ? <span>已跳过 {progress.skipped} 题</span> : null}
      </div>

      {progress.uncovered.length > 0 && active ? (
        <p className="text-xs text-ink-500">
          还没问到：{progress.uncovered.join("、")}
        </p>
      ) : null}

      {active && progress.current_question_id ? (
        <div className="space-y-2">
          <p className="text-sm text-ink-800">
            <span className="text-xs text-ink-500">当前题：</span>
            {onTable ?? "（题目内容见对话）"}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("skip")}
              className="btn btn-sm btn-secondary"
            >
              跳过本题
            </button>
            <button
              type="button"
              disabled={busy || progress.swaps_left <= 0}
              onClick={() => void act("swap")}
              className="btn btn-sm btn-secondary"
            >
              换一题（剩余 {progress.swaps_left} 次）
            </button>
          </div>
        </div>
      ) : null}

      {notice ? <p className="notice notice-success text-xs">{notice}</p> : null}
      {error ? (
        <p className="notice notice-danger text-xs" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
