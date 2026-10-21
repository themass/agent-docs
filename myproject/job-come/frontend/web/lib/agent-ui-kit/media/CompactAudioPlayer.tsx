"use client";

import { useEffect, useRef, useState } from "react";

import type { AgentAudioPlayerLabels } from "../types";

/**
 * One-row audio player: play/pause, a thin progress bar, elapsed/total time.
 *
 * Replaces `<audio controls>`. The native widget renders a full transport (seek bar,
 * volume slider, playback-rate menu) at a fixed height Chrome and Safari do not agree
 * on, and neither can be made shorter with CSS — the control surface is drawn by the
 * browser's own UA shadow DOM, not by markup this file owns. In a chat composer that
 * is screen space the resume/profile content next to it does not get back; a voice
 * clip only needs replay and a time readout, so this draws exactly that in a fixed,
 * predictable height instead.
 */
export function CompactAudioPlayer({
  src,
  labels,
  className = "",
}: {
  src: string;
  labels: AgentAudioPlayerLabels;
  className?: string;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);
  const [totalMs, setTotalMs] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrentMs(audio.currentTime * 1000);
    const onMeta = () => {
      // A webm/opus clip from MediaRecorder commonly reports `Infinity` here until the
      // browser has actually read through the stream once; a finite but wrong-looking
      // number only after `durationchange` settles is a real duration, not a glitch.
      if (Number.isFinite(audio.duration)) setTotalMs(audio.duration * 1000);
    };
    const onEnd = () => {
      setPlaying(false);
      setCurrentMs(0);
    };
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("durationchange", onMeta);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("play", () => setPlaying(true));
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("durationchange", onMeta);
      audio.removeEventListener("ended", onEnd);
    };
  }, [src]);

  function toggle(): void {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) void audio.play().catch(() => undefined);
    else audio.pause();
  }

  function seek(event: React.MouseEvent<HTMLDivElement>): void {
    const audio = audioRef.current;
    if (!audio || !totalMs) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    audio.currentTime = (ratio * totalMs) / 1000;
  }

  function fmt(ms: number): string {
    const total = Math.round(ms / 1000);
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  const progress = totalMs > 0 ? Math.min(1, currentMs / totalMs) : 0;

  return (
    <div className={`flex min-w-0 items-center gap-2 ${className}`}>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption -- a voice memo has no track to caption; the transcript beside this player is the equivalent. */}
      <audio ref={audioRef} src={src} preload="metadata" className="hidden" />
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? labels.pause : labels.play}
        className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ink-900 text-white"
      >
        {playing ? (
          <svg viewBox="0 0 16 16" className="size-3" fill="currentColor" aria-hidden>
            <rect x="3" y="2" width="3.5" height="12" rx="0.5" />
            <rect x="9.5" y="2" width="3.5" height="12" rx="0.5" />
          </svg>
        ) : (
          <svg viewBox="0 0 16 16" className="size-3" fill="currentColor" aria-hidden>
            <path d="M4 2.5v11l10-5.5-10-5.5z" />
          </svg>
        )}
      </button>
      <div
        className="relative h-1.5 min-w-0 flex-1 cursor-pointer rounded-full bg-ink-300/70"
        onClick={seek}
        role="slider"
        aria-label={labels.progressAria}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-ink-600"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
      <span className="shrink-0 text-micro tabular-nums text-ink-500">
        {fmt(currentMs)}/{totalMs ? fmt(totalMs) : "--:--"}
      </span>
    </div>
  );
}
