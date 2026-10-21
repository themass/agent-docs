"use client";

import type { ReactNode } from "react";

import { attachmentSrc, type AgentUiAttachment } from "./display-items";
import { VoiceCard } from "../media/VoiceCard";
import { ZoomableImage } from "../media/ZoomableImage";
import type { AgentAudioPlayerLabels, AgentImageViewerLabels, AgentVoiceCardLabels } from "../types";
import { BUBBLE_MAX_WIDTH } from "./bubble-metrics";

/** Media copy the bubble's attachment renderers need — one bundle so call sites pass it once. */
export type AgentUserBubbleMediaLabels = {
  imageViewer: AgentImageViewerLabels;
  voiceCard: AgentVoiceCardLabels;
  audioPlayer: AgentAudioPlayerLabels;
  /** Fallback file-type label when a file attachment has no mime type. */
  fileAttachmentFallback: string;
};

function FileChip({ att, fallbackLabel }: { att: AgentUiAttachment; fallbackLabel: string }) {
  const preview = att.text_preview?.trim();
  return (
    <div className="border-b border-brand-100 px-3 py-2 last:border-b-0">
      <p className="text-xs font-medium text-ink-700">📄 {att.label ?? att.name}</p>
      {preview ? (
        <p className="mt-1 max-h-24 overflow-hidden text-micro leading-relaxed text-ink-600">
          {preview.slice(0, 400)}
          {preview.length > 400 ? "…" : ""}
        </p>
      ) : (
        <p className="mt-0.5 text-micro text-ink-500">{att.mime_type ?? fallbackLabel}</p>
      )}
    </div>
  );
}

/** Rich user message bubble — naviforge-style combinations of text + images + audio + files. */
export function AgentUserBubble({
  content,
  attachments,
  avatar,
  mediaLabels,
  failed,
  retryLabel,
  onRetry,
}: {
  content: string;
  attachments?: AgentUiAttachment[];
  /** Host-supplied user mark (mirrors the assistant's `renderAgentIcon`). Omit for no mark. */
  avatar?: ReactNode;
  mediaLabels: AgentUserBubbleMediaLabels;
  /** This message's turn ended without a reply (timeout/disconnect/error). Shows the
   * red-dot + retry affordance instead of leaving the user to retype. */
  failed?: boolean;
  retryLabel?: string;
  onRetry?: () => void;
}) {
  const items = attachments ?? [];
  // A replayed message has no `data_url` — the bytes were offloaded to storage and the
  // row carries a signed URL instead. Filtering on `data_url` alone made every photo
  // and voice clip vanish from history.
  const images = items.filter((a) => a.kind === "image" && attachmentSrc(a));
  // Not filtered on having a source: when the upload to object storage failed, the
  // transcript is all that survived, and dropping the bubble would make the user's own
  // message disappear from their history.
  const audios = items.filter(
    (a) => a.kind === "audio" && (attachmentSrc(a) || a.transcript?.trim()),
  );
  const files = items.filter((a) => a.kind === "file");
  const bodyText = content.trim();
  const hasMedia = images.length > 0 || audios.length > 0 || files.length > 0;

  return (
    // `min-w-0` on the bubble is unnecessary here (it is `w-fit` inside a
    // `justify-end` row and the max-width clamps it), but the media grid inside can
    // still report a wide intrinsic size, so the ceiling has to live on the same
    // element as `w-fit` -- which it does, below.
    <div className="flex items-start justify-end gap-2">
      {failed && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          title={retryLabel}
          aria-label={retryLabel}
          className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-danger-600 transition hover:bg-danger-50"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 0 0 4.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 0 1-15.357-2m15.357 2H15" />
          </svg>
        </button>
      ) : null}
      <div
        className={`relative w-fit break-words ${BUBBLE_MAX_WIDTH} overflow-hidden rounded-xl rounded-br-sm bg-brand-50 text-sm leading-relaxed text-ink-800 shadow-xs ring-1 ring-inset ${
          failed ? "ring-danger-300" : "ring-brand-100"
        }`}
      >
        {failed ? (
          <span
            aria-hidden
            className="absolute -right-1 -top-1 block size-2.5 rounded-full bg-danger-500 ring-2 ring-surface"
          />
        ) : null}
        {images.length > 0 ? (
          <div
            className={`grid gap-1.5 border-b border-brand-100 p-2 ${
              images.length > 1 ? "grid-cols-2" : "grid-cols-1"
            }`}
          >
            {images.map((img, i) => (
              <ZoomableImage
                key={`${img.name}-${i}`}
                src={attachmentSrc(img)!}
                label={img.label ?? img.name}
                className="block overflow-hidden rounded-xl"
                imgClassName="max-h-[140px] w-full rounded-xl border border-black/5 object-cover shadow-xs"
                labels={mediaLabels.imageViewer}
              />
            ))}
          </div>
        ) : null}

        {audios.map((audio, i) => (
          <VoiceCard
            key={`${audio.name}-${i}`}
            src={attachmentSrc(audio) ?? undefined}
            transcript={audio.transcript}
            durationMs={audio.duration_ms}
            storageError={audio.storage_error}
            bubble
            labels={mediaLabels.voiceCard}
            audioLabels={mediaLabels.audioPlayer}
          />
        ))}

        {files.map((file, i) => (
          <FileChip key={`${file.name}-${i}`} att={file} fallbackLabel={mediaLabels.fileAttachmentFallback} />
        ))}

        {bodyText ? (
          <div className={`px-4 py-2.5 ${hasMedia ? "border-t border-brand-100" : ""}`}>
            <p className="whitespace-pre-wrap">{bodyText}</p>
          </div>
        ) : null}
      </div>
      {avatar ? <div className="mt-0.5 shrink-0">{avatar}</div> : null}
    </div>
  );
}
