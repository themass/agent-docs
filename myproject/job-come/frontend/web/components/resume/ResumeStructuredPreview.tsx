"use client";

import type { ResumeDraft } from "@/lib/api/resume";
import { experienceLabel, type AgentUiFocus } from "@/lib/ui-context";

import type { PreviewProgress } from "@/lib/preview-progress";
import { ElevatePreviewGenerating } from "./ElevatePreviewGenerating";

/**
 * Scope values at or under this length are role metadata ("带 7 人团队") and sit on the
 * title row; longer ones are a sentence and keep their own lead paragraph. Mirrors the
 * export templates (`templates/resume/_sections.html`, `resume_render_engine`) so the
 * preview shows the same shape the downloaded file has.
 */
const INLINE_SCOPE_MAX = 14;
const inlineScope = (scope?: string | null) => {
  const text = (scope ?? "").trim();
  return text && text.length <= INLINE_SCOPE_MAX ? text : null;
};

type ExperienceBlock = {
  company?: string;
  title?: string;
  date_range?: string;
  location?: string | null;
  /** The 先总后分 opener: team size, ownership, scale. Written from the user's own words. */
  scope_line?: string | null;
  bullets?: string[];
};

type ProjectBlock = {
  name?: string;
  role?: string | null;
  date_range?: string | null;
  description?: string | null;
  scope_line?: string | null;
  bullets?: string[];
};

type Props = {
  draft: ResumeDraft | null;
  progress?: PreviewProgress;
  generating?: boolean;
  loadStartedAt?: number | null;
  onRetry?: () => void;
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

const SECTION_TITLES: Record<string, string> = {
  experience: "工作经历（优化稿）",
  experience_blocks: "工作经历（优化稿）",
  projects: "项目经历",
  project_blocks: "项目经历",
};

/**
 * The structured view of a generated draft.
 *
 * Two things here are not cosmetic. It renders the scope line, because that line *is*
 * the 先总后分 layer — without it the structured view shows a job title followed by
 * bullets and the document reads as a flat list. And it renders project blocks in the
 * draft's own `section_order`, because the composition pass is allowed to promote
 * projects above experience when the evidence lives there; a preview with a hardcoded
 * order would silently contradict the exported file.
 */
export function ResumeStructuredPreview({
  draft,
  progress,
  generating = false,
  loadStartedAt = null,
  onRetry,
  focusPath = null,
  onUiFocus,
}: Props) {
  if (generating) {
    return (
      <ElevatePreviewGenerating progress={progress} startedAt={loadStartedAt} onRetry={onRetry} />
    );
  }

  if (!draft) {
    return (
      <div className="card-sunken bg-sheen px-4 py-12 text-center">
        <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-500">
          点顶部工具栏的「生成预览」，完成后会自动显示在这里，无需刷新页面。
        </p>
      </div>
    );
  }

  const sections = draft.sections as {
    /**
     * `photo_data_uri` is present only when the user uploaded a headshot *and* left
     * the display switch on — the builder omits it otherwise, which is the same
     * signal the export templates read. Showing it here means the preview matches
     * what the PDF will contain, rather than the photo being a surprise on export.
     */
    header?: {
      name?: string;
      headline?: string;
      contact_line?: string;
      photo_data_uri?: string;
    };
    summary?: string;
    experience_blocks?: ExperienceBlock[];
    project_blocks?: ProjectBlock[];
    education_blocks?: Array<{ school?: string; degree_line?: string; date_range?: string }>;
    skills_block?: { content?: string };
    section_order?: string[];
  };

  const experiences = sections.experience_blocks ?? [];
  const projects = sections.project_blocks ?? [];

  // Follow the draft's section order so the preview matches the exported document.
  // Only the two blocks that carry evidence are ordered here; the rest keep their
  // fixed position below, where a recruiter skims rather than reads.
  // Normalised to one token per section: the backend uses `experience` in
  // `section_order` and `experience_blocks` as the payload key, and rendering both would
  // duplicate the section.
  const order: string[] = [];
  for (const key of sections.section_order ?? ["experience", "projects"]) {
    const group = key.startsWith("experience")
      ? "experience"
      : key.startsWith("project")
        ? "projects"
        : null;
    if (group && !order.includes(group)) order.push(group);
  }
  const ordered = order.length ? order : ["experience", "projects"];

  function renderExperiences() {
    if (!experiences.length) return null;
    return (
      <div key="experience" className="space-y-3">
        <h3 className="label-meta">{SECTION_TITLES.experience}</h3>
        {experiences.map((exp, idx) => {
          const path = `experiences[${idx}]`;
          const focused = focusPath === path || (focusPath?.startsWith(`${path}.`) ?? false);
          return (
            <article
              key={`${exp.company ?? "exp"}-${idx}`}
              data-path={path}
              role="button"
              tabIndex={0}
              onClick={() =>
                onUiFocus?.({
                  path,
                  kind: "preview-experience",
                  label: experienceLabel(exp.company ?? "", exp.title ?? ""),
                })
              }
              className={`card card-pad cursor-pointer transition hover:shadow-raised ${
                focused ? "ring-2 ring-brand-500" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-base font-semibold tracking-tight text-ink-900">
                    {exp.title ?? "职位"}
                    {inlineScope(exp.scope_line) ? (
                      <span className="ml-2 text-sm font-medium text-ink-500">
                        · {inlineScope(exp.scope_line)}
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 text-sm font-medium text-brand-700">
                    {exp.company ?? "公司"}
                  </p>
                </div>
                {exp.date_range ? (
                  <span className="badge badge-neutral shrink-0 tabular-nums">
                    {exp.date_range}
                  </span>
                ) : null}
              </div>
              {/* The scope line, visually set apart from the bullets: it is a summary of
                  the role, not one more accomplishment. */}
              {exp.scope_line && !inlineScope(exp.scope_line) ? (
                <p className="mt-2.5 border-l-2 border-brand-200 pl-2.5 text-sm leading-relaxed text-ink-600">
                  {exp.scope_line}
                </p>
              ) : null}
              <ul className="mt-3 space-y-2">
                {(exp.bullets ?? []).map((bullet, bIdx) => {
                  const bulletPath = `experiences[${idx}].highlights[${bIdx}]`;
                  return (
                    <li
                      key={bIdx}
                      data-path={bulletPath}
                      className={`flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-ink-700 hover:bg-brand-50 ${
                        focusPath === bulletPath ? "bg-brand-50" : ""
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onUiFocus?.({
                          path: bulletPath,
                          kind: "highlight",
                          label: `${experienceLabel(exp.company ?? "", exp.title ?? "")} · 要点 ${
                            bIdx + 1
                          }`,
                          excerpt: bullet,
                        });
                      }}
                    >
                      <span
                        className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                        aria-hidden
                      />
                      <span>{bullet}</span>
                    </li>
                  );
                })}
              </ul>
            </article>
          );
        })}
      </div>
    );
  }

  function renderProjects() {
    if (!projects.length) return null;
    return (
      <div key="projects" className="space-y-3">
        <h3 className="label-meta">{SECTION_TITLES.projects}</h3>
        {projects.map((proj, idx) => {
          const path = `projects[${idx}]`;
          const focused = focusPath === path || (focusPath?.startsWith(`${path}.`) ?? false);
          return (
            <article
              key={`${proj.name ?? "proj"}-${idx}`}
              data-path={path}
              className={`card card-pad ${focused ? "ring-2 ring-brand-500" : ""}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-base font-semibold tracking-tight text-ink-900">
                    {proj.name ?? "项目"}
                  </p>
                  {proj.role ? (
                    <p className="mt-0.5 text-sm font-medium text-brand-700">{proj.role}</p>
                  ) : null}
                </div>
                {proj.date_range ? (
                  <span className="badge badge-neutral shrink-0 tabular-nums">
                    {proj.date_range}
                  </span>
                ) : null}
              </div>
              {(() => {
                const lead = inlineScope(proj.scope_line)
                  ? proj.description
                  : (proj.scope_line ?? proj.description);
                return lead ? (
                  <p className="mt-2.5 border-l-2 border-brand-200 pl-2.5 text-sm leading-relaxed text-ink-600">
                    {lead}
                  </p>
                ) : null;
              })()}
              <ul className="mt-3 space-y-2">
                {(proj.bullets ?? []).map((bullet, bIdx) => (
                  <li
                    key={bIdx}
                    className="flex gap-2 px-1 py-0.5 text-sm leading-relaxed text-ink-700"
                  >
                    <span
                      className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                      aria-hidden
                    />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sections.header ? (
        <div className="card card-pad">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-xl font-semibold tracking-tight text-ink-900">
                {sections.header.name}
              </p>
              {sections.header.headline ? (
                <p className="mt-0.5 text-sm font-medium text-brand-700">
                  {sections.header.headline}
                </p>
              ) : null}
              {sections.header.contact_line ? (
                <p className="mt-1 text-xs text-ink-500">{sections.header.contact_line}</p>
              ) : null}
            </div>
            {sections.header.photo_data_uri ? (
              // Same 4:5 box and `object-cover` as the print stylesheet, so the
              // framing shown here is the framing that gets printed.
              <img
                src={sections.header.photo_data_uri}
                alt=""
                className="shrink-0 rounded border border-surface-border object-cover object-top"
                style={{ width: 60, height: 75 }}
              />
            ) : null}
          </div>
        </div>
      ) : null}

      {sections.summary ? (
        <div className="card card-pad">
          <h3 className="label-meta">个人摘要</h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-700">{sections.summary}</p>
        </div>
      ) : null}

      {ordered.map((key) => (key === "experience" ? renderExperiences() : renderProjects()))}

      {sections.skills_block?.content ? (
        <div className="card card-pad">
          <h3 className="label-meta">技能</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sections.skills_block.content.split(/[,，；;]/).map((skill) => {
              const label = skill.trim();
              if (!label) return null;
              return (
                <span
                  key={label}
                  className="rounded-md bg-surface-sunken px-2.5 py-1 text-xs font-medium text-ink-700 ring-1 ring-inset ring-surface-border"
                >
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
