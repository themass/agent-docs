"use client";

import { type MetricCandidate } from "@/lib/api/evidence";

/** How the achievement runs, in the user's words. Labels the chip honestly rather than
 *  implying every metric is an improvement. */
const DIRECTION_HINT: Record<string, string> = {
  down: "越低越好",
  up: "越高越好",
  scale: "量级",
};

/**
 * Clickable ways to answer "能用一个数字说明吗".
 *
 * A row of metric names was not enough: the user still had to invent the sentence and
 * guess what shape of answer we can use. Clicking a chip writes the skeleton into the
 * textarea with `___` where the figure goes, and puts the cursor on the first blank.
 *
 * What a chip never carries is a value. Offering `P99 从 800ms 降到 200ms` to click would
 * be writing a fact on the user's behalf — plausible enough to be accepted, and theirs
 * to defend in the interview. The shape is ours; the numbers are the user's.
 *
 * Shared by the evidence panel (repairing a bullet that exists) and the intake panel
 * (collecting the first bullets there are). Both ask for the same thing in the same
 * words, and one of them having a worse affordance than the other is not a decision
 * anyone would make on purpose.
 */
export function MetricChips({
  metrics,
  onPick,
  hint = "点一个句式填进去，数字由你填——我们不会替你估。",
}: {
  metrics: MetricCandidate[];
  onPick: (skeleton: string) => void;
  hint?: string;
}) {
  if (!metrics.length) return null;
  return (
    <div className="mt-2">
      <p className="text-micro text-ink-500">{hint}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {metrics.map((m) => {
          const direction = DIRECTION_HINT[m.direction];
          return (
            <button
              key={m.dimension}
              type="button"
              onClick={() => onPick(m.skeleton)}
              title={m.skeleton}
              className="btn btn-sm btn-secondary max-w-full"
            >
              <span className="truncate">{m.dimension}</span>
              {m.unit ? <span className="ml-1 shrink-0 text-ink-500">{m.unit}</span> : null}
              {direction ? (
                <span className="ml-1 shrink-0 text-ink-500">· {direction}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
