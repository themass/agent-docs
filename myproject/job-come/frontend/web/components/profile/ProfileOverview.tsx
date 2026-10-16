"use client";

import type { Profile, ProfileEducation, ProfileExperience, ProfilePayload } from "@/lib/api/profile";
import {
  estimateYears,
  formatDateRange,
  headlineFromProfile,
  isParseDraft,
  parseStatusLabel,
} from "@/lib/profile-utils";
import { ZHOUKA_NAME } from "@/lib/brand";
import { isDegradedIngest } from "@/lib/resume-workflow";
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
    <div className="rounded-xl bg-surface-sunken px-3.5 py-3 ring-1 ring-inset ring-surface-border">
      <p className="text-2xl font-semibold tabular-nums tracking-tight text-ink-900">{value}</p>
      <p className="mt-0.5 text-xs text-ink-500">{label}</p>
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
      <div className="card-sunken px-4 py-10 text-center">
        <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-500">
          未识别到工作经历。可在下方「快速编辑」补充，或让右侧{ZHOUKA_NAME}帮你整理。
        </p>
      </div>
    );
  }

  return (
    <ol className="space-y-4">
      {items.map((exp, idx) => (
        <li key={exp.id || idx} className="relative pl-8">
          {idx < items.length - 1 ? (
            <span
              className="absolute left-[11px] top-8 h-[calc(100%+1rem)] w-px bg-surface-border-strong"
              aria-hidden
            />
          ) : null}
          <span
            className="absolute left-0 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-micro font-bold text-white ring-4 ring-surface-sunken"
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
            className={`card card-pad cursor-pointer transition hover:shadow-raised ${focusRing(focusPath === `experiences[${idx}]` || (focusPath?.startsWith(`experiences[${idx}].`) ?? false))}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h4 className="text-base font-semibold tracking-tight text-ink-900">{exp.title || "职位待补充"}</h4>
                <p className="mt-0.5 text-sm font-medium text-brand-700">{exp.company || "公司待补充"}</p>
              </div>
              <time className="badge badge-neutral shrink-0 tabular-nums">
                {formatDateRange(exp.start_date, exp.end_date)}
              </time>
            </div>
            {exp.location ? <p className="mt-1 text-xs text-ink-500">{exp.location}</p> : null}
            {exp.highlights?.length ? (
              <ul className="mt-3 space-y-1.5">
                {exp.highlights.map((h, i) => {
                  const path = `experiences[${idx}].highlights[${i}]`;
                  return (
                    <li
                      key={i}
                      data-path={path}
                      className={`-mx-1 flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-ink-700 hover:bg-brand-50 ${
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
              <p className="mt-2 text-sm italic text-ink-500">暂无要点描述</p>
            )}
            {exp.skills?.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {exp.skills.map((s) => (
                  <span
                    key={s}
                    className="badge badge-brand"
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
          className={`card card-pad cursor-pointer transition hover:shadow-raised ${focusRing(focusPath === path)}`}
        >
          <p className="text-sm font-semibold text-ink-900">{edu.school}</p>
          <p className="mt-1 text-sm text-ink-600">
            {[edu.degree, edu.major].filter(Boolean).join(" · ") || "学历信息待补充"}
          </p>
          <p className="mt-2 text-xs text-ink-500">
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
          className="rounded-md bg-surface px-2.5 py-1 text-xs font-medium text-ink-700 shadow-xs ring-1 ring-inset ring-surface-border"
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
  const status = source ? parseStatusLabel(source.parse_status, source.parse_phase) : null;
  const parseWarning = source?.parse_error;
  const degradedIngest = isDegradedIngest(profile);
  const showParseFailure = Boolean(
    parseWarning && source?.parse_status === "failed" && !degradedIngest,
  );
  const showReviewBanner =
    !showParseFailure && (draft || degradedIngest || Boolean(parseWarning));
  const reviewDetail =
    parseWarning ??
    (degradedIngest
      ? "我们已为您生成可编辑草稿，请核对并补充经历，或稍后重新上传简历。"
      : "系统已从简历提取基础信息。请核对下方经历与要点是否完整。");
  const sourceLocale = payload.meta?.source_locale || profile.locale || "zh-CN";

  if (compact) {
    return (
      <section className="card bg-sheen card-pad">
        <div className="flex flex-wrap items-center gap-1.5">
          {status ? (
            <span
              className={`badge ${
                status.tone === "ok"
                  ? "badge-success"
                  : status.tone === "warn"
                    ? "badge-danger"
                    : "badge-neutral"
              }`}
            >
              {status.label}
            </span>
          ) : null}
          <span className="badge badge-neutral tabular-nums">v{profile.version}</span>
          <span className={`badge ${profile.status === "confirmed" ? "badge-success" : "badge-warn"}`}>
            {profile.status === "confirmed" ? "已确认" : "草稿"}
          </span>
        </div>
        <h2 className="mt-2.5 text-xl font-semibold tracking-tight text-ink-900">
          {contact.name || "姓名待填写"}
        </h2>
        <p className="mt-0.5 text-sm text-ink-600">{headlineFromProfile(payload)}</p>
        <p className="mt-2 text-xs tabular-nums text-ink-500">
          {payload.experiences.length} 段经历 · {payload.education.length} 段教育
          {years != null ? ` · 约 ${years} 年` : ""}
        </p>
        {showParseFailure ? (
          <div className="notice notice-danger mt-3 text-xs" role="alert">
            <span>{parseWarning}</span>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-6">
      {showParseFailure ? (
        <div className="notice notice-danger" role="alert">
          <svg className="mt-0.5 h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p className="font-medium">简历处理失败</p>
            <p className="mt-0.5 text-xs leading-relaxed opacity-80">{parseWarning}</p>
          </div>
        </div>
      ) : null}

      {showReviewBanner ? (
        <div className="notice notice-warn" role="status">
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
            <p className="mt-0.5 text-xs leading-relaxed opacity-85">{reviewDetail}</p>
            <p className="mt-1 text-xs leading-relaxed opacity-70">
              也可在右侧对{ZHOUKA_NAME}说「帮我补全经历」。
            </p>
          </div>
        </div>
      ) : null}

      {/* Identity header. Light surface: the dark gradient competed with the
          content below it and is the main reason the page read as dated. */}
      <section className="card bg-sheen relative overflow-hidden p-5 sm:p-6">
        <div
          className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-brand-200/30 blur-3xl"
          aria-hidden
        />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-1.5">
              {status ? (
                <span
                  className={`badge ${
                    status.tone === "ok"
                      ? "badge-success"
                      : status.tone === "warn"
                        ? "badge-danger"
                        : "badge-neutral"
                  }`}
                >
                  {status.label}
                </span>
              ) : null}
              <span className="badge badge-neutral tabular-nums">v{profile.version}</span>
              {source ? (
                <span className="truncate text-xs text-ink-500" title={source.file_name}>
                  {source.file_name}
                </span>
              ) : null}
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-ink-900">
              {contact.name || "姓名待填写"}
            </h2>
            <p className="mt-1 max-w-prose text-base text-ink-600">{headlineFromProfile(payload)}</p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {[contact.location, contact.email, contact.phone]
                .filter(Boolean)
                .map((value) => (
                  <span
                    key={value as string}
                    className="rounded-md bg-surface px-2.5 py-1 text-xs text-ink-600 shadow-xs ring-1 ring-inset ring-surface-border"
                  >
                    {value}
                  </span>
                ))}
            </div>
            {onRelocalize ? (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="label-meta">档案原文语言</span>
                <div className="segment">
                  {(["zh-CN", "en-US"] as const).map((loc) => {
                    const active = sourceLocale.startsWith(loc === "en-US" ? "en" : "zh");
                    return (
                      <button
                        key={loc}
                        type="button"
                        onClick={() => onRelocalize(loc)}
                        aria-pressed={active}
                        className={`segment-item ${active ? "segment-item-active" : ""}`}
                      >
                        {loc === "zh-CN" ? "中文" : "英文"}
                      </button>
                    );
                  })}
                </div>
                <span className="text-xs text-ink-500">切换会生成另一份译文；界面仍为中文。</span>
              </div>
            ) : null}
          </div>
          <div className="grid shrink-0 grid-cols-3 gap-2.5 lg:min-w-[260px]">
            <StatCard label="工作经历" value={payload.experiences.length} />
            <StatCard label="教育背景" value={payload.education.length} />
            <StatCard label="经验年限" value={years != null ? `${years}年` : "—"} />
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
          className={`card-pad cursor-pointer rounded-xl ${
            draft
              ? "bg-warn-50/60 ring-1 ring-inset ring-warn-200"
              : "card"
          } ${focusRing(uiContext?.focus?.path === "summary")}`}
        >
          <h3 className="label-meta">{draft ? "解析摘要（待核对）" : "个人总结"}</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
            {payload.summary}
          </p>
        </section>
      ) : null}

      <section className="space-y-4">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-lg font-semibold tracking-tight text-ink-900">工作经历</h3>
          <span className="text-xs text-ink-500">按时间倒序</span>
        </div>
        <ExperienceTimeline
          items={payload.experiences}
          focusPath={uiContext?.focus?.path}
          onUiFocus={onUiFocus}
        />
      </section>

      {payload.education.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-lg font-semibold tracking-tight text-ink-900">教育背景</h3>
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
          <h3 className="text-lg font-semibold tracking-tight text-ink-900">项目经历</h3>
          {/* Projects carry the same bullet density as experience, so they get the same
              full-width layout rather than a two-column card grid that truncates them. */}
          <ol className="space-y-3">
            {payload.projects.map((proj, idx) => {
              const projPath = `projects[${idx}]`;
              const label = proj.name || `项目 ${idx + 1}`;
              return (
                <li key={proj.id || idx}>
                  <div
                    data-path={projPath}
                    role="button"
                    tabIndex={0}
                    onClick={() => onUiFocus?.({ path: projPath, kind: "project", label })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onUiFocus?.({ path: projPath, kind: "project", label });
                      }
                    }}
                    className={`card card-pad cursor-pointer transition hover:shadow-raised ${focusRing(
                      uiContext?.focus?.path === projPath ||
                        (uiContext?.focus?.path?.startsWith(`${projPath}.`) ?? false),
                    )}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <h4 className="text-base font-semibold tracking-tight text-ink-900">
                          {label}
                        </h4>
                        {proj.role ? (
                          <p className="mt-0.5 text-sm font-medium text-brand-700">{proj.role}</p>
                        ) : null}
                      </div>
                      {proj.start_date ? (
                        <time className="badge badge-neutral shrink-0 tabular-nums">
                          {formatDateRange(proj.start_date, proj.end_date)}
                        </time>
                      ) : null}
                    </div>
                    {proj.description ? (
                      <p className="mt-2 text-sm leading-relaxed text-ink-600">
                        {proj.description}
                      </p>
                    ) : null}
                    {proj.highlights?.length ? (
                      <ul className="mt-3 space-y-1.5">
                        {proj.highlights.map((h, i) => {
                          const path = `${projPath}.highlights[${i}]`;
                          return (
                            <li
                              key={i}
                              data-path={path}
                              className={`-mx-1 flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-ink-700 hover:bg-brand-50 ${
                                uiContext?.focus?.path === path ? "bg-brand-50" : ""
                              }`}
                              onClick={(e) => {
                                e.stopPropagation();
                                onUiFocus?.({
                                  path,
                                  kind: "highlight",
                                  label: `${label} · 要点 ${i + 1}`,
                                  excerpt: h,
                                });
                              }}
                            >
                              <span
                                className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand-400"
                                aria-hidden
                              />
                              <span>{h}</span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}
    </div>
  );
}
