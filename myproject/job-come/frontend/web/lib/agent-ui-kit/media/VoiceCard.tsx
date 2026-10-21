"use client";

import { CompactAudioPlayer } from "./CompactAudioPlayer";
import { formatClipDuration } from "../format";
import type { AgentAudioPlayerLabels, AgentVoiceCardLabels } from "../types";

/**
 * A recorded voice clip.
 *
 * Shows the transcript, not just a player. There is no server-side speech-to-text in
 * this version, so the browser's words are the only readable form of the recording —
 * and a chat history of bare audio players is unskimmable and unsearchable. The player
 * stays for verifying what was actually said.
 *
 * `src` can legitimately be missing on a replayed turn whose upload to object storage
 * failed. In that case the words are all that survived, and they are worth more than
 * the clip was: the bubble renders them and says the recording is gone, rather than
 * disappearing and leaving the user wondering whether they ever sent anything.
 */
export function VoiceCard({
  src,
  compact,
  bubble,
  transcript,
  durationMs,
  storageError,
  onClear,
  labels,
  audioLabels,
}: {
  src?: string;
  compact?: boolean;
  bubble?: boolean;
  transcript?: string | null;
  durationMs?: number | null;
  storageError?: boolean | null;
  onClear?: () => void;
  labels: AgentVoiceCardLabels;
  audioLabels: AgentAudioPlayerLabels;
}) {
  const said = transcript?.trim() ?? "";
  if (!src && !said) return null;
  const length = formatClipDuration(durationMs);

  if (bubble) {
    return (
      <div className="border-b border-brand-100 bg-brand-50/60 px-3 py-2 last:border-b-0">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-white/80 text-micro text-ink-600 shadow-xs">
            🎤
          </span>
          {src ? (
            <CompactAudioPlayer src={src} labels={audioLabels} className="min-w-0 flex-1" />
          ) : (
            <span className="min-w-0 flex-1 text-micro text-ink-500">
              {labels.uploadFailed}{length ? `（${length}）` : ""}
            </span>
          )}
        </div>
        {said ? (
          <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-ink-800">{said}</p>
        ) : (
          <p className="mt-1.5 text-micro text-ink-500">{labels.noTranscript}</p>
        )}
      </div>
    );
  }

  return (
    <div
      className={
        compact
          ? "relative min-w-[200px] max-w-[280px] rounded-xl border border-ink-200 bg-ink-50 px-2 py-1.5"
          : "relative w-full rounded-xl bg-ink-200/70 px-3 py-2"
      }
    >
      <div className="flex items-center gap-1.5">
        {src ? (
          <CompactAudioPlayer src={src} labels={audioLabels} className="min-w-0 flex-1" />
        ) : length ? (
          <span className="text-micro text-ink-500">{length}</span>
        ) : null}
      </div>
      {/*
       * The transcript is intentionally not repeated here: in the composer, `said`
       * is already folded into the input box text the moment dictation finishes, so
       * showing it again under every clip just duplicates (and, with multiple clips
       * stacked side by side, visually resembles concatenating) the same words the
       * user already sees above. The clip stays purely a player + remove control.
       */}
      {storageError ? <p className="mt-1 text-micro text-danger-700">{labels.uploadFailed}</p> : null}
      {onClear ? (
        <button
          type="button"
          className="absolute -right-1.5 -top-1.5 inline-flex size-4 items-center justify-center rounded-full bg-ink-900 text-micro text-white"
          onClick={onClear}
          aria-label={labels.removeAria}
        >
          ✕
        </button>
      ) : null}
    </div>
  );
}
