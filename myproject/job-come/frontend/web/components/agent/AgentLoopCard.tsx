"use client";

import { useState } from "react";

import { AgentMark } from "@/components/agent/AgentMark";
import { AgentPlanTodos } from "@/components/agent/AgentPlanTodos";
import { AgentUserBubble } from "@/components/agent/AgentUserBubble";
import type { AgentTurn, TurnActivity } from "@/lib/agent-turn-model";
import { ZHOUKA_NAME } from "@/lib/brand";
import type { AgentDisplayItem } from "@/lib/types/agent";

function JsonBlock({ value }: { value: unknown }) {
  if (value === undefined || value === null) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="scroll-area mt-1 max-h-32 overflow-auto rounded-md bg-surface-sunken p-2 font-mono text-micro leading-relaxed text-ink-600 ring-1 ring-inset ring-surface-border">
      {text.slice(0, 2000)}
    </pre>
  );
}

function ActivityLine({ activity, expanded, onToggle }: { activity: TurnActivity; expanded: boolean; onToggle: () => void }) {
  if (activity.kind === "skill") {
    return (
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-brand-50/70">
        <span className="text-brand-600">⚡</span>
        <span className="min-w-0 flex-1 text-xs font-medium text-ink-800">Skill · {activity.name}</span>
        <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
      </button>
    );
  }
  if (activity.kind === "thinking") {
    return (
      <div className="rounded-lg bg-warn-50/50 ring-1 ring-inset ring-warn-100">
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className="text-warn-600">◌</span>
          <span className="min-w-0 flex-1 truncate text-xs font-medium text-warn-900">
            Thinking · {activity.content.slice(0, 48) || "…"}
          </span>
          <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <p className="whitespace-pre-wrap border-t border-warn-100 px-2.5 py-2 text-xs leading-relaxed text-warn-900">
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
      <div className={`rounded-lg px-2.5 py-2 ring-1 ring-inset ${running ? "bg-brand-50/50 ring-brand-200" : "bg-surface ring-surface-border"}`}>
        <p className="text-xs font-medium text-ink-800">
          {running ? "子 Agent 运行中" : "子 Agent 完成"} · {activity.name}
        </p>
        {activity.description ? (
          <p className="mt-1 text-micro leading-relaxed text-ink-600">{String(activity.description).slice(0, 200)}</p>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "tool") {
    const { tool } = activity;
    const running = tool.state === "running";
    return (
      <div className={`rounded-lg ring-1 ring-inset ${running ? "bg-brand-50/40 ring-brand-200" : "bg-surface ring-surface-border"}`}>
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className={running ? "animate-spin text-brand-600" : tool.state === "error" ? "text-danger-600" : "text-success-600"}>
            {running ? "◌" : tool.state === "error" ? "!" : "✓"}
          </span>
          <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink-800">
            {running ? `${tool.name}` : tool.name}
          </span>
          <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <div className="space-y-1 border-t border-surface-border px-2.5 py-2">
            {tool.args ? <JsonBlock value={tool.args} /> : null}
            {tool.result ? <JsonBlock value={tool.result} /> : running ? (
              <p className="text-micro text-ink-500">等待工具返回…</p>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "error") {
    return (
      <p className="rounded-lg bg-danger-50 px-2.5 py-1.5 text-xs leading-relaxed text-danger-700 ring-1 ring-inset ring-danger-100">
        {activity.message}
      </p>
    );
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
      <div className="max-w-[calc(100%-2rem)] rounded-xl rounded-tl-sm border border-surface-border bg-surface px-3.5 py-2.5 text-sm leading-relaxed text-ink-800 shadow-xs">
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
      : `${ZHOUKA_NAME}正在思考…`
    : hasActivity
      ? `已完成 ${turn.activities.length} 个步骤`
      : null;

  return (
    <div className="space-y-2">
      {turn.user ? <UserBubble item={turn.user} /> : null}

      {hasActivity && headline ? (
        <div className="rounded-xl border border-surface-border bg-surface shadow-xs">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left"
          >
            <span className="flex gap-0.5" aria-hidden>
              <span className="size-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.2s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.1s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-brand-500" />
            </span>
            <span className="min-w-0 flex-1 text-xs font-medium text-ink-700">{headline}</span>
            <span className="text-micro text-ink-500">{open ? "收起" : "展开"}</span>
          </button>
          {open ? (
            <div className="space-y-1.5 border-t border-surface-border px-2 py-2">
              {turn.activities.map((activity) => {
                if (activity.kind === "confirm" && onConfirm) {
                  const item = activity.item;
                  return (
                    <div key={item.id} className="rounded-xl bg-warn-50/60 p-3 text-xs ring-1 ring-inset ring-warn-200">
                      <p className="font-medium text-warn-900">确认档案修改</p>
                      {item.status === "pending" ? (
                        <div className="mt-2 flex gap-2">
                          <button type="button" className="btn btn-sm btn-primary" onClick={() => onConfirm(item.confirmId, true)}>确认</button>
                          <button type="button" className="btn btn-sm btn-secondary" onClick={() => onConfirm(item.confirmId, false)}>拒绝</button>
                        </div>
                      ) : (
                        <p className="mt-1 text-micro uppercase text-warn-900">{item.status === "applied" ? "已应用" : "已拒绝"}</p>
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
