"use client";

type Props = {
  interim: string;
  transcript: string;
  onCancel: () => void;
  onFinish: () => void;
};

export function VoiceCaptureBar({ interim, transcript, onCancel, onFinish }: Props) {
  const live = [transcript.trim(), interim.trim()].filter(Boolean).join(" ");
  const bars = [0.35, 0.65, 0.45, 0.85, 0.5, 0.75, 0.4, 0.6];

  return (
    <div
      className="mb-2 overflow-hidden rounded-2xl border border-red-200/80 bg-red-50/90 px-3 py-2.5 shadow-[0_4px_20px_rgba(239,68,68,0.08)]"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <span className="relative flex size-2.5 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-60" />
          <span className="relative inline-flex size-2.5 rounded-full bg-red-500" />
        </span>
        <svg className="size-3.5 shrink-0 text-red-600" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path strokeLinecap="round" strokeWidth={2} d="M12 14a3 3 0 003-3V7a3 3 0 10-6 0v4a3 3 0 003 3zm7-1v1a7 7 0 01-14 0v-1M12 19v3" />
        </svg>
        <p className="min-w-0 flex-1 text-[12px] font-medium text-red-800">正在聆听…</p>
        <div className="flex h-4 items-end gap-0.5" aria-hidden>
          {bars.map((height, index) => (
            <span
              key={index}
              className="w-0.5 animate-pulse rounded-full bg-red-400/90"
              style={{ height: `${Math.round(height * 100)}%`, animationDelay: `${index * 90}ms` }}
            />
          ))}
        </div>
      </div>

      <p className="mt-2 min-h-[1.25rem] text-[13px] leading-relaxed text-neutral-800">
        {live ? (
          <>
            {transcript.trim() ? <span>{transcript.trim()}</span> : null}
            {interim.trim() ? (
              <span className={transcript.trim() ? "text-neutral-500" : "text-neutral-800"}>
                {interim.trim()}
              </span>
            ) : null}
            {interim.trim() ? (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-red-500 align-middle" />
            ) : null}
          </>
        ) : (
          <span className="text-neutral-500">请开始说话，识别文字会出现在这里</span>
        )}
      </p>

      <p className="mt-1 text-[10px] text-red-700/80">再次点击麦克风或点「完成」结束录音</p>

      <div className="mt-2 flex items-center justify-end gap-2">
        <button
          type="button"
          className="rounded-full px-3 py-1 text-[12px] text-neutral-600 hover:bg-white/70"
          onClick={onCancel}
        >
          取消
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-full bg-red-600 px-3 py-1 text-[12px] font-medium text-white hover:bg-red-700"
          onClick={onFinish}
        >
          完成
        </button>
      </div>
    </div>
  );
}
