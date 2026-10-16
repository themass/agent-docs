"use client";

import { VoiceCard } from "@/components/agent/media/VoiceCard";
import { ZoomableImage } from "@/components/agent/media/ZoomableImage";
import type { AgentAttachment } from "@/lib/types/agent";

function FileChip({ att }: { att: AgentAttachment }) {
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
        <p className="mt-0.5 text-micro text-ink-500">{att.mime_type ?? "文件"}</p>
      )}
    </div>
  );
}

/** Rich user message bubble — naviforge-style combinations of text + images + audio + files. */
export function AgentUserBubble({
  content,
  attachments,
}: {
  content: string;
  attachments?: AgentAttachment[];
}) {
  const items = attachments ?? [];
  const images = items.filter((a) => a.kind === "image" && a.data_url);
  const audios = items.filter((a) => a.kind === "audio" && a.data_url);
  const files = items.filter((a) => a.kind === "file");
  const bodyText = content.trim();
  const hasMedia = images.length > 0 || audios.length > 0 || files.length > 0;

  return (
    <div className="flex justify-end">
      <div className="max-w-[min(88%,360px)] overflow-hidden rounded-xl rounded-br-sm bg-brand-50 text-sm leading-relaxed text-ink-800 shadow-xs ring-1 ring-inset ring-brand-100">
        {images.length > 0 ? (
          <div
            className={`grid gap-1.5 border-b border-brand-100 p-2 ${
              images.length > 1 ? "grid-cols-2" : "grid-cols-1"
            }`}
          >
            {images.map((img, i) => (
              <ZoomableImage
                key={`${img.name}-${i}`}
                src={img.data_url!}
                label={img.label ?? img.name}
                className="block overflow-hidden rounded-xl"
                imgClassName="max-h-[140px] w-full rounded-xl border border-black/5 object-cover shadow-xs"
              />
            ))}
          </div>
        ) : null}

        {audios.map((audio, i) => (
          <VoiceCard key={`${audio.name}-${i}`} src={audio.data_url!} bubble />
        ))}

        {files.map((file, i) => (
          <FileChip key={`${file.name}-${i}`} att={file} />
        ))}

        {bodyText ? (
          <div className={`px-4 py-2.5 ${hasMedia ? "border-t border-brand-100" : ""}`}>
            <p className="whitespace-pre-wrap">{bodyText}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
