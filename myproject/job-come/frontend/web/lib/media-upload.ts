/**
 * Direct-upload client for chat attachments (ADR-011 §6-C).
 *
 * The contract the rest of the app gets: `tryDirectUpload(blob, mime)` returns
 * an object key when the bytes are verifiably in the bucket, or `null` when
 * the direct channel is not available (disabled server, CORS not configured,
 * browser offline, mime outside the scene whitelist). `null` is NOT a failure
 * to show the user — the `data_url` channel stays alive as the degradation
 * path (ADR-011 §6-A), so the turn works either way and the composer never
 * has to reason about why.
 *
 * Two rules this file owns:
 * - A presigned PUT URL is a bearer secret (§7.4): never logged, never
 *   surfaced in errors, never kept on the attachment object. Only the key
 *   travels onward.
 * - The key is consumed at bind. One key = one message. Anything that
 *   re-sends an attachment (retry) MUST re-upload under a fresh key, which is
 *   what `refreshLiveUploads` is for.
 */

import { apiJson } from "@/lib/api/client";
import type { AgentAttachment } from "@/lib/types/agent";

export type DirectUploadScene = "chat-image" | "chat-audio" | "profile-source";

/** Mirrors `media_scene.py` whitelists; keep in step. A mime the server would
 * reject at sign must degrade to inline HERE rather than round-trip a 400. */
const IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/heic",
]);
const AUDIO_TYPES = new Set([
  "audio/webm",
  "audio/ogg",
  "audio/opus",
  "audio/mp4",
  "audio/aac",
  "audio/mpeg",
  "audio/wav",
]);

/** The `profile-source` scene whitelist (ADR-011 §4): photo resumes plus
 * documents. Mirrors `media_scene.py` (`_IMAGE_TYPES | _DOC_TYPES`) minus
 * gif/heic, which the resume uploader's own accept list has never taken. A
 * mime the server would refuse at sign degrades to multipart HERE rather
 * than round-tripping a 400 — same net effect, one less red line in prod. */
export const PROFILE_SOURCE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]);

function baseMime(mime: string): string {
  return (mime.split(";")[0] ?? "").trim().toLowerCase();
}

export function sceneForMime(mime: string | null | undefined): DirectUploadScene | null {
  const base = baseMime(mime ?? "");
  if (IMAGE_TYPES.has(base)) return "chat-image";
  if (AUDIO_TYPES.has(base)) return "chat-audio";
  return null;
}

/** Any sign/PUT failure surfaces as this; callers that degrade catch it. */
export class DirectUploadUnavailable extends Error {}

type SignResponse = {
  objectKey: string;
  upload: { method: string; url: string; headers: Record<string, string> };
};

/**
 * sign → PUT. Throws `DirectUploadUnavailable` on any failure in either leg
 * (including a non-whitelisted mime — callers should prefer `sceneForMime`).
 * Returns the object key; the signed URL is dropped here and never escapes.
 */
export async function directUpload(
  scene: DirectUploadScene,
  blob: Blob,
  contentType: string,
): Promise<string> {
  const signedBase = baseMime(contentType);
  let signed: SignResponse;
  try {
    signed = await apiJson<SignResponse>("/media/sign", {
      method: "POST",
      body: JSON.stringify({ scene, contentType: signedBase, sizeBytes: blob.size }),
    });
  } catch (error) {
    throw new DirectUploadUnavailable("直传签发失败", { cause: error });
  }
  try {
    // No `credentials`: the signature in the URL IS the authorization.
    const res = await fetch(signed.upload.url, {
      method: signed.upload.method || "PUT",
      headers: signed.upload.headers,
      body: blob,
    });
    if (!res.ok) throw new Error(`PUT ${res.status}`);
  } catch (error) {
    throw new DirectUploadUnavailable("直传失败", { cause: error });
  }
  return signed.objectKey;
}

/**
 * The degrade-friendly wrapper everything in the UI calls. `null` means
 * "upload the old way" — a typed upload failure, nothing else. A genuinely
 * unexpected bug still throws, so a coding mistake never silently becomes
 * "every user just gets the slow path forever".
 */
export async function tryDirectUpload(blob: Blob, contentType: string): Promise<string | null> {
  const scene = sceneForMime(contentType);
  if (!scene) return null;
  try {
    return await directUpload(scene, blob, contentType);
  } catch (error) {
    if (error instanceof DirectUploadUnavailable) return null;
    throw error;
  }
}

/** base64 `data:` URL → Blob. `atob` exists in browser and node alike, so the
 * retry path below is testable without a DOM. Null on any malformed input. */
export function dataUrlToBlob(dataUrl: string): Blob | null {
  if (!dataUrl.startsWith("data:")) return null;
  const comma = dataUrl.indexOf(",");
  if (comma < 0) return null;
  const header = dataUrl.slice("data:".length, comma);
  if (!header.includes("base64")) return null;
  const mime = baseMime(header.split(";")[0] ?? "") || "application/octet-stream";
  let bin: string;
  try {
    bin = atob(dataUrl.slice(comma + 1));
  } catch {
    return null;
  }
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

/**
 * PUT every media attachment's staged bytes and return copies with FRESH keys.
 *
 * Called once per send attempt, from `sendMessage`, for two reasons it must
 * not move earlier:
 * - The sign TTL is 10 minutes. A key minted at file-pick time expires while
 *   the user composes, and bind answers 410 on a photo the user can see.
 * - A key is consumed by bind, so every attempt needs its own: on retry the
 *   previous attempt's key is bound (or binding), and reusing it answers 409.
 *
 * Items keep their `data_url` in React state as preview + re-upload source;
 * the wire never carries both fields (see `toWireAttachment`).
 *
 * An item whose upload fails keeps its `data_url` and NO key: it goes out the
 * inline channel, which is the degradation ADR-011 keeps on purpose.
 * Non-media items and server-history stubs pass through untouched.
 */
export async function refreshLiveUploads(
  attachments: AgentAttachment[],
): Promise<AgentAttachment[]> {
  return Promise.all(
    attachments.map(async (att) => {
      if ((att.kind !== "image" && att.kind !== "audio") || !att.data_url) return att;
      const blob = dataUrlToBlob(att.data_url);
      if (!blob) return att;
      const objectKey = await tryDirectUpload(blob, att.mime_type ?? blob.type);
      return objectKey ? { ...att, object_key: objectKey } : att;
    }),
  );
}

/**
 * The request-body projection: with a key, the wire carries ONLY the key —
 * `data_url` and `object_key` are mutually exclusive server-side (schema
 * 422), and the preview bytes are for the bubble and for retry, not for the
 * API. Without a key the attachment is exactly what it always was.
 */
export function toWireAttachment(att: AgentAttachment): AgentAttachment {
  if (!att.object_key) return att;
  return {
    kind: att.kind,
    name: att.name,
    label: att.label ?? null,
    mime_type: att.mime_type,
    object_key: att.object_key,
    text_preview: att.text_preview,
    transcript: att.transcript,
    duration_ms: att.duration_ms,
  };
}
