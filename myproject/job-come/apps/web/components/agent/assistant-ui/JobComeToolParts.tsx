"use client";

import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { useState } from "react";

import { AgentPlanTodos } from "@/components/agent/AgentPlanTodos";
import { useAgentThreadUI } from "@/components/agent/assistant-ui/AgentThreadUIContext";

function JsonBlock({ value }: { value: unknown }) {
  if (value === undefined || value === null) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="mt-1 max-h-32 overflow-auto rounded-md bg-slate-900/5 p-2 font-mono text-[10px] text-slate-600">
      {text.slice(0, 2000)}
    </pre>
  );
}

function CollapsibleTool({
  title,
  tone,
  running,
  children,
}: {
  title: string;
  tone: "violet" | "blue" | "amber" | "rose" | "sky";
  running?: boolean;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(running ?? false);
  const border = {
    violet: "border-violet-200 bg-violet-50/30",
    blue: "border-blue-200 bg-blue-50/40",
    amber: "border-amber-100 bg-amber-50/40",
    rose: "border-rose-200 bg-rose-50/40",
    sky: "border-sky-200 bg-sky-50/40",
  }[tone];

  return (
    <div className={`rounded-lg border ${border}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left"
      >
        <span className={running ? "animate-spin text-violet-600" : "text-slate-500"}>
          {running ? "◌" : "✓"}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-slate-800">{title}</span>
        <span className="text-[10px] text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && children ? (
        <div className="space-y-1 border-t border-slate-100 px-2.5 py-2">{children}</div>
      ) : null}
    </div>
  );
}

export const JobComeConfirmTool: ToolCallMessagePartComponent = ({ args, result }) => {
  const { onConfirm } = useAgentThreadUI();
  const confirmId = String(args?.confirm_id ?? "");
  const status = String(result?.status ?? args?.status ?? "pending");

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-2.5 text-[12px]">
      <p className="font-medium text-amber-900">确认档案修改</p>
      {status === "pending" && onConfirm ? (
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] text-white"
            onClick={() => onConfirm(confirmId, true)}
          >
            确认
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-2.5 py-1 text-[11px]"
            onClick={() => onConfirm(confirmId, false)}
          >
            拒绝
          </button>
        </div>
      ) : (
        <p className="mt-1 text-[10px] uppercase text-amber-800">
          {status === "applied" ? "已应用" : status === "rejected" ? "已拒绝" : status}
        </p>
      )}
    </div>
  );
};

export const JobComeSubagentTool: ToolCallMessagePartComponent = ({ args, result }) => {
  const running = !result;
  const name = String(args?.subagent_type ?? "subagent");
  const description = args?.description ? String(args.description) : undefined;
  return (
    <div
      className={`rounded-lg border px-2.5 py-2 ${running ? "border-blue-200 bg-blue-50/40" : "border-slate-200 bg-white"}`}
    >
      <p className="text-[11px] font-medium text-slate-800">
        {running ? "子 Agent 运行中" : "子 Agent 完成"} · {name}
      </p>
      {description ? (
        <p className="mt-1 text-[10px] leading-relaxed text-slate-600">{description.slice(0, 200)}</p>
      ) : null}
    </div>
  );
};

export const JobComeToolFallback: ToolCallMessagePartComponent = ({
  toolName,
  args,
  argsText,
  result,
}) => {
  const running = result === undefined;
  if (toolName === "write_todos") {
    const todos = (args?.todos as Array<{ content?: string; status?: string }>) ?? [];
    return <AgentPlanTodos todos={todos} />;
  }
  if (toolName === "jobcome_thinking") {
    const content = String((result as { content?: string })?.content ?? args?.preview ?? "");
    return (
      <CollapsibleTool title={`Thinking · ${content.slice(0, 40)}`} tone="amber" running={running}>
        <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-amber-950">{content}</p>
      </CollapsibleTool>
    );
  }
  if (toolName === "jobcome_skill") {
    return (
      <CollapsibleTool title={`Skill · ${String(args?.name ?? toolName)}`} tone="sky">
        <JsonBlock value={args} />
      </CollapsibleTool>
    );
  }
  if (toolName === "jobcome_error") {
    return <p className="rounded-lg bg-rose-50 px-2 py-1.5 text-[11px] text-rose-700">{String(args?.message ?? "Error")}</p>;
  }

  return (
    <CollapsibleTool title={running ? toolName : `${toolName}`} tone="violet" running={running}>
      {argsText ? <JsonBlock value={argsText} /> : args ? <JsonBlock value={args} /> : null}
      {result ? <JsonBlock value={result} /> : running ? (
        <p className="text-[10px] text-slate-400">等待工具返回…</p>
      ) : null}
    </CollapsibleTool>
  );
};
