"use client";

import { useEffect, useState } from "react";

import { getAdminProfile } from "@/lib/api/admin";
import { userFacingApiError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";
import type { Profile } from "@/lib/api/profile";

/**
 * Read-only render of a full structured profile for the admin drawer.
 *
 * Deliberately not the product's `ProfileEditor` / `ProfileStudioEditor` —
 * those are built to be edited and carry a lot of form-state machinery this
 * surface has no use for. This is support tooling: look at what a user's
 * resume actually contains, nothing is writable here.
 */
export function AdminProfileDetail({ profileId }: { profileId: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void getAdminProfile(profileId)
      .then(setProfile)
      .catch((e) => setError(userFacingApiError(e, "加载简历详情失败")))
      .finally(() => setLoading(false));
  }, [profileId]);

  if (loading) return <p className="text-sm text-ink-500">加载中…</p>;
  if (error)
    return (
      <p className="notice notice-warn text-xs" role="alert">
        {error}
      </p>
    );
  if (!profile) return null;

  const { payload } = profile;

  return (
    <div className="space-y-4">
      <section className="card grid gap-x-4 gap-y-1.5 px-3 py-2.5 text-xs text-ink-600 sm:grid-cols-2">
        <p>
          <span className="text-ink-500">姓名</span> {payload.contact.name ?? "—"}
        </p>
        <p>
          <span className="text-ink-500">邮箱</span> {payload.contact.email ?? "—"}
        </p>
        <p>
          <span className="text-ink-500">电话</span> {payload.contact.phone ?? "—"}
        </p>
        <p>
          <span className="text-ink-500">所在地</span> {payload.contact.location ?? "—"}
        </p>
      </section>

      {payload.summary ? (
        <section>
          <p className="label-meta mb-1">概述</p>
          <p className="whitespace-pre-wrap text-sm text-ink-700">{payload.summary}</p>
        </section>
      ) : null}

      <section>
        <p className="label-meta mb-2">工作经历（{payload.experiences.length}）</p>
        {payload.experiences.length === 0 ? (
          <p className="text-sm text-ink-500">没有工作经历记录。</p>
        ) : (
          <ul className="space-y-2">
            {payload.experiences.map((exp) => (
              <li key={exp.id} className="card px-3 py-2.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-ink-900">
                    {exp.company} · {exp.title}
                  </p>
                  <p className="shrink-0 text-micro text-ink-500">
                    {exp.start_date} – {exp.end_date || "至今"}
                  </p>
                </div>
                {exp.scope ? <p className="mt-1 text-xs text-ink-600">{exp.scope}</p> : null}
                {exp.highlights && exp.highlights.length > 0 ? (
                  <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-ink-700">
                    {exp.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {payload.projects && payload.projects.length > 0 ? (
        <section>
          <p className="label-meta mb-2">项目经历（{payload.projects.length}）</p>
          <ul className="space-y-2">
            {payload.projects.map((p) => (
              <li key={p.id} className="card px-3 py-2.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-ink-900">
                    {p.name}
                    {p.role ? ` · ${p.role}` : ""}
                  </p>
                  {p.start_date ? (
                    <p className="shrink-0 text-micro text-ink-500">
                      {p.start_date} – {p.end_date || "至今"}
                    </p>
                  ) : null}
                </div>
                {p.description ? <p className="mt-1 text-xs text-ink-600">{p.description}</p> : null}
                {p.highlights && p.highlights.length > 0 ? (
                  <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-ink-700">
                    {p.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <p className="label-meta mb-2">教育经历（{payload.education.length}）</p>
        {payload.education.length === 0 ? (
          <p className="text-sm text-ink-500">没有教育经历记录。</p>
        ) : (
          <ul className="space-y-1.5">
            {payload.education.map((edu) => (
              <li key={edu.id} className="card px-3 py-2">
                <p className="text-sm text-ink-800">
                  {edu.school}
                  {edu.degree ? ` · ${edu.degree}` : ""}
                  {edu.major ? ` · ${edu.major}` : ""}
                </p>
                {edu.start_date ? (
                  <p className="mt-0.5 text-micro text-ink-500">
                    {edu.start_date} – {edu.end_date || "至今"}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {payload.skills && payload.skills.length > 0 ? (
        <section>
          <p className="label-meta mb-2">技能（{payload.skills.length}）</p>
          <div className="flex flex-wrap gap-1.5">
            {payload.skills.map((s, i) => (
              <span key={i} className="badge badge-neutral">
                {s.name}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <p className="text-micro text-ink-400">
        v{profile.version} · {profile.locale ?? "—"} · {formatDateTime(profile.sources[0]?.updated_at ?? "")}
      </p>
    </div>
  );
}
