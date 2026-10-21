import type { AgentDisplayItem } from "@/lib/types/agent";

export type PhotoCropRequest = {
  status: "photo_crop_required";
  session_id: string;
  profile_id: string;
  message_id: string;
  attachment_index: number;
  name: string;
};

/** Parse only structured results of the known tool, never assistant prose. */
export function latestPhotoRequest(items: AgentDisplayItem[], sessionId: string | null): PhotoCropRequest | null {
  for (const item of [...items].reverse()) {
    if (item.kind !== "tool_result" || item.name !== "jc_profile_photo_set") continue;
    try {
      const value = JSON.parse(item.result) as Partial<PhotoCropRequest>;
      if (value.status !== "photo_crop_required" || value.session_id !== sessionId ||
        typeof value.profile_id !== "string" || typeof value.message_id !== "string" ||
        typeof value.name !== "string" || typeof value.attachment_index !== "number" ||
        !Number.isInteger(value.attachment_index) || value.attachment_index < 0) return null;
      return value as PhotoCropRequest;
    } catch { return null; }
  }
  return null;
}
