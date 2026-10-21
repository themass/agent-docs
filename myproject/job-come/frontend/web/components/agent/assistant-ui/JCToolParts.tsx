"use client";

import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { useState } from "react";

import { AgentPlanTodos } from "@/lib/agent-ui-kit/conversation/AgentPlanTodos";
import { useAgentThreadUI } from "@/components/agent/assistant-ui/AgentThreadUIContext";

function JsonBlock({ value }: { value: unknown }) {
  if (value === undefined || value === null) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="mt-1 max-h-32 overflow-auto rounded-md bg-ink-900/5 p-2 font-mono text-micro text-ink-600">
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
    violet: "border-brand-200 bg-brand-50/30",
    blue: "border-brand-200 bg-brand-50/40",
    amber: "border-warn-100 bg-warn-50/40",
    rose: "border-danger-200 bg-danger-50/40",
    sky: "border-brand-200 bg-brand-50/40",
  }[tone];

  return (
    <div className={`rounded-lg border ${border}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left"
      >
        <span className={running ? "animate-spin text-brand-600" : "text-ink-500"}>
          {running ? "◌" : "✓"}
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink-800">{title}</span>
        <span className="text-micro text-ink-500">{open ? "▾" : "▸"}</span>
      </button>
      {open && children ? (
        <div className="space-y-1 border-t border-surface-border px-2.5 py-2">{children}</div>
      ) : null}
    </div>
  );
}

export const JCConfirmTool: ToolCallMessagePartComponent = ({ args, result }) => {
  const { onConfirm } = useAgentThreadUI();
  const confirmId = String(args?.confirm_id ?? "");
  const status = String(result?.status ?? args?.status ?? "pending");

  return (
    <div className="rounded-lg bg-warn-50 p-2.5 text-xs ring-1 ring-inset ring-warn-200">
      <p className="font-medium text-warn-900">确认档案修改</p>
      {status === "pending" && onConfirm ? (
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={() => onConfirm(confirmId, true)}
          >
            确认
          </button>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => onConfirm(confirmId, false)}
          >
            拒绝
          </button>
        </div>
      ) : (
        <p className="label-meta mt-1 text-warn-700">
          {status === "applied" ? "已应用" : status === "rejected" ? "已拒绝" : status}
        </p>
      )}
    </div>
  );
};

export const JCSubagentTool: ToolCallMessagePartComponent = ({ args, result }) => {
  const running = !result;
  const name = String(args?.subagent_type ?? "subagent");
  const description = args?.description ? String(args.description) : undefined;
  return (
    <div
      className={`rounded-lg px-2.5 py-2 ring-1 ring-inset ${running ? "bg-brand-50/50 ring-brand-200" : "bg-surface ring-surface-border"}`}
    >
      <p className="text-xs font-medium text-ink-800">
        {running ? "子 Agent 运行中" : "子 Agent 完成"} · {name}
      </p>
      {description ? (
        <p className="mt-1 text-micro leading-relaxed text-ink-600">{description.slice(0, 200)}</p>
      ) : null}
    </div>
  );
};

export const JCToolFallback: ToolCallMessagePartComponent = ({
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
  if (toolName === "jc_thinking") {
    const content = String((result as { content?: string })?.content ?? args?.preview ?? "");
    return (
      <CollapsibleTool title={`Thinking · ${content.slice(0, 40)}`} tone="amber" running={running}>
        <p className="whitespace-pre-wrap text-xs leading-relaxed text-warn-900">{content}</p>
      </CollapsibleTool>
    );
  }
  if (toolName === "jc_skill") {
    return (
      <CollapsibleTool title={`Skill · ${String(args?.name ?? toolName)}`} tone="sky">
        <JsonBlock value={args} />
      </CollapsibleTool>
    );
  }
  if (toolName === "jc_error") {
    return <p className="rounded-lg bg-danger-50 px-2 py-1.5 text-xs text-danger-700">{String(args?.message ?? "Error")}</p>;
  }

  return (
    <CollapsibleTool title={running ? toolName : `${toolName}`} tone="violet" running={running}>
      {argsText ? <JsonBlock value={argsText} /> : args ? <JsonBlock value={args} /> : null}
      {result ? <JsonBlock value={result} /> : running ? (
        <p className="text-micro text-ink-500">等待工具返回…</p>
      ) : null}
    </CollapsibleTool>
  );
};
