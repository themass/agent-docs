"use client";

import { useEffect, useRef, useState } from "react";

import { RichText } from "./RichText";

/** Presentation-only pacing. Never delays receiving, saving, or confirming a run. */
export function AssistantReplyText({ text, streaming, reveal }: {
  text: string;
  streaming: boolean;
  /** Only newly received replies animate; loading history must not replay it. */
  reveal: boolean;
}) {
  const [visible, setVisible] = useState(() => (reveal || streaming ? "" : text));
  const visibleRef = useRef(visible);
  const targetRef = useRef(text);
  const frameRef = useRef(0);

  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const showAll = () => {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      visibleRef.current = targetRef.current;
      setVisible(targetRef.current);
    };
    motion.addEventListener("change", showAll);
    return () => {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      motion.removeEventListener("change", showAll);
    };
  }, []);

  useEffect(() => {
    targetRef.current = text;
    // A non-prefix replacement (sanitization/history correction) is authoritative,
    // not another delta. Do not replay text or resurrect removed content.
    if ((!reveal && !streaming)
        || window.matchMedia("(prefers-reduced-motion: reduce)").matches
        || !text.startsWith(visibleRef.current)) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = 0;
      visibleRef.current = text;
      setVisible(text);
      return;
    }
    if (frameRef.current || visibleRef.current === text) return;

    let last = performance.now();
    let budget = 0;
    const tick = (now: number) => {
      // Read the newest target, not the chunk which started this frame loop.
      // Updating props must not cancel/restart the clock: fast token arrival
      // would otherwise starve the animation before its first frame.
      const target = targetRef.current;
      const chars = Array.from(target);
      let count = Array.from(visibleRef.current).length;
      const remaining = chars.length - count;
      // Normal text advances at 60 chars/sec; bursts catch up rather than leaving
      // the UI "typing" for minutes. Code points avoid splitting emoji pairs.
      budget += Math.min(now - last, 100) / 1000 * Math.max(60, remaining / 0.35);
      last = now;
      const advance = Math.floor(budget);
      budget -= advance;
      if (advance > 0) {
        count = Math.min(chars.length, count + advance);
        visibleRef.current = chars.slice(0, count).join("");
        setVisible(visibleRef.current);
      }
      frameRef.current = count < chars.length ? requestAnimationFrame(tick) : 0;
    };
    frameRef.current = requestAnimationFrame(tick);
  }, [text, reveal, streaming]);

  const typing = streaming || visible !== text;
  return (
    <div data-assistant-reply data-typing={typing ? "true" : "false"}>
      <RichText text={visible} caret={typing ? (
        <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-brand-500 align-middle" aria-hidden />
      ) : undefined} />
    </div>
  );
}
