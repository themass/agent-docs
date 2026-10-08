"use client";

import type { Profile, ProfileEducation, ProfileExperience, ProfilePayload } from "@/lib/api/profile";
import {
  estimateYears,
  formatDateRange,
  headlineFromProfile,
  isParseDraft,
  parseStatusLabel,
} from "@/lib/profile-utils";
import { experienceLabel, type AgentUiContext, type AgentUiFocus } from "@/lib/ui-context";

type Props = {
  profile: Profile;
  compact?: boolean;
  onRelocalize?: (source: "zh-CN" | "en-US") => void;
  uiContext?: AgentUiContext | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-white/80 px-4 py-3 ring-1 ring-white/60 backdrop-blur-sm">
      <p className="text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}

function focusRing(active: boolean): string {
  return active ? "ring-2 ring-brand-500 border-brand-300" : "";
}

function ExperienceTimeline({
  items,
  focusPath,
  onUiFocus,
}: {
  items: ProfileExperience[];
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
}) {
  if (!items.length) {
    return (
      <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        未识别到工作经历。可在下方「快速编辑」补充，或让右侧 Agent 帮你整理。
      </p>
    );
  }

  return (
    <ol className="space-y-4">
      {items.map((exp, idx) => (
        <li key={exp.id || idx} className="relative pl-8">
          {idx < items.length - 1 ? (
            <span
              className="absolute left-[11px] top-8 h-[calc(100%+0.5rem)] w-px bg-gradient-to-b from-brand-300 to-transparent"
              aria-hidden
            />
          ) : null}
          <span
            className="absolute left-0 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white ring-4 ring-brand-50"
            aria-hidden
          >
            {idx + 1}
          </span>
          <div
            data-path={`experiences[${idx}]`}
            role="button"
            tabIndex={0}
            onClick={() =>
              onUiFocus?.({
                path: `experiences[${idx}]`,
                kind: "experience",
                label: experienceLabel(exp.company, exp.title),
              })
            }
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onUiFocus?.({
                  path: `experiences[${idx}]`,
                  kind: "experience",
                  label: experienceLabel(exp.company, exp.title),
                });
              }
            }}
            className={`cursor-pointer rounded-xl border border-surface-border bg-white p-4 shadow-sm transition hover:border-brand-200 hover:shadow-card ${focusRing(focusPath === `experiences[${idx}]` || (focusPath?.startsWith(`experiences[${idx}].`) ?? false))}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h4 className="font-semibold text-slate-900">{exp.title || "职位待补充"}</h4>
                <p className="text-sm font-medium text-brand-700">{exp.company || "公司待补充"}</p>
              </div>
              <time className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {formatDateRange(exp.start_date, exp.end_date)}
              </time>
            </div>
            {exp.location ? <p className="mt-1 text-xs text-slate-400">{exp.location}</p> : null}
            {exp.highlights?.length ? (
              <ul className="mt-3 space-y-1.5">
                {exp.highlights.map((h, i) => {
                  const path = `experiences[${idx}].highlights[${i}]`;
                  return (
                    <li
                      key={i}
                      data-path={path}
                      className={`-mx-1 flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-slate-700 hover:bg-brand-50 ${
                        focusPath === path ? "bg-brand-50" : ""
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onUiFocus?.({
                          path,
                          kind: "highlight",
                          label: `${experienceLabel(exp.company, exp.title)} · 要点 ${i + 1}`,
                          excerpt: h,
                        });
                      }}
                    >
                      <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand-400" aria-hidden />
                      <span>{h}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-sm italic text-slate-400">暂无要点描述</p>
            )}
            {exp.skills?.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {exp.skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-md bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700"
                  >
                    {s}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function EducationList({
  items,
  focusPath,
  onUiFocus,
}: {
  items: ProfileEducation[];
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map((edu, idx) => {
        const path = `education[${idx}]`;
        return (
        <div
          key={edu.id}
          data-path={path}
          role="button"
          tabIndex={0}
          onClick={() =>
            onUiFocus?.({
              path,
              kind: "education",
              label: [edu.school, edu.degree, edu.major].filter(Boolean).join(" · ") || "教育经历",
            })
          }
          className={`cursor-pointer rounded-xl border border-surface-border bg-white p-4 shadow-sm ${focusRing(focusPath === path)}`}
        >
          <p className="font-medium text-slate-900">{edu.school}</p>
          <p className="mt-1 text-sm text-slate-600">
            {[edu.degree, edu.major].filter(Boolean).join(" · ") || "学历信息待补充"}
          </p>
          <p className="mt-2 text-xs text-slate-400">
            {formatDateRange(edu.start_date, edu.end_date)}
          </p>
        </div>
        );
      })}
    </div>
  );
}

function SkillsCloud({
  payload,
  active,
  onUiFocus,
}: {
  payload: ProfilePayload;
  active?: boolean;
  onUiFocus?: (focus: AgentUiFocus) => void;
}) {
  const fromList = payload.skills?.map((s) => s.name) ?? [];
  const fromExp = payload.experiences.flatMap((e) => e.skills ?? []);
  const unique = [...new Set([...fromList, ...fromExp].filter(Boolean))];
  if (!unique.length) return null;

  return (
    <div
      data-path="skills"
      role="button"
      tabIndex={0}
      onClick={() => onUiFocus?.({ path: "skills", kind: "skills", label: "技能" })}
      className={`flex flex-wrap gap-2 rounded-xl p-1 ${active ? "ring-2 ring-brand-500" : ""}`}
    >
      {unique.map((name) => (
        <span
          key={name}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
        >
          {name}
        </span>
      ))}
    </div>
  );
}

export function ProfileOverview({
  profile,
  compact = false,
  onRelocalize,
  uiContext = null,
  onUiFocus,
}: Props) {
  const payload = profile.payload;
  const contact = payload.contact;
  const source = profile.sources[0];
  const years = estimateYears(payload.experiences);
  const draft = isParseDraft(payload.summary);
  const status = source ? parseStatusLabel(source.parse_status) : null;
  const parseWarning = source?.parse_error;
  const sourceLocale = payload.meta?.source_locale || profile.locale || "zh-CN";

  if (compact) {
    return (
      <section className="rounded-xl border border-surface-border bg-gradient-to-r from-brand-900 to-brand-700 p-4 text-white shadow-sm">
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          {status ? (
            <span className="rounded-full bg-white/15 px-2 py-0.5">{status.label}</span>
          ) : null}
          <span className="rounded-full bg-white/15 px-2 py-0.5">v{profile.version}</span>
          <span className="rounded-full bg-white/15 px-2 py-0.5">
            {profile.status === "confirmed" ? "已确认" : "草稿"}
          </span>
        </div>
        <h2 className="mt-2 text-lg font-bold">{contact.name || "姓名待填写"}</h2>
        <p className="text-sm text-white/85">{headlineFromProfile(payload)}</p>
        <p className="mt-2 text-xs text-white/70">
          {payload.experiences.length} 段经历 · {payload.education.length} 段教育
          {years != null ? ` · 约 ${years} 年` : ""}
        </p>
        {parseWarning ? (
          <p className="mt-2 text-xs text-amber-200">{parseWarning}</p>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-6">
      {parseWarning ? (
        <div
          className="flex gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="alert"
        >
          <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p className="font-medium">解析未走完整 LLM 链路</p>
            <p className="mt-0.5 text-red-800/90">{parseWarning}</p>
          </div>
        </div>
      ) : null}

      {draft ? (
        <div
          className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          role="status"
        >
          <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p className="font-medium">解析草稿待核对</p>
            <p className="mt-0.5 text-amber-800/80">
              系统已从简历提取基础信息。请核对下方经历与要点是否完整，或用右侧 Agent 说「帮我补全经历」。
            </p>
          </div>
        </div>
      ) : null}

      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-900 via-brand-700 to-brand-600 p-6 text-white shadow-panel sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/10 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {status ? (
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                    status.tone === "ok"
                      ? "bg-emerald-400/20 text-emerald-100"
                      : status.tone === "warn"
                        ? "bg-red-400/20 text-red-100"
                        : "bg-white/15 text-white/90"
                  }`}
                >
                  {status.label}
                </span>
              ) : null}
              <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[11px]">v{profile.version}</span>
              {source ? (
                <span className="truncate text-[11px] text-white/70" title={source.file_name}>
                  {source.file_name}
                </span>
              ) : null}
            </div>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {contact.name || "姓名待填写"}
            </h2>
            <p className="mt-1 text-lg text-white/85">{headlineFromProfile(payload)}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-sm">
              {contact.location ? (
                <span className="rounded-lg bg-white/10 px-3 py-1 backdrop-blur-sm">{contact.location}</span>
              ) : null}
              {contact.email ? (
                <span className="rounded-lg bg-white/10 px-3 py-1 backdrop-blur-sm">{contact.email}</span>
              ) : null}
              {contact.phone ? (
                <span className="rounded-lg bg-white/10 px-3 py-1 backdrop-blur-sm">{contact.phone}</span>
              ) : null}
            </div>
            {onRelocalize ? (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-white/80">
                <span>档案原文语言（生成另一份译文；界面仍为中文）</span>
                {(["zh-CN", "en-US"] as const).map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    onClick={() => onRelocalize(loc)}
                    className={`rounded-full px-2.5 py-0.5 ${
                      sourceLocale.startsWith(loc === "en-US" ? "en" : "zh")
                        ? "bg-white text-brand-800"
                        : "bg-white/15 hover:bg-white/25"
                    }`}
                  >
                    {loc === "zh-CN" ? "中文" : "英文"}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[240px]">
            <StatCard label="工作经历" value={payload.experiences.length} />
            <StatCard label="教育背景" value={payload.education.length} />
            <StatCard
              label="经验年限"
              value={years != null ? `${years}年` : "—"}
            />
          </div>
        </div>
      </section>

      {payload.summary ? (
        <section
          data-path="summary"
          role="button"
          tabIndex={0}
          onClick={() =>
            onUiFocus?.({
              path: "summary",
              kind: "summary",
              label: "个人总结",
              excerpt: payload.summary ?? undefined,
            })
          }
          className={`cursor-pointer rounded-2xl border p-5 shadow-card ${
            draft ? "border-amber-200 bg-amber-50/50" : "border-surface-border bg-white"
          } ${focusRing(uiContext?.focus?.path === "summary")}`}
        >
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            {draft ? "解析摘要（待核对）" : "个人总结"}
          </h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {payload.summary}
          </p>
        </section>
      ) : null}

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900">工作经历</h3>
          <span className="text-xs text-slate-400">按时间倒序</span>
        </div>
        <ExperienceTimeline
          items={payload.experiences}
          focusPath={uiContext?.focus?.path}
          onUiFocus={onUiFocus}
        />
      </section>

      {payload.education.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-base font-semibold text-slate-900">教育背景</h3>
          <EducationList
            items={payload.education}
            focusPath={uiContext?.focus?.path}
            onUiFocus={onUiFocus}
          />
        </section>
      ) : null}

      <SkillsCloud
        payload={payload}
        active={uiContext?.focus?.path === "skills"}
        onUiFocus={onUiFocus}
      />

      {payload.projects?.length ? (
        <section className="space-y-3">
          <h3 className="text-base font-semibold text-slate-900">项目经历</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {payload.projects.map((p) => (
              <div key={p.id} className="rounded-xl border border-surface-border bg-white p-4 shadow-sm">
                <p className="font-medium text-slate-900">{p.name}</p>
                {p.role ? <p className="text-sm text-brand-700">{p.role}</p> : null}
                {p.description ? (
                  <p className="mt-2 text-sm text-slate-600">{p.description}</p>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
