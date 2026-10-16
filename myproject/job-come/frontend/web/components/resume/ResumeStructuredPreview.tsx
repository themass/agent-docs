"use client";

import type { ResumeDraft } from "@/lib/api/resume";
import { experienceLabel, type AgentUiFocus } from "@/lib/ui-context";

type ExperienceBlock = {
  company?: string;
  title?: string;
  date_range?: string;
  location?: string | null;
  bullets?: string[];
};

type Props = {
  draft: ResumeDraft | null;
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

export function ResumeStructuredPreview({ draft, focusPath = null, onUiFocus }: Props) {
  if (!draft) {
    return (
      <div className="card-sunken bg-sheen px-4 py-12 text-center">
        <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-500">
          生成优化预览后，这里将以结构化卡片展示每条经历要点。
        </p>
      </div>
    );
  }

  const sections = draft.sections as {
    header?: { name?: string; headline?: string; contact_line?: string };
    summary?: string;
    experience_blocks?: ExperienceBlock[];
    education_blocks?: Array<{ school?: string; degree_line?: string; date_range?: string }>;
    skills_block?: { content?: string };
  };

  const experiences = sections.experience_blocks ?? [];

  return (
    <div className="space-y-4">
      {sections.header ? (
        <div className="card card-pad">
          <p className="text-xl font-semibold tracking-tight text-ink-900">{sections.header.name}</p>
          {sections.header.headline ? (
            <p className="mt-0.5 text-sm font-medium text-brand-700">{sections.header.headline}</p>
          ) : null}
          {sections.header.contact_line ? (
            <p className="mt-1 text-xs text-ink-500">{sections.header.contact_line}</p>
          ) : null}
        </div>
      ) : null}

      {sections.summary ? (
        <div className="card card-pad">
          <h3 className="label-meta">个人摘要</h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-700">{sections.summary}</p>
        </div>
      ) : null}

      <div className="space-y-3">
        <h3 className="label-meta">工作经历（优化稿）</h3>
        {experiences.map((exp, idx) => (
          <article
            key={`${exp.company ?? "exp"}-${idx}`}
            data-path={`experiences[${idx}]`}
            role="button"
            tabIndex={0}
            onClick={() =>
              onUiFocus?.({
                path: `experiences[${idx}]`,
                kind: "preview-experience",
                label: experienceLabel(exp.company ?? "", exp.title ?? ""),
              })
            }
            className={`card card-pad cursor-pointer transition hover:shadow-raised ${
              focusPath === `experiences[${idx}]` || (focusPath?.startsWith(`experiences[${idx}].`) ?? false)
                ? "ring-2 ring-brand-500"
                : ""
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-base font-semibold tracking-tight text-ink-900">{exp.title ?? "职位"}</p>
                <p className="mt-0.5 text-sm font-medium text-brand-700">{exp.company ?? "公司"}</p>
              </div>
              {exp.date_range ? (
                <span className="badge badge-neutral shrink-0 tabular-nums">{exp.date_range}</span>
              ) : null}
            </div>
            <ul className="mt-3 space-y-2">
              {(exp.bullets ?? []).map((bullet, bIdx) => {
                const path = `experiences[${idx}].highlights[${bIdx}]`;
                return (
                <li
                  key={bIdx}
                  data-path={path}
                  className={`flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-ink-700 hover:bg-brand-50 ${
                    focusPath === path ? "bg-brand-50" : ""
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onUiFocus?.({
                      path,
                      kind: "highlight",
                      label: `${experienceLabel(exp.company ?? "", exp.title ?? "")} · 要点 ${bIdx + 1}`,
                      excerpt: bullet,
                    });
                  }}
                >
                  <span className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" aria-hidden />
                  <span>{bullet}</span>
                </li>
                );
              })}
            </ul>
          </article>
        ))}
      </div>

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
