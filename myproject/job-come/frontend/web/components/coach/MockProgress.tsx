"use client";

import type { MockProgress as Progress, MockSession } from "@/lib/api/coach";

type Props = {
  session: MockSession;
  progress: Progress | null;
  active: boolean;
};

/**
 * Where the live session stands, beside the setup: how far through the questions, how many of the
 * job's must-haves have been asked about, and the one still to ask. The things the candidate can do
 * with the question on the table are in the bar above the conversation.
 */
export function MockProgress({ session, progress, active }: Props) {
  if (!progress) return null;
  const onTable = session.questions.find((q) => q.id === progress.current_question_id)?.stem ?? null;

  return (
    <div className="card-sunken mt-4 space-y-2 px-4 py-3">
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
        <p className="text-xs text-ink-500">还没问到：{progress.uncovered.join("、")}</p>
      ) : null}

      {active && onTable ? (
        <p className="text-sm text-ink-800">
          <span className="text-xs text-ink-500">当前题：</span>
          {onTable}
        </p>
      ) : null}
    </div>
  );
}
