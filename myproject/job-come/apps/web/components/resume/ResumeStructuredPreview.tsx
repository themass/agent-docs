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
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        生成优化预览后，这里将以结构化卡片展示每条经历要点。
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
        <div className="rounded-xl border border-surface-border bg-white px-4 py-3 shadow-sm">
          <p className="text-lg font-semibold text-slate-900">{sections.header.name}</p>
          {sections.header.headline ? (
            <p className="text-sm text-brand-700">{sections.header.headline}</p>
          ) : null}
          {sections.header.contact_line ? (
            <p className="mt-1 text-xs text-slate-500">{sections.header.contact_line}</p>
          ) : null}
        </div>
      ) : null}

      {sections.summary ? (
        <div className="rounded-xl border border-surface-border bg-white px-4 py-3 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">个人摘要</h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">{sections.summary}</p>
        </div>
      ) : null}

      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">工作经历（优化稿）</h3>
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
            className={`cursor-pointer rounded-xl border bg-white p-4 shadow-sm ring-1 ${
              focusPath === `experiences[${idx}]` || (focusPath?.startsWith(`experiences[${idx}].`) ?? false)
                ? "border-brand-400 ring-brand-400"
                : "border-brand-100 ring-brand-50"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-slate-900">{exp.title ?? "职位"}</p>
                <p className="text-sm text-slate-600">{exp.company ?? "公司"}</p>
              </div>
              {exp.date_range ? (
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] text-slate-600">
                  {exp.date_range}
                </span>
              ) : null}
            </div>
            <ul className="mt-3 space-y-2">
              {(exp.bullets ?? []).map((bullet, bIdx) => {
                const path = `experiences[${idx}].highlights[${bIdx}]`;
                return (
                <li
                  key={bIdx}
                  data-path={path}
                  className={`flex cursor-pointer gap-2 rounded-md px-1 py-0.5 text-sm leading-relaxed text-slate-700 hover:bg-brand-50 ${
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
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                  <span>{bullet}</span>
                </li>
                );
              })}
            </ul>
          </article>
        ))}
      </div>

      {sections.skills_block?.content ? (
        <div className="rounded-xl border border-surface-border bg-white px-4 py-3 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">技能</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sections.skills_block.content.split(/[,，；;]/).map((skill) => {
              const label = skill.trim();
              if (!label) return null;
              return (
                <span
                  key={label}
                  className="rounded-full bg-slate-900 px-2.5 py-0.5 text-[11px] font-medium text-white"
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
