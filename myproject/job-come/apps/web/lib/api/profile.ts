import { apiJson } from "./client";

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
  description?: string | null;
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
  parse_error?: string | null;
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

export function uploadProfile(file: File): Promise<Profile> {
  const form = new FormData();
  form.append("file", file);
  return apiJson<Profile>("/profiles/upload", { method: "POST", body: form });
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
