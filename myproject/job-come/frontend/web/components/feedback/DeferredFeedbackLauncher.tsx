"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

/**
 * Mounts the floating feedback entry point **after** the page is interactive.
 *
 * Why this exists: `FeedbackLauncher` measured 1,600ms of total blocking time on an
 * otherwise static page — perf 72 → 99 once removed. It is a draggable portal button
 * that subscribes to `useAuth`, and every visitor paid for its hydration before they
 * could scroll a guide they arrived at from a search result. It is not first-screen
 * content and not needed to read anything, so it can wait.
 *
 * The wait is bounded: `requestIdleCallback` when available, a 200ms timeout otherwise,
 * and a `window` "load" listener as a backstop so a browser that never goes idle still
 * gets the button. Deferral must not turn into "some users never see it".
 */
const FeedbackLauncher = dynamic(
  () => import("@/components/feedback/FeedbackLauncher").then((m) => m.FeedbackLauncher),
  { ssr: false },
);

export function DeferredFeedbackLauncher() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const enable = () => {
      if (!cancelled) setReady(true);
    };

    const idle = (
      window as Window & {
        requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
      }
    ).requestIdleCallback;
    let idleId: number | undefined;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    if (typeof idle === "function") {
      idleId = idle(enable, { timeout: 2500 });
    } else {
      timeoutId = setTimeout(enable, 200);
    }
    window.addEventListener("load", enable, { once: true });

    return () => {
      cancelled = true;
      if (idleId !== undefined) {
        (
          window as Window & { cancelIdleCallback?: (id: number) => void }
        ).cancelIdleCallback?.(idleId);
      }
      if (timeoutId !== undefined) clearTimeout(timeoutId);
      window.removeEventListener("load", enable);
    };
  }, []);

  if (!ready) return null;
  return <FeedbackLauncher />;
}
