import { apiJson } from "./client";
import { ApiError, USER_NETWORK_ERROR, USER_SERVICE_UNAVAILABLE } from "./errors";
import {
  isSourceParseSettled,
  PROFILE_PARSE_POLL_MS,
} from "@/lib/profile-parse";

export type ProfileLink = { type: string; url: string };

/**
 * The candidate's headshot. `storage_key` is the durable record; `download_url` is a
 * short-lived signed URL the server re-derives on every read, so it is safe to render
 * but never safe to cache.
 *
 * `enabled` is a separate switch rather than "has a key": turning the photo off keeps
 * the upload, so changing your mind does not cost another crop. Default is off, which
 * is why uploading a photo never silently changes what an export looks like.
 */
export type ProfilePhoto = {
  storage_key?: string | null;
  download_url?: string | null;
  mime_type?: string | null;
  width?: number | null;
  height?: number | null;
  /** Whether the Chinese resume draws it. */
  enabled: boolean;
  /**
   * Whether the 中英双语 version draws it too. Off by default and deliberately
   * separate from `enabled`: a bilingual document is usually read by the
   * English-market side of a process. The English-only track never draws a photo
   * at all, regardless of either flag — that rule is enforced server-side.
   */
  show_in_bilingual?: boolean;
};

export type ProfileContact = {
  name: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  links?: ProfileLink[];
  /**
   * Optional on this type only for payloads written before the field existed — the
   * server always returns it. Every editor must spread the existing `contact` when
   * saving, or a `PATCH /profiles/{id}` would drop the photo along with it.
   */
  photo?: ProfilePhoto;
};

export type ProfileExperience = {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date?: string | null;
  location?: string | null;
  /**
   * What this role covered: team size, ownership, scale. Stored as a source fact rather
   * than derived, because team size and mandate cannot be inferred from a list of
   * accomplishments — only the user knows them. Rendered as the opening line of the
   * block, which is the 先总后分 layer of the document.
   */
  scope?: string | null;
  highlights?: string[];
  skills?: string[];
  confidence?: string;
};

export type ProfileEducation = {
  id: string;
  school: string;
  degree?: string | null;
  major?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

export type ProfileSkill = {
  name: string;
  level?: string | null;
  evidence?: string[];
};

export type ProfileProject = {
  id: string;
  name: string;
  role?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
  /** Same role as `ProfileExperience.scope`: the project's size and the user's mandate. */
  scope?: string | null;
  /** Accomplishments, one per entry — same shape as ProfileExperience.highlights. */
  highlights?: string[];
};

export type ProfileMeta = {
  source_file?: string | null;
  ingest_mode?: string | null;
  confirmed_at?: string | null;
  source_locale?: string | null;
  i18n_status?: Record<string, string>;
};

export type ProfilePayload = {
  contact: ProfileContact;
  summary: string | null;
  experiences: ProfileExperience[];
  education: ProfileEducation[];
  skills?: ProfileSkill[];
  projects?: ProfileProject[];
  meta?: ProfileMeta;
};

export type ProfileSource = {
  id: string;
  file_name: string;
  storage_key: string;
  parse_status: string;
  parse_phase?: string | null;
  parse_error?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type Profile = {
  id: string;
  status: string;
  version: number;
  locale?: string;
  payload: ProfilePayload;
  sources: ProfileSource[];
  confirmed_at?: string | null;
};

export type ProfileConfirmResult = {
  id: string;
  status: string;
  version: number;
  confirmed_at: string;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function uploadProfile(file: File): Promise<Profile> {
  return uploadProfileWithProgress(file);
}

/** Upload a binary with real transport progress; fetch does not expose upload progress. */
export function uploadProfileWithProgress(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Profile> {
  const form = new FormData();
  form.append("file", file);
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1"}/profiles/upload`);
    request.withCredentials = true;
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    request.onerror = () => reject(new Error(USER_NETWORK_ERROR));
    request.onabort = () => reject(new Error(USER_NETWORK_ERROR));
    request.onload = () => {
      let body: unknown;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        body = undefined;
      }
      if (request.status < 200 || request.status >= 300) {
        const errorBody = body && typeof body === "object"
          ? body as { code?: string; message?: string; detail?: string }
          : {};
        reject(new ApiError(request.status, errorBody));
        return;
      }
      if (!body || typeof body !== "object") {
        reject(new Error(USER_SERVICE_UNAVAILABLE));
        return;
      }
      resolve(body as Profile);
    };
    request.send(form);
  });
}

/** Upload then poll until background LLM parse finishes (avoids proxy timeouts). */
export async function uploadProfileAndWait(file: File, maxWaitMs = 300_000): Promise<Profile> {
  const initial = await uploadProfile(file);
  const sourceId = initial.sources[0]?.id;
  if (!sourceId) return initial;

  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    const profile = await getProfile(initial.id);
    const source = profile.sources.find((s) => s.id === sourceId) ?? profile.sources[0];
    if (source && isSourceParseSettled(source.parse_status)) {
      return profile;
    }
    await sleep(PROFILE_PARSE_POLL_MS);
  }
  throw new Error("解析时间较长，请稍后刷新页面；后台可能仍在处理，页面会自动继续跟进。");
}

/** Poll until a specific source finishes parsing (same interval as upload wait). */
export async function waitForProfileSourceParse(
  profileId: string,
  sourceId: string,
  maxWaitMs = 300_000,
): Promise<Profile> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    const profile = await getProfile(profileId);
    const source = profile.sources.find((s) => s.id === sourceId) ?? profile.sources[0];
    if (source && isSourceParseSettled(source.parse_status)) {
      return profile;
    }
    await sleep(PROFILE_PARSE_POLL_MS);
  }
  throw new Error("解析时间较长，请稍后刷新页面；后台可能仍在处理，页面会自动继续跟进。");
}

export function getProfile(profileId: string): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}`);
}

export function updateProfile(
  profileId: string,
  payload: ProfilePayload,
  expectedVersion?: number,
): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}`, {
    method: "PATCH",
    body: JSON.stringify({ payload, expected_version: expectedVersion ?? null }),
  });
}

/**
 * Upload an already-cropped headshot. The crop happens in the browser (see
 * `PhotoCropDialog`) because framing a face needs immediate visual feedback; the
 * server still re-encodes, bounds the size, and strips metadata.
 *
 * `enabled` is sent explicitly rather than relying on the server default so the
 * caller can express "upload and show it" in one request instead of two.
 */
export function setProfilePhoto(
  profileId: string,
  file: Blob,
  enabled: boolean,
): Promise<Profile> {
  const form = new FormData();
  form.append("file", file, "headshot.jpg");
  return apiJson<Profile>(
    `/profiles/${profileId}/photo?enabled=${enabled ? "true" : "false"}`,
    { method: "PUT", body: form },
  );
}

/**
 * Flip whether the stored photo is drawn on the resume, keeping the upload.
 *
 * `showInBilingual` is omitted rather than sent as `false` when the caller is only
 * changing the Chinese switch, so toggling one cannot reset the other.
 */
export function toggleProfilePhoto(
  profileId: string,
  enabled: boolean,
  showInBilingual?: boolean,
): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}/photo`, {
    method: "PATCH",
    body: JSON.stringify(
      showInBilingual === undefined
        ? { enabled }
        : { enabled, show_in_bilingual: showInBilingual },
    ),
  });
}

/** Remove the photo from the profile entirely (a re-upload is then required). */
export function deleteProfilePhoto(profileId: string): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}/photo`, { method: "DELETE" });
}

export function confirmProfile(profileId: string): Promise<ProfileConfirmResult> {
  return apiJson<ProfileConfirmResult>(`/profiles/${profileId}/confirm`, {
    method: "POST",
  });
}

export function reopenProfile(profileId: string): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}/reopen`, {
    method: "POST",
  });
}

export type ProfileListItem = {
  id: string;
  status: string;
  contact_name: string | null;
  summary_text: string | null;
  updated_at: string;
  is_active: boolean;
};

export function listProfiles(): Promise<{ profiles: ProfileListItem[]; active_profile_id: string | null }> {
  return apiJson("/profiles");
}

export function createProfile(): Promise<Profile> {
  return apiJson<Profile>("/profiles", { method: "POST" });
}

/**
 * Build a profile from text the user pasted or typed — the third way in, next to
 * uploading a file and answering the interview.
 *
 * Returns immediately with a profile whose source is still parsing, exactly like
 * `uploadProfile`, so the caller can hand it to the same progress UI instead of
 * holding the user on a spinner for a model call that takes a minute.
 */
export function ingestProfileText(rawText: string, title?: string | null): Promise<Profile> {
  return apiJson<Profile>("/profiles/from-text", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, title: title ?? null }),
  });
}

export function activateProfile(profileId: string): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}/activate`, { method: "POST" });
}
