"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";

/**
 * The blank in every metric skeleton. Must match `metric_prompts.BLANK` on the server:
 * the caret placement below locates it by this exact token.
 */
export const METRIC_BLANK = "___";

type Drafts = Record<string, string>;

/**
 * Click a sentence shape, get it in the textarea with the caret on the blank.
 *
 * Shared by the evidence panel and the intake panel because both ask the user for a
 * figure and both offer `metric_prompts` skeletons to click. The mechanism looks trivial
 * and is not: the caret has to be placed in a layout effect, after React commits the new
 * value. Doing it in the click handler — even behind `requestAnimationFrame` — races the
 * commit on a controlled textarea, and the commit resets the selection. That bug is
 * invisible in review and obvious in use, which is exactly the kind of thing that must
 * not exist in two copies.
 *
 * What a skeleton never carries is a value. Offering `P99 从 800ms 降到 200ms` to click
 * would be writing a fact on the user's behalf — plausible enough to be accepted, and
 * theirs to defend in the interview. The shape is ours; the numbers are the user's.
 */
export function useSkeletonInsert(setDrafts: (update: (prev: Drafts) => Drafts) => void) {
  const inputs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  // Which field is waiting for its caret. State rather than a ref because the placement
  // has to happen on the render that carries the new value, and only a state change
  // schedules one.
  //
  // Carries a sequence number so each insert is a distinct value. Keyed by name alone,
  // clicking a second shape for the *same* field would set identical state, React would
  // skip the re-render, and the caret would stay on the blank the user already filled.
  const [pending, setPending] = useState<{ key: string; seq: number } | null>(null);
  const seq = useRef(0);

  const insert = useCallback(
    (key: string, skeleton: string) => {
      setDrafts((prev) => {
        const current = (prev[key] ?? "").trim();
        // Append rather than overwrite: one bullet can legitimately carry two figures,
        // and silently discarding what the user already typed is never the right
        // reading of a click on a suggestion.
        const next = current ? `${current}；${skeleton}` : skeleton;
        return { ...prev, [key]: next };
      });
      seq.current += 1;
      setPending({ key, seq: seq.current });
    },
    [setDrafts],
  );

  useLayoutEffect(() => {
    if (!pending) return;
    const el = inputs.current[pending.key];
    setPending(null);
    if (!el) return;
    el.focus();
    // Last occurrence, so clicking a second shape lands on the blank it just added
    // rather than jumping back to one the user has already filled.
    const at = el.value.lastIndexOf(METRIC_BLANK);
    if (at >= 0) el.setSelectionRange(at, at + METRIC_BLANK.length);
    else el.setSelectionRange(el.value.length, el.value.length);
  }, [pending]);

  return { inputs, insert };
}
