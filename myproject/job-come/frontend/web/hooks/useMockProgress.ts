"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getMockProgress, type MockProgress } from "@/lib/api/coach";

/** A safety net. The page also asks right after each of the interviewer's turns, which is when the
 * progress changes, so this only catches what happens without a turn (a session closing on its own). */
const POLL_MS = 15_000;

/**
 * Where the live interview stands, read from the server. One reader for the page, so the interview
 * bar and the panel beside it never ask separately or disagree.
 *
 * `onEnded` runs once when the server says the session is no longer active, whoever ended it: the
 * candidate, the interviewer's own `jc_mock_end`, or the idle timeout.
 */
export function useMockProgress(sessionId: string | null, onEnded?: (sessionId: string) => void) {
  const [progress, setProgress] = useState<MockProgress | null>(null);
  const [error, setError] = useState(false);
  const currentId = useRef<string | null>(null);
  const endedRef = useRef(onEnded);
  endedRef.current = onEnded;

  const refresh = useCallback(async () => {
    const id = currentId.current;
    if (!id) return;
    try {
      const next = await getMockProgress(id);
      // An answer for a session the page has since left is not this page's to show.
      if (currentId.current !== id) return;
      setProgress(next);
      setError(false);
      if (next.status !== "active") {
        currentId.current = null;
        endedRef.current?.(id);
      }
    } catch {
      if (currentId.current === id) setError(true);
    }
  }, []);

  useEffect(() => {
    currentId.current = sessionId;
    setProgress(null);
    setError(false);
    if (!sessionId) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [sessionId, refresh]);

  return { progress, error, refresh };
}
