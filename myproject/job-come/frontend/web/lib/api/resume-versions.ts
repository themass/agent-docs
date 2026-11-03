import { API_BASE, apiJson } from "./client";

export type ResumeVersionExport = {
  id: string;
  format: "pdf" | "docx" | "html";
  status: "pending" | "processing" | "done" | "failed";
  completed_at: string | null;
  download_url: string | null;
  error_message: string | null;
};

export type ResumeVersionItem = {
  id: string;
  created_at: string;
  job: { id: string; title: string; company: string } | null;
  elevation_level: "conservative" | "standard" | "elevated";
  locale: string;
  template_id: string;
  reviewer_status: "pending" | "passed" | "failed";
  exports: ResumeVersionExport[];
};

export type ResumeVersionGroup = {
  profile_id: string;
  contact_name: string | null;
  is_active: boolean;
  versions: ResumeVersionItem[];
};

export type ResumeVersionList = { groups: ResumeVersionGroup[] };

export function listResumeVersions(): Promise<ResumeVersionList> {
  return apiJson<ResumeVersionList>("/resume-versions");
}

export function deleteResumeVersion(draftId: string): Promise<void> {
  return apiJson<void>(`/resume-versions/${draftId}`, { method: "DELETE" });
}

/** A same-origin URL the browser opens with the session cookie; the response is sandboxed. */
export function resumeVersionViewUrl(draftId: string): string {
  return `${API_BASE}/resume-versions/${draftId}/html`;
}
