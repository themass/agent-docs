import { apiJson } from "./client";
import {
  isSourceParseSettled,
  PROFILE_PARSE_POLL_MS,
} from "@/lib/profile-parse";

export type ProfileLink = { type: string; url: string };

export type ProfileContact = {
  name: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  links?: ProfileLink[];
};

export type ProfileExperience = {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date?: string | null;
  location?: string | null;
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
  const form = new FormData();
  form.append("file", file);
  return apiJson<Profile>("/profiles/upload", { method: "POST", body: form });
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

export function activateProfile(profileId: string): Promise<Profile> {
  return apiJson<Profile>(`/profiles/${profileId}/activate`, { method: "POST" });
}
