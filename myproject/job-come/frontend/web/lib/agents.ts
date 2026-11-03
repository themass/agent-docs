/**
 * The three agents a candidate works with, and the record pages each one produces. The header's
 * first-level entries, each agent's own frame, and the tabs inside it all read from here.
 *
 * The names and promises are the ones decided in docs/architecture/AGENTS-DESIGN.md (§2, §10).
 */
export type AgentId = "resume" | "interview" | "apply";

export type AgentRecord = { href: string; label: string };

export type Agent = {
  id: AgentId;
  name: string;
  promise: string;
  /** The agent's own workbench: where its conversation lives. */
  home: string;
  /** The letter on its badge. */
  initial: string;
  /** Tailwind background class for its badge. */
  tone: string;
  /** Record pages this agent produces, shown as tabs inside its frame. */
  records: AgentRecord[];
  /** Other paths that belong to this agent but are not tabs (a report opened from its archive). */
  also?: string[];
};

export const AGENTS: Agent[] = [
  {
    id: "resume",
    name: "简历顾问",
    promise: "把真实经历整理成招聘方看得懂的简历，并过质检",
    home: "/resume-agent",
    initial: "简",
    tone: "bg-brand-600",
    records: [{ href: "/resume-versions", label: "简历版本" }],
  },
  {
    id: "interview",
    name: "面试教练",
    promise: "像真实面试官一样追问，给出有依据的修正和参考答案",
    home: "/coach-agent",
    initial: "面",
    tone: "bg-warn-600",
    records: [
      { href: "/bank", label: "题库" },
      { href: "/interviews", label: "面试归档" },
    ],
    also: ["/mock-reports"],
  },
  {
    id: "apply",
    name: "投递经理",
    promise: "针对一个岗位，走完从定制简历到准备材料的流程",
    home: "/apply-agent",
    initial: "投",
    tone: "bg-ink-800",
    records: [
      { href: "/jobs", label: "定向岗位" },
      { href: "/applications", label: "投递看板" },
    ],
  },
];

export const OVERVIEW = { href: "/campaign", label: "战役看板" };

const matches = (pathname: string, href: string) =>
  pathname === href || pathname.startsWith(`${href}/`);

/** The agent a path belongs to, or null for the overview and the account pages. */
export function agentOfPath(pathname: string): Agent | null {
  return (
    AGENTS.find((agent) =>
      [agent.home, ...agent.records.map((r) => r.href), ...(agent.also ?? [])].some((href) =>
        matches(pathname, href),
      ),
    ) ?? null
  );
}

export function agentById(id: AgentId): Agent {
  const agent = AGENTS.find((a) => a.id === id);
  if (!agent) throw new Error(`unknown agent ${id}`);
  return agent;
}
