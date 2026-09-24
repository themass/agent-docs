"use client";

export function VoiceCard({
  src,
  compact,
  bubble,
  onClear,
}: {
  src?: string;
  compact?: boolean;
  bubble?: boolean;
  onClear?: () => void;
}) {
  if (!src) return null;

  if (bubble) {
    return (
      <div className="flex items-center gap-2 border-b border-neutral-200/70 bg-neutral-200/40 px-3 py-2">
        <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-white/80 text-neutral-600 shadow-sm">
          🎤
        </span>
        <audio src={src} controls preload="metadata" className="min-w-0 flex-1" />
        <span className="shrink-0 text-[10px] text-neutral-500">语音</span>
      </div>
    );
  }

  return (
    <div
      className={
        compact
          ? "relative min-w-[168px] max-w-[240px] rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5"
          : "relative w-full rounded-xl bg-neutral-200/70 px-3 py-2"
      }
    >
      <audio src={src} controls preload="metadata" className="w-full" />
      {onClear ? (
        <button
          type="button"
          className="absolute -right-1.5 -top-1.5 inline-flex size-4 items-center justify-center rounded-full bg-slate-900 text-[10px] text-white"
          onClick={onClear}
          aria-label="移除语音"
        >
          ✕
        </button>
      ) : null}
    </div>
  );
}
