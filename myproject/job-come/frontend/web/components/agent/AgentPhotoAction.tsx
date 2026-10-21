"use client";

import { useState } from "react";
import { PhotoCropDialog } from "@/components/resume/PhotoCropDialog";
import { latestPhotoRequest, type PhotoCropRequest } from "@/lib/agent/photo-action";
import { apiBlob } from "@/lib/api/client";
import { setProfilePhoto } from "@/lib/api/profile";
import { userFacingApiError } from "@/lib/api/user-error";
import { photoFileError } from "@/lib/image-crop";
import type { AgentDisplayItem } from "@/lib/types/agent";

type Props = {
  sessionId: string | null;
  items: AgentDisplayItem[];
  disabled?: boolean;
  onSaved?: () => void;
};

/** Product-specific photo action. The generic chat kit only provides a slot. */
export function AgentPhotoAction({ sessionId, items, disabled, onSaved }: Props) {
  const request = latestPhotoRequest(items, sessionId);
  const resultId = [...items].reverse().find(
    (item) => item.kind === "tool_result" && item.name === "jc_profile_photo_set",
  )?.id;
  const key = request
    ? `${resultId}:${request.session_id}:${request.message_id}:${request.attachment_index}`
    : "";
  return request ? <PhotoRequestAction key={key} request={request} disabled={disabled} onSaved={onSaved} /> : null;
}

function PhotoRequestAction({ request, disabled, onSaved }: {
  request: PhotoCropRequest; disabled?: boolean; onSaved?: () => void;
}) {
  // Dismissal is presentation-only, never a stored permission or write command.
  const [dismissed, setDismissed] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (dismissed) return null;

  async function openCrop() {
    if (!request || busy) return;
    setBusy(true); setError(null);
    try {
      const blob = await apiBlob(`/agent/sessions/${encodeURIComponent(request.session_id)}/messages/${encodeURIComponent(request.message_id)}/images/${request.attachment_index}`);
      const next = new File([blob], request.name, { type: blob.type });
      const rejection = photoFileError(next);
      if (rejection) throw new Error(rejection);
      setFile(next);
    } catch (err) { setError(userFacingApiError(err, "照片读取失败，请重试。")); }
    finally { setBusy(false); }
  }

  async function save(blob: Blob, enabled: boolean) {
    if (!request || busy) return;
    setBusy(true); setError(null);
    try {
      await setProfilePhoto(request.profile_id, blob, enabled);
      setFile(null); setDismissed(true); onSaved?.();
    } catch (err) { setError(userFacingApiError(err, "照片保存失败，请重试。")); }
    finally { setBusy(false); }
  }

  return <>
    <div className="mx-3 mb-2 shrink-0 rounded-xl border border-surface-border bg-white px-3 py-2" role="region" aria-label="设置简历头像">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 text-xs text-ink-600">照片已选好，裁剪并保存后才会设置为头像。</p>
        <button type="button" className="btn btn-sm btn-primary shrink-0" disabled={disabled || busy} onClick={openCrop}>
          {busy ? "处理中…" : "裁剪并设置头像"}
        </button>
        <button type="button" className="text-xs text-ink-500" disabled={busy} onClick={() => setDismissed(true)}>暂不设置</button>
      </div>
      {error && !file ? <p role="alert" className="mt-1 text-xs text-danger-600">{error}</p> : null}
    </div>
    {file ? <PhotoCropDialog file={file} initialEnabled={false} busy={busy} error={error}
      onCancel={() => { if (!busy) { setFile(null); setError(null); } }} onConfirm={save} /> : null}
  </>;
}
