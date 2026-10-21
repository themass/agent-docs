"use client";

import { useState } from "react";

import type { ResumeBlueprintReport, ResumeStructure } from "@/lib/api/resume";

type Props = {
  blueprint?: ResumeBlueprintReport | null;
  structure?: ResumeStructure | null;
  /** Jump to the evidence questions, which is how most unmet requirements get fixed. */
  onGoToEvidence?: () => void;
  /** Open the per-bullet change list, where the moves below can be read in context. */
  onGoToChanges?: () => void;
};

const SECTION_LABELS: Record<string, string> = {
  summary: "摘要",
  experience: "工作经历",
  experience_blocks: "工作经历",
  projects: "项目经历",
  project_blocks: "项目经历",
  skills: "技能",
  skills_block: "技能",
  education: "教育",
  education_blocks: "教育",
  certifications: "证书",
  publications: "作品 / 发表",
};

function sectionLabel(key: string): string {
  return SECTION_LABELS[key] ?? key;
}

/**
 * The document-level report: what bar this resume is being written to, and which parts
 * of it the current draft clears.
 *
 * Why this panel exists
 * ---------------------
 * Two complaints have the same root cause. "不同岗位有不同的方法论" was true in the code
 * and invisible in the product — the role family only ever reached the writer prompt.
 * And "只是逐条优化文字，没有根本性提升" was partly a perception problem: the draft had
 * already been re-ordered and re-sectioned, but every signal on screen was sentence-level,
 * so that work read as polish.
 *
 * So this shows the two things a per-bullet diff structurally cannot: the *contract*
 * (what a resume in this family must do) and the *document moves* (what changed above
 * the sentence). Each unmet requirement states what is wrong, why it costs the user a
 * screen, and the one action that fixes it.
 *
 * Everything here is measured by deterministic checks, never by a model, and nothing
 * here blocks export. A structural shortfall that the user chooses to accept is their
 * call; a checklist that refuses to let them download is a product that does not ship.
 */
export function BlueprintPanel({
  blueprint,
  structure,
  onGoToEvidence,
  onGoToChanges,
}: Props) {
  // Collapsed by default: step 3 already carries the controls, the evidence prompts and
  // the document itself, and pushing the resume below the fold is the exact complaint
  // this panel is meant to answer.
  const [expanded, setExpanded] = useState(false);

  if (!blueprint) return null;

  const { blueprint: bp, findings, met, total } = blueprint;
  const unmet = findings.filter((f) => !f.met);
  const allMet = total > 0 && met === total;
  const moves = structure?.moves ?? [];
  const reordered = Boolean(structure?.section_order_changed);

  return (
    <section className="card card-pad">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-start justify-between gap-3 text-left"
      >
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
            按「{bp.label}」的简历标准检查
            <span className={`badge ${allMet ? "badge-success" : "badge-warn"}`}>
              {met}/{total} 达标
            </span>
          </h3>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            {allMet
              ? "这一稿满足该岗位的文档结构要求：摘要结论先行、每段先说范围、最强成果在前、分量达标。"
              : unmet.length === 1
                ? `还差 1 项：${unmet[0].label}。`
                : `还差 ${unmet.length} 项：${unmet
                    .slice(0, 2)
                    .map((f) => f.label)
                    .join("、")}${unmet.length > 2 ? " 等" : ""}。`}
          </p>
        </div>
        <svg
          viewBox="0 0 20 20"
          aria-hidden="true"
          fill="currentColor"
          className={`mt-0.5 h-4 w-4 shrink-0 text-ink-500 transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        >
          <path d="M5.5 7.5 10 12l4.5-4.5H5.5Z" />
        </svg>
      </button>

      {/* A one-line summary of the document moves stays visible when collapsed: it is
          the shortest possible answer to "这次到底改了什么结构". */}
      {!expanded && (reordered || moves.length > 0) ? (
        <p className="mt-2.5 border-t border-surface-border pt-2.5 text-xs leading-relaxed text-ink-600">
          本稿做了文档级调整：
          {reordered ? "重排了章节顺序" : ""}
          {reordered && moves.length ? "，" : ""}
          {moves.length ? `把 ${moves.length} 条最有分量的要点提到了段首` : ""}。
        </p>
      ) : null}

      {expanded ? (
        <div className="mt-4 space-y-4 border-t border-surface-border pt-4">
          {/* 1. The contract. Shown first because it is what the user asked to see:
                 the methodology for their specific role, in their own words. */}
          <div className="card-sunken p-3">
            <p className="label-meta">这类岗位的简历怎么写</p>
            <dl className="mt-2.5 space-y-2 text-xs leading-relaxed">
              <div>
                <dt className="font-medium text-ink-800">章节顺序</dt>
                <dd className="mt-0.5 text-ink-600">
                  {bp.section_order.map(sectionLabel).join(" › ")}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-ink-800">摘要公式</dt>
                <dd className="mt-0.5 text-ink-600">{bp.summary_formula.join(" → ")}</dd>
              </div>
              <div>
                <dt className="font-medium text-ink-800">每段开头要说清</dt>
                <dd className="mt-0.5 text-ink-600">{bp.scope_dimensions.join("、")}</dd>
              </div>
              <div>
                <dt className="font-medium text-ink-800">最有说服力的证据</dt>
                <dd className="mt-0.5 text-ink-600">{bp.evidence_ladder.join(" > ")}</dd>
              </div>
              <div>
                <dt className="font-medium text-ink-800">分量要求</dt>
                <dd className="mt-0.5 text-ink-600">
                  最近一段至少 {bp.lead_bullets} 条要点，更早每段至少 {bp.tail_bullets} 条；
                  其中至少 {Math.round(bp.outcome_ratio * 100)}% 要写到结果
                  {bp.quantification_optional ? "（这类岗位可用成果描述代替数字）" : ""}。
                </dd>
              </div>
              {bp.must_haves.length ? (
                <div>
                  <dt className="font-medium text-ink-800">缺了就算不完整</dt>
                  <dd className="mt-0.5 text-ink-600">{bp.must_haves.join("、")}</dd>
                </div>
              ) : null}
            </dl>
            {bp.anti_patterns.length ? (
              <div className="mt-3 border-t border-surface-border pt-2.5">
                <p className="label-meta">这类简历最常见的写法问题</p>
                <ul className="mt-1.5 space-y-1 text-xs leading-relaxed text-ink-600">
                  {bp.anti_patterns.map((a) => (
                    <li key={a} className="flex gap-1.5">
                      <span aria-hidden="true" className="text-ink-500">
                        ·
                      </span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {/* 2. Per-requirement verdict. Unmet first — a checklist read top to bottom
                 should start with what needs doing. */}
          <div>
            <p className="label-meta">这一稿的逐项检查</p>
            <ul className="mt-2 space-y-2">
              {[...findings].sort((a, b) => Number(a.met) - Number(b.met)).map((f) => (
                <li
                  key={f.id}
                  className={`rounded-xl border p-3 ${
                    f.met
                      ? "border-surface-border bg-surface"
                      : "border-warn-200 bg-warn-50"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {f.met ? (
                      <svg
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                        fill="currentColor"
                        className="mt-0.5 h-4 w-4 shrink-0 text-success-600"
                      >
                        <path d="M8.2 13.4 5 10.2l1.1-1.1 2.1 2.1 5.6-5.6L15 6.7l-6.8 6.7Z" />
                      </svg>
                    ) : (
                      <svg
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                        fill="currentColor"
                        className="mt-0.5 h-4 w-4 shrink-0 text-warn-700"
                      >
                        <path d="M10 2.5 18.5 17H1.5L10 2.5Zm-.9 5.2v4h1.8v-4H9.1Zm0 5.3v1.8h1.8V13H9.1Z" />
                      </svg>
                    )}
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-xs font-medium ${
                          f.met ? "text-ink-800" : "text-warn-900"
                        }`}
                      >
                        {f.label}
                        <span className="ml-1.5 font-normal opacity-80">{f.detail}</span>
                      </p>
                      {!f.met ? (
                        <>
                          <p className="mt-1 text-xs leading-relaxed text-warn-900 opacity-90">
                            {f.why}
                          </p>
                          <p className="mt-1 text-xs leading-relaxed text-ink-600">
                            怎么改：{f.fix}
                          </p>
                        </>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {unmet.length && onGoToEvidence ? (
              <button
                type="button"
                onClick={onGoToEvidence}
                className="btn btn-sm btn-secondary mt-2.5"
              >
                去补充证据
              </button>
            ) : null}
          </div>

          {/* 3. The document moves. The per-bullet diff cannot show these, which is
                 why the structural work read as "only wording changed". */}
          {structure ? (
            <div>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="label-meta">本稿的文档级改动</p>
                {moves.length && onGoToChanges ? (
                  <button
                    type="button"
                    onClick={onGoToChanges}
                    className="btn btn-sm btn-ghost text-brand-700 hover:text-brand-800"
                  >
                    逐条查看改动 →
                  </button>
                ) : null}
              </div>
              <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-ink-600">
                <li>
                  章节顺序：{structure.section_order.map(sectionLabel).join(" › ")}
                  {structure.section_order_reason ? (
                    <span className="text-ink-500">
                      （{structure.section_order_reason}）
                    </span>
                  ) : (
                    <span className="text-ink-500">（沿用该岗位默认顺序）</span>
                  )}
                </li>
                <li>
                  范围句覆盖：{structure.scope_lines}/{structure.blocks_total} 段
                  {structure.blocks_total && structure.scope_lines < structure.blocks_total ? (
                    <span className="text-ink-500">
                      （缺的那几段读者无法判断你的量级）
                    </span>
                  ) : null}
                </li>
                {structure.summary_shape ? (
                  <li>
                    摘要：
                    {structure.summary_shape.conclusion_first
                      ? "已结论先行"
                      : [
                          structure.summary_shape.positioning ? null : "缺定位",
                          structure.summary_shape.evidence ? null : "缺硬证据",
                          structure.summary_shape.direction ? null : "缺方向",
                        ]
                          .filter(Boolean)
                          .join("、")}
                  </li>
                ) : null}
                {moves.length ? (
                  <li>
                    段内重排 {moves.length} 处，最有分量的成果已提到段首：
                    <ul className="mt-1 space-y-1">
                      {moves.slice(0, 3).map((m) => (
                        <li key={m.field_path} className="text-ink-500">
                          {m.where}：「{m.text.slice(0, 28)}
                          {m.text.length > 28 ? "…" : ""}」{m.from_index + 1} → {m.to_index + 1}
                          （{m.reason}）
                        </li>
                      ))}
                    </ul>
                  </li>
                ) : (
                  <li className="text-ink-500">段内顺序未调整：每段第一条已是最有分量的成果。</li>
                )}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
