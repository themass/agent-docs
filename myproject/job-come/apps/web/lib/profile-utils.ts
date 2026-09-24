import type { ProfileExperience, ProfilePayload } from "@/lib/api/profile";

export function formatDateRange(start: string | null | undefined, end?: string | null): string {
  const s = (start ?? "").trim();
  const e = (end ?? "").trim();
  if (!s && !e) return "时间待补充";
  if (!e || e === "至今" || e.toLowerCase() === "present") return `${s} — 至今`;
  return `${s} — ${e}`;
}

export function estimateYears(experiences: ProfileExperience[]): number | null {
  const years: number[] = [];
  for (const exp of experiences) {
    const start = parseYear(exp.start_date);
    const end = parseYear(exp.end_date) ?? new Date().getFullYear();
    if (start && end >= start) years.push(end - start);
  }
  if (!years.length) return null;
  return Math.max(1, Math.round(years.reduce((a, b) => a + b, 0)));
}

function parseYear(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const m = raw.match(/(19|20)\d{2}/);
  return m ? Number(m[0]) : null;
}

export function isParseDraft(summary: string | null | undefined): boolean {
  return Boolean(summary?.includes("解析草稿") || summary?.includes("请核对"));
}

export function headlineFromProfile(payload: ProfilePayload): string {
  const latest = payload.experiences[0];
  if (latest?.title && latest?.company) return `${latest.title} · ${latest.company}`;
  if (latest?.title) return latest.title;
  return "求职者";
}

export function parseStatusLabel(status: string): { label: string; tone: "ok" | "warn" | "pending" } {
  const s = status.toLowerCase();
  if (s === "done" || s === "parsed" || s === "success") return { label: "解析完成", tone: "ok" };
  if (s === "failed" || s === "error") return { label: "解析失败", tone: "warn" };
  return { label: "解析中", tone: "pending" };
}
