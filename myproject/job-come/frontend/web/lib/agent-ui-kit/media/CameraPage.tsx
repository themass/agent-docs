"use client";


import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";

import {
  captureVideoFrame,
  hasGetUserMedia,
  mediaErrorMessage,
  openCameraStream,
  shouldMirrorPreview,
  stopMediaStream,
  videoInputCount,
  type CameraFacing,
} from "../camera-capture";
import type { AgentCameraLabels } from "../types";

type Phase = "live" | "review" | "blocked";

const PANEL_WIDTH = 280;
const VIEWPORT_PAD = 10;

function defaultPanelPosition(): { x: number; y: number } {
  if (typeof window === "undefined") return { x: 12, y: 48 };
  return { x: Math.max(VIEWPORT_PAD, window.innerWidth - PANEL_WIDTH - 12), y: 48 };
}

function clampPanelPosition(x: number, y: number, width: number, height: number): { x: number; y: number } {
  if (typeof window === "undefined") return { x, y };
  const maxX = Math.max(VIEWPORT_PAD, window.innerWidth - width - VIEWPORT_PAD);
  const maxY = Math.max(VIEWPORT_PAD, window.innerHeight - height - VIEWPORT_PAD);
  return {
    x: Math.min(Math.max(VIEWPORT_PAD, x), maxX),
    y: Math.min(Math.max(VIEWPORT_PAD, y), maxY),
  };
}

export function CameraPage({
  onClose,
  onUse,
  labels,
}: {
  onClose: () => void;
  onUse: (dataUrl: string) => void;
  labels: AgentCameraLabels;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ originX: number; originY: number; startX: number; startY: number } | null>(null);
  const [offset, setOffset] = useState(defaultPanelPosition);
  // Guards against overlapping `startCamera` calls. React 18's Strict Mode runs effects
  // twice in dev (mount, cleanup, mount again), so without this a stale call's
  // `getUserMedia` can resolve *after* a newer call has already swapped `video.srcObject`
  // out from under it - the newer call's `video.play()` promise then rejects with
  // "the play() request was interrupted because the media was removed from the
  // document", and the stale call's own stream is never stopped (its track stays live,
  // which is why the camera can appear stuck/busy on the next open). Each call captures
  // the token it was issued; if the token has moved on by the time `getUserMedia`
  // resolves, the call stops the stream it just opened and touches nothing else.
  const startTokenRef = useRef(0);
  const [phase, setPhase] = useState<Phase>("live");
  const [facing, setFacing] = useState<CameraFacing>("user");
  const [ready, setReady] = useState(false);
  const [canFlip, setCanFlip] = useState(false);
  const [shot, setShot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mirrored = shouldMirrorPreview(facing);
  const supported = hasGetUserMedia();

  function onDragStart(event: ReactPointerEvent<HTMLDivElement>): void {
    if (event.button !== 0) return;
    event.preventDefault();
    dragRef.current = {
      originX: offset.x,
      originY: offset.y,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onDragMove(event: ReactPointerEvent<HTMLDivElement>): void {
    const drag = dragRef.current;
    if (!drag) return;
    const panel = panelRef.current;
    const width = panel?.offsetWidth ?? PANEL_WIDTH;
    const height = panel?.offsetHeight ?? 320;
    const next = clampPanelPosition(
      drag.originX + event.clientX - drag.startX,
      drag.originY + event.clientY - drag.startY,
      width,
      height,
    );
    setOffset(next);
  }

  function onDragEnd(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!dragRef.current) return;
    dragRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function release(): void {
    stopMediaStream(streamRef.current);
    streamRef.current = null;
    const video = videoRef.current;
    if (video) video.srcObject = null;
  }

  async function startCamera(nextFacing: CameraFacing): Promise<void> {
    if (!supported) {
      setPhase("blocked");
      setError(labels.unsupported);
      return;
    }
    // Claim this call's token *before* the first await. A call started after this one
    // bumps the ref past this value, so when this call resumes it can tell it has been
    // superseded without any shared mutable state besides the one counter.
    const token = ++startTokenRef.current;
    setBusy(true);
    setError(null);
    release();
    try {
      const stream = await openCameraStream(nextFacing);
      if (token !== startTokenRef.current) {
        // Superseded while `getUserMedia` was pending. The newer call already owns
        // `videoRef`/`streamRef`; this stream was never attached anywhere, so stopping
        // it here is the only chance to release the camera device.
        stopMediaStream(stream);
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      if (token !== startTokenRef.current) {
        // Superseded while `play()` was pending (the race the error toast reported).
        // The newer call has since called `release()`, which already stopped this
        // call's stream and cleared `srcObject` - nothing left to undo.
        return;
      }
      setFacing(nextFacing);
      setReady(true);
      setPhase("live");
      const count = await videoInputCount();
      if (token !== startTokenRef.current) return;
      setCanFlip(count > 1);
    } catch (err) {
      // A `play()` aborted by a newer call's `release()` lands here too (its own
      // AbortError, not the newer call's business) - the token check keeps it from
      // reporting a fake failure over whatever the newer call is doing.
      if (token !== startTokenRef.current) return;
      setPhase("blocked");
      setError(mediaErrorMessage(err));
      setReady(false);
    } finally {
      if (token === startTokenRef.current) setBusy(false);
    }
  }

  useEffect(() => {
    void startCamera("user");
    return () => {
      // Bump the token so a call already in flight (Strict Mode's extra mount/cleanup
      // pass, or an unmount while `getUserMedia`/`play()` is pending) finds itself
      // superseded on the way out and stops its own stream instead of attaching it to
      // a `videoRef` that may already point at a different element.
      startTokenRef.current += 1;
      release();
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (phase === "review") {
          setShot(null);
          setPhase("live");
          return;
        }
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, phase]);

  function shutter(): void {
    const video = videoRef.current;
    if (!video) return;
    try {
      const dataUrl = captureVideoFrame(video, mirrored);
      setShot(dataUrl);
      setPhase("review");
      release();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : labels.captureFailed);
    }
  }

  const panel = (
    <div
      ref={panelRef}
      className="fixed z-[9998] flex max-h-[85vh] flex-col overflow-hidden rounded-2xl border border-ink-200 bg-ink-900 shadow-2xl"
      style={{ width: PANEL_WIDTH, left: offset.x, top: offset.y }}
    >
      <div
        className="flex cursor-grab touch-none items-center justify-between border-b border-white/10 px-3 py-2 active:cursor-grabbing"
        onPointerDown={onDragStart}
        onPointerMove={onDragMove}
        onPointerUp={onDragEnd}
        onPointerCancel={onDragEnd}
        title={labels.dragPanelTitle}
      >
        <span className="flex items-center gap-1.5 text-xs font-medium text-white">
          <svg className="size-3.5 text-white/50" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <circle cx="5" cy="7" r="1.5" />
            <circle cx="12" cy="7" r="1.5" />
            <circle cx="19" cy="7" r="1.5" />
            <circle cx="5" cy="12" r="1.5" />
            <circle cx="12" cy="12" r="1.5" />
            <circle cx="19" cy="12" r="1.5" />
          </svg>
          {labels.panelTitle}
        </span>
        <button type="button" className="text-white/70 hover:text-white" onClick={onClose} aria-label={labels.closeAria}>
          ✕
        </button>
      </div>

      {phase === "blocked" ? (
        <div className="space-y-2 p-4 text-center text-xs text-white/80">
          <p>{error ?? labels.blockedFallback}</p>
          <button
            type="button"
            className="rounded-full bg-white/10 px-3 py-1 text-white hover:bg-white/20"
            onClick={() => void startCamera(facing)}
          >
            {labels.retry}
          </button>
        </div>
      ) : phase === "review" && shot ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2 p-2">
          <img src={shot} alt={labels.previewAlt} className="min-h-0 flex-1 rounded-xl object-contain" />
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              className="flex-1 rounded-xl bg-white/10 py-2 text-xs text-white hover:bg-white/20"
              onClick={() => {
                setShot(null);
                void startCamera(facing);
              }}
            >
              {labels.retake}
            </button>
            <button
              type="button"
              className="flex-1 rounded-xl bg-brand-600 py-2 text-xs text-white hover:bg-brand-700"
              onClick={() => onUse(shot)}
            >
              {labels.useThisShot}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden bg-black">
            <video
              ref={videoRef}
              playsInline
              muted
              className={`absolute inset-0 size-full object-cover ${mirrored ? "-scale-x-100" : ""}`}
            />
            {!ready ? (
              <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-xs text-white">
                {busy ? labels.opening : labels.preparingPreview}
              </div>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2 p-2">
            {/* Equal-width flex slots either side of the shutter, not a fixed-width
                spacer: a bare `<span />` on the left (when `canFlip` is false) had no
                width to match the right-hand spacer, so the shutter button in the
                middle drifted off-center. `flex-1` keeps both slots equal regardless
                of whether the flip button's label is short or long. */}
            <div className="flex flex-1 justify-start">
              {canFlip ? (
                <button
                  type="button"
                  className="rounded-full bg-white/10 px-2.5 py-1 text-xs text-white hover:bg-white/20"
                  onClick={() => void startCamera(facing === "user" ? "environment" : "user")}
                >
                  {labels.flip}
                </button>
              ) : null}
            </div>
            <button
              type="button"
              disabled={!ready}
              className="inline-flex size-12 shrink-0 items-center justify-center rounded-full border-4 border-white bg-white/20 text-white disabled:opacity-40"
              onClick={shutter}
              aria-label={labels.shutterAria}
            >
              <span className="size-8 rounded-full bg-white" />
            </button>
            <div className="flex-1" />
          </div>
        </div>
      )}
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(panel, document.body);
}
