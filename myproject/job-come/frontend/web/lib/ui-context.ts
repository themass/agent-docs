export type AgentUiFocusKind =
  | "experience"
  | "project"
  | "highlight"
  | "education"
  | "skills"
  | "summary"
  | "preview-experience";

export type AgentUiFocus = {
  path: string;
  kind: AgentUiFocusKind;
  label: string;
  excerpt?: string;
};

export type AgentUiContext = {
  page: string;
  step: string;
  focus: AgentUiFocus | null;
  mock_session_id?: string | null;
};

export function experienceLabel(company: string, title: string): string {
  return [company.trim() || "公司待补充", title.trim() || "职位待补充"].join(" · ");
}

export function formatUiFocusChip(ctx: AgentUiContext | null): string | null {
  const label = ctx?.focus?.label?.trim();
  return label || null;
}
