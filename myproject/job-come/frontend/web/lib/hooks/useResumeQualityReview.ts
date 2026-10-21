"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { reviewBeforeExport, type ExportReview, type ResumeTrack } from "@/lib/api/resume";
import { userFacingExportError } from "@/lib/api/user-error";
import { advanceReviewProgress, REVIEW_TIMEOUT_MS, type ReviewProgress } from "@/lib/review-progress";

type Target = {
  profileId: string;
  profileVersion: number;
  canReview: boolean;
  draftId: string | null;
  locale: ResumeTrack;
  elevationLevel: "conservative" | "standard" | "elevated";
};

/** Owned by ResumeStudio, not a step: navigation never starts another model call. */
export function useResumeQualityReview({ profileId, profileVersion, canReview, draftId, locale, elevationLevel }: Target) {
  const targetKey = JSON.stringify([profileId, profileVersion, draftId, locale, elevationLevel, canReview]);
  const [stateKey, setStateKey] = useState(targetKey);
  const [review, setReview] = useState<ExportReview | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  // Set when the user has read blocking findings and chosen to download anyway.
  const [acknowledged, setAcknowledged] = useState(false);
  // Waiting is optional; skipping cancels this request as well as unlocking download.
  const [skipped, setSkipped] = useState(false);
  const [reviewProgress, setReviewProgress] = useState<ReviewProgress>({});
  const [reviewStartedAt, setReviewStartedAt] = useState<number | null>(null);
  const reviewAbortRef = useRef<AbortController | null>(null);
  const reviewRequestRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);

  const cancelReview = useCallback(() => {
    ++reviewRequestRef.current;
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    reviewAbortRef.current?.abort();
    reviewAbortRef.current = null;
  }, []);

  const runReview = useCallback(async () => {
    if (!canReview || !draftId) return;
    cancelReview();
    const requestId = ++reviewRequestRef.current;
    const controller = new AbortController();
    reviewAbortRef.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), REVIEW_TIMEOUT_MS);
    timeoutRef.current = timeout;
    setReviewBusy(true);
    setReview(null);
    setAcknowledged(false);
    setReviewError(null);
    setReviewProgress({});
    setReviewStartedAt(Date.now());
    setSkipped(false);
    try {
      const res = await reviewBeforeExport(profileId, elevationLevel, locale, draftId, {
        signal: controller.signal,
        onProgress: (event) => {
          if (requestId === reviewRequestRef.current) {
            setReviewProgress((current) => advanceReviewProgress(current, event));
          }
        },
      });
      if (requestId === reviewRequestRef.current) setReview(res);
    } catch (err) {
      if (requestId !== reviewRequestRef.current) return;
      setReview(null);
      setReviewError(controller.signal.aborted
        ? "内容检查等待超时，本次未完成核对。你可以重试，也可以继续导出。"
        : userFacingExportError(err));
    } finally {
      window.clearTimeout(timeout);
      if (requestId === reviewRequestRef.current) {
        reviewAbortRef.current = null;
        timeoutRef.current = null;
        setReviewBusy(false);
        setReviewStartedAt(null);
      }
    }
  }, [cancelReview, canReview, profileId, profileVersion, elevationLevel, locale, draftId]);

  // The check always reflects the draft currently selected in step 3.
  useEffect(() => {
    cancelReview();
    setStateKey(targetKey);
    setReviewBusy(false);
    setReviewError(null);
    setReview(null);
    setReviewProgress({});
    setReviewStartedAt(null);
    // A new draft has not been read yet, so a previous acknowledgement does not carry.
    setAcknowledged(false);
    setSkipped(false);
    // React StrictMode intentionally mounts effects twice in development. Starting the
    // SSE request directly here made one draft launch two expensive reviewer calls; the
    // first was aborted only after it had already reached the model. Schedule one turn
    // later so the probe mount is cancelled before any network request is created.
    let scheduled: number | null = null;
    if (canReview && draftId) {
      scheduled = window.setTimeout(() => void runReview(), 0);
    }
    return () => {
      if (scheduled !== null) window.clearTimeout(scheduled);
      cancelReview();
    };
  }, [canReview, draftId, targetKey, runReview, cancelReview]);

  const skipReview = useCallback(() => {
    cancelReview();
    setSkipped(true);
    setReviewBusy(false);
    setReviewStartedAt(null);
  }, [cancelReview]);

  // Never show the previous draft's result, even on the render before effects run.
  const current = stateKey === targetKey;
  return {
    review: current ? review : null,
    reviewBusy: current && reviewBusy,
    reviewError: current ? reviewError : null,
    acknowledged: current && acknowledged,
    skipped: current && skipped,
    reviewProgress: current ? reviewProgress : {},
    reviewStartedAt: current ? reviewStartedAt : null,
    runReview, skipReview, setAcknowledged,
  };
}

export type ResumeQualityReview = ReturnType<typeof useResumeQualityReview>;
