"use client";

import { useState } from "react";

import { AgentMark } from "@/components/agent/AgentMark";
import { AgentPlanTodos } from "@/components/agent/AgentPlanTodos";
import { AgentUserBubble } from "@/components/agent/AgentUserBubble";
import type { AgentTurn, TurnActivity } from "@/lib/agent-turn-model";
import type { AgentDisplayItem } from "@/lib/types/agent";

function JsonBlock({ value }: { value: unknown }) {
  if (value === undefined || value === null) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="mt-1 max-h-32 overflow-auto rounded-md bg-slate-900/5 p-2 font-mono text-[10px] text-slate-600">
      {text.slice(0, 2000)}
    </pre>
  );
}

function ActivityLine({ activity, expanded, onToggle }: { activity: TurnActivity; expanded: boolean; onToggle: () => void }) {
  if (activity.kind === "skill") {
    return (
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-sky-50/80">
        <span className="text-sky-600">⚡</span>
        <span className="min-w-0 flex-1 text-[11px] font-medium text-slate-800">Skill · {activity.name}</span>
        <span className="text-[10px] text-slate-400">{expanded ? "▾" : "▸"}</span>
      </button>
    );
  }
  if (activity.kind === "thinking") {
    return (
      <div className="rounded-lg border border-amber-100 bg-amber-50/40">
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className="text-amber-600">◌</span>
          <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-amber-900">
            Thinking · {activity.content.slice(0, 48) || "…"}
          </span>
          <span className="text-[10px] text-slate-400">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <p className="border-t border-amber-100 px-2.5 py-2 text-[11px] leading-relaxed text-amber-950 whitespace-pre-wrap">
            {activity.content}
          </p>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "plan") {
    return <AgentPlanTodos todos={activity.todos as Array<{ content?: string; status?: string; id?: string }>} />;
  }
  if (activity.kind === "subagent") {
    const running = activity.state === "running";
    return (
      <div className={`rounded-lg border px-2.5 py-2 ${running ? "border-blue-200 bg-blue-50/40" : "border-slate-200 bg-white"}`}>
        <p className="text-[11px] font-medium text-slate-800">
          {running ? "子 Agent 运行中" : "子 Agent 完成"} · {activity.name}
        </p>
        {activity.description ? (
          <p className="mt-1 text-[10px] leading-relaxed text-slate-600">{String(activity.description).slice(0, 200)}</p>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "tool") {
    const { tool } = activity;
    const running = tool.state === "running";
    return (
      <div className={`rounded-lg border ${running ? "border-violet-200 bg-violet-50/30" : "border-slate-200 bg-white"}`}>
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className={running ? "animate-spin text-violet-600" : tool.state === "error" ? "text-rose-600" : "text-emerald-600"}>
            {running ? "◌" : tool.state === "error" ? "!" : "✓"}
          </span>
          <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-slate-800">
            {running ? `${tool.name}` : tool.name}
          </span>
          <span className="text-[10px] text-slate-400">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <div className="space-y-1 border-t border-slate-100 px-2.5 py-2">
            {tool.args ? <JsonBlock value={tool.args} /> : null}
            {tool.result ? <JsonBlock value={tool.result} /> : running ? (
              <p className="text-[10px] text-slate-400">等待工具返回…</p>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "error") {
    return <p className="rounded-lg bg-rose-50 px-2 py-1.5 text-[11px] text-rose-700">{activity.message}</p>;
  }
  return null;
}

function UserBubble({ item }: { item: Extract<AgentDisplayItem, { kind: "user" }> }) {
  return <AgentUserBubble content={item.content} attachments={item.attachments} />;
}

function AssistantBubble({ item }: { item: Extract<AgentDisplayItem, { kind: "assistant" }> }) {
  return (
    <div className="flex items-start gap-2">
      <AgentMark size={24} className="mt-0.5" />
      <div className="max-w-[calc(100%-2rem)] rounded-2xl rounded-tl-md border border-slate-200/80 bg-white px-3 py-2 text-[13px] leading-relaxed text-slate-800">
        {item.content || (item.streaming ? "…" : "")}
        {item.streaming ? <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-brand-500 align-middle" /> : null}
      </div>
    </div>
  );
}

export function AgentLoopCard({
  turn,
  onConfirm,
}: {
  turn: AgentTurn;
  onConfirm?: (confirmId: string, approved: boolean) => void;
}) {
  const [open, setOpen] = useState(turn.streaming || turn.activities.some((a) => a.kind === "tool" && a.tool.state === "running"));
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const hasActivity = turn.activities.length > 0;
  const runningTools = turn.activities.filter((a) => a.kind === "tool" && a.tool.state === "running").length;
  const headline = turn.streaming
    ? runningTools > 0
      ? `正在调用 ${runningTools} 个工具…`
      : "Agent 正在思考…"
    : hasActivity
      ? `已完成 ${turn.activities.length} 个步骤`
      : null;

  return (
    <div className="space-y-2">
      {turn.user ? <UserBubble item={turn.user} /> : null}

      {hasActivity && headline ? (
        <div className="rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05)]">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left"
          >
            <span className="flex gap-0.5" aria-hidden>
              <span className="size-1.5 animate-bounce rounded-full bg-sky-500 [animation-delay:-0.2s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-sky-500 [animation-delay:-0.1s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-sky-500" />
            </span>
            <span className="min-w-0 flex-1 text-[11px] font-medium text-slate-700">{headline}</span>
            <span className="text-[10px] text-slate-400">{open ? "收起" : "展开"}</span>
          </button>
          {open ? (
            <div className="space-y-1.5 border-t border-slate-100 px-2 py-2">
              {turn.activities.map((activity) => {
                if (activity.kind === "confirm" && onConfirm) {
                  const item = activity.item;
                  return (
                    <div key={item.id} className="rounded-xl border border-amber-200 bg-amber-50/50 p-2.5 text-[12px]">
                      <p className="font-medium text-amber-900">确认档案修改</p>
                      {item.status === "pending" ? (
                        <div className="mt-2 flex gap-2">
                          <button type="button" className="rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] text-white" onClick={() => onConfirm(item.confirmId, true)}>确认</button>
                          <button type="button" className="rounded-lg border border-slate-300 px-2.5 py-1 text-[11px]" onClick={() => onConfirm(item.confirmId, false)}>拒绝</button>
                        </div>
                      ) : (
                        <p className="mt-1 text-[10px] uppercase text-amber-800">{item.status === "applied" ? "已应用" : "已拒绝"}</p>
                      )}
                    </div>
                  );
                }
                const key =
                  activity.kind === "tool"
                    ? activity.tool.id
                    : activity.kind === "confirm"
                      ? activity.item.id
                      : activity.id;
                const isOpen = expanded[key] ?? activity.kind === "thinking";
                return (
                  <ActivityLine
                    key={key}
                    activity={activity}
                    expanded={isOpen}
                    onToggle={() => setExpanded((prev) => ({ ...prev, [key]: !isOpen }))}
                  />
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      {turn.assistant ? <AssistantBubble item={turn.assistant} /> : null}
    </div>
  );
}
