/** The kinds of interview question the bank files a question under, in one place.
 *
 * The server stores the type as free text, so a type added here needs no migration. The first five
 * are the original ones and keep their ids; "case" and "domain" are for work that is not
 * engineering (a product case, a campaign review, a sales scenario, a design critique). */
export const QUESTION_TYPES: { id: string; label: string }[] = [
  { id: "behavioral", label: "行为/STAR" },
  { id: "project_deep", label: "项目深挖" },
  { id: "technical", label: "技术" },
  { id: "system_design", label: "系统设计" },
  { id: "case", label: "案例/情景" },
  { id: "domain", label: "专业技能" },
  { id: "other", label: "其他" },
];

export function questionTypeLabel(id: string): string {
  return QUESTION_TYPES.find((t) => t.id === id)?.label ?? id;
}
