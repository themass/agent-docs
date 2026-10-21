/**
 * User-facing names for the resume writing techniques the backend detects.
 *
 * Ids must stay in sync with `backend/server/src/jc/services/elevation_techniques.py`.
 * Unknown ids are ignored rather than rendered raw, so a backend addition degrades
 * quietly instead of leaking an internal identifier into the UI.
 */

export type TechniqueId =
  | "quantified"
  | "outcome"
  | "ownership"
  | "object"
  | "jd_aligned"
  | "tightened"
  | "expanded";

export type Technique = {
  id: TechniqueId;
  label: string;
  hint: string;
};

export const TECHNIQUES: Technique[] = [
  {
    id: "quantified",
    label: "补量化",
    hint: "把规模、指标或前后对比写进要点，让成果可衡量。",
  },
  {
    id: "outcome",
    label: "加结果",
    hint: "补上这件事带来的变化，而不是只说做了什么。",
  },
  {
    id: "ownership",
    label: "强化主导性",
    hint: "在原文支持的范围内，换用更能体现负责程度的动词。",
  },
  {
    id: "object",
    label: "明确对象",
    hint: "写清动作作用在哪个系统、产品或流程上，避免空泛。",
  },
  {
    id: "jd_aligned",
    label: "对齐岗位",
    hint: "换用目标岗位描述里的说法，指同一件事，不新增技能。",
  },
  {
    id: "tightened",
    label: "精简表达",
    hint: "删掉冗余铺垫，让招聘方更快读到重点。",
  },
  {
    id: "expanded",
    label: "补充细节",
    hint: "把原文压缩掉的背景和职责还原出来。",
  },
];

const BY_ID = new Map(TECHNIQUES.map((t) => [t.id, t]));

export function techniqueOf(id: string): Technique | null {
  return BY_ID.get(id as TechniqueId) ?? null;
}

/** Resolve a raw id list from the API into renderable techniques, dropping unknowns. */
export function resolveTechniques(ids: unknown): Technique[] {
  if (!Array.isArray(ids)) return [];
  const out: Technique[] = [];
  for (const raw of ids) {
    const found = typeof raw === "string" ? techniqueOf(raw) : null;
    if (found && !out.some((t) => t.id === found.id)) out.push(found);
  }
  return out;
}

/** Count technique usage across a draft's elevation map, preserving catalogue order. */
export function summarizeTechniques(
  entries: Array<{ techniques?: unknown }>,
): Array<Technique & { count: number }> {
  const counts = new Map<TechniqueId, number>();
  for (const entry of entries) {
    for (const t of resolveTechniques(entry.techniques)) {
      counts.set(t.id, (counts.get(t.id) ?? 0) + 1);
    }
  }
  return TECHNIQUES.filter((t) => counts.has(t.id)).map((t) => ({
    ...t,
    count: counts.get(t.id) ?? 0,
  }));
}

/**
 * What each elevation level controls: how far the wording may travel from the source.
 * No level permits inventing facts — that boundary is enforced in the writer prompt
 * and re-checked by the reviewer before export.
 */
export const LEVEL_GUIDE: Record<
  "conservative" | "standard" | "elevated",
  { label: string; summary: string; detail: string }
> = {
  conservative: {
    label: "保守",
    summary: "贴近原文，只做语句通顺和结构整理",
    detail: "适合内推、已有熟人背书，或你对原简历措辞很有把握的场景。",
  },
  standard: {
    label: "标准",
    summary: "按「动作 + 对象 + 结果」重写要点，补齐缺失的结果表述",
    detail: "大多数情况下的推荐档位：读起来专业，每句话都还能对上原始经历。",
  },
  elevated: {
    label: "强化",
    summary: "在证据允许的上限内强化主导性与量化，突出最强成果",
    detail: "适合冲击更高职级。每条拔高的表述都要能撑过面试官追问「能具体讲讲吗」。",
  },
};
