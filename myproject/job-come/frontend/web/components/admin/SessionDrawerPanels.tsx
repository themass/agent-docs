"use client";

import { useEffect, useRef, useState } from "react";

import {
  getAdminSessionMessages,
  getAdminSessionTrace,
  type AdminMessageItem,
  type AdminTraceItem,
} from "@/lib/api/admin";
import { downloadTextFile } from "@/lib/clipboard";
import { formatDateTime } from "@/lib/datetime";
import { userFacingApiError } from "@/lib/api/user-error";

function RoleTag({ role }: { role: string }) {
  const tone =
    role === "user" ? "badge-brand" : role === "assistant" ? "badge-success" : "badge-neutral";
  return <span className={`badge ${tone}`}>{role}</span>;
}

function ExportButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="btn btn-sm btn-ghost shrink-0 text-ink-600 disabled:opacity-40"
    >
      导出 txt
    </button>
  );
}

function exportFilename(sessionId: string, kind: "messages" | "trace"): string {
  const ts = formatDateTime(new Date().toISOString()).replace(/[: ]/g, "-");
  return `jc_${kind}_${sessionId}_${ts}.txt`;
}

function formatMessagesAsText(sessionId: string, messages: AdminMessageItem[]): string {
  const lines: string[] = [`session: ${sessionId}`, `messages: ${messages.length}`, "=".repeat(60)];
  for (const m of messages) {
    lines.push(
      "",
      `[${formatDateTime(m.created_at)}] ${m.role} · ${m.event_type} (id=${m.id})`,
      m.content ?? "（无文本内容）",
    );
    if (m.payload) {
      lines.push("--- payload ---", JSON.stringify(m.payload, null, 2));
    }
    lines.push("-".repeat(60));
  }
  return lines.join("\n");
}

function formatTraceAsText(sessionId: string, events: AdminTraceItem[]): string {
  const lines: string[] = [`session: ${sessionId}`, `events: ${events.length}`, "=".repeat(60)];
  for (const ev of events) {
    lines.push(
      "",
      `#${ev.seq} [${formatDateTime(ev.created_at)}] ${ev.role} · ${ev.event_type} (id=${ev.id})`,
      `trace_id=${ev.trace_id ?? "—"} llm_call_id=${ev.llm_call_id ?? "—"} user_id=${ev.user_id ?? "—"}`,
      "--- payload ---",
      JSON.stringify(ev.payload, null, 2),
      "-".repeat(60),
    );
  }
  return lines.join("\n");
}

/** Message list (`jc_agent_message`, the UI projection) — click a row to expand its payload. */
export function MessageListPanel({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<AdminMessageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExpandedId(null);
    void getAdminSessionMessages(sessionId)
      .then((res) => setMessages(res.messages))
      .catch((e) => setError(userFacingApiError(e, "加载消息列表失败")))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <p className="text-sm text-ink-500">加载中…</p>;
  if (error)
    return (
      <p className="notice notice-warn text-xs" role="alert">
        {error}
      </p>
    );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-500">{messages.length} 条消息</p>
        <ExportButton
          disabled={messages.length === 0}
          onClick={() =>
            downloadTextFile(exportFilename(sessionId, "messages"), formatMessagesAsText(sessionId, messages))
          }
        />
      </div>
      {messages.length === 0 ? (
        <p className="text-sm text-ink-500">这个会话还没有消息。</p>
      ) : (
        <ul className="space-y-1.5">
          {messages.map((m) => {
            const expanded = expandedId === m.id;
            return (
              <li key={m.id} className="card overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : m.id)}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-ink-50"
                >
                  <RoleTag role={m.role} />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 block text-sm text-ink-800">
                      {m.content || <span className="text-ink-400">（无文本内容，{m.event_type}）</span>}
                    </span>
                    <span className="mt-0.5 block text-micro text-ink-500">
                      {m.event_type} · {formatDateTime(m.created_at)}
                    </span>
                  </span>
                </button>
                {expanded ? (
                  <div className="border-t border-surface-border bg-surface-sunken px-3 py-2">
                    {m.payload ? (
                      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all font-mono text-micro text-ink-700">
                        {JSON.stringify(m.payload, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-xs text-ink-500">没有附加 payload。</p>
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function isFailure(ev: AdminTraceItem): boolean {
  return ev.event_type === "error";
}

/** `ExceptionType @stage` for a failed run, or "" for anything else.
 *
 * Reads the keys the harness writes alongside `message` on an `error` event
 * (`exception_type` / `stage`). Returns "" rather than a placeholder when they
 * are absent, because rows written before those keys existed are still valid
 * history and should not be decorated with a fake diagnosis.
 */
function failureSummary(ev: AdminTraceItem): string {
  if (!isFailure(ev)) return "";
  const payload = (ev.payload ?? {}) as Record<string, unknown>;
  const type = typeof payload.exception_type === "string" ? payload.exception_type : "";
  const stage = typeof payload.stage === "string" ? payload.stage : "";
  if (!type) return "";
  return stage ? `${type} @${stage}` : type;
}

/** Full event ledger (`jc_agent_trace`) — same rows `trace.jsonl` exports, read inline.
 *
 * `focusLlmCallId`: deep link from the LLM 调用 admin page's "查看调用链" button.
 * When set, the first matching row (same `llm_call_id`) auto-expands and
 * scrolls into view instead of leaving the operator to scan a 5000-row ledger
 * by eye for the one call they came here to look at.
 */
export function TraceListPanel({
  sessionId,
  focusLlmCallId = null,
}: {
  sessionId: string;
  focusLlmCallId?: string | null;
}) {
  const [events, setEvents] = useState<AdminTraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const focusRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExpandedId(null);
    void getAdminSessionTrace(sessionId)
      .then((res) => {
        setEvents(res.events);
        if (focusLlmCallId) {
          const match = res.events.find((ev) => ev.llm_call_id === focusLlmCallId);
          if (match) setExpandedId(match.id);
        }
      })
      .catch((e) => setError(userFacingApiError(e, "加载事件账本失败")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, focusLlmCallId]);

  useEffect(() => {
    if (expandedId && focusLlmCallId) {
      focusRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [expandedId, focusLlmCallId]);

  if (loading) return <p className="text-sm text-ink-500">加载中…</p>;
  if (error)
    return (
      <p className="notice notice-warn text-xs" role="alert">
        {error}
      </p>
    );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-500">{events.length} 条事件</p>
        <ExportButton
          disabled={events.length === 0}
          onClick={() =>
            downloadTextFile(exportFilename(sessionId, "trace"), formatTraceAsText(sessionId, events))
          }
        />
      </div>
      {events.length === 0 ? (
        <p className="text-sm text-ink-500">这个会话还没有事件记录。</p>
      ) : (
        <ul className="space-y-1.5">
          {events.map((ev) => {
            const expanded = expandedId === ev.id;
            const isFocusTarget = focusLlmCallId != null && ev.llm_call_id === focusLlmCallId;
            return (
              <li
                key={ev.id}
                ref={isFocusTarget ? focusRef : undefined}
                className={`card overflow-hidden ${
                  isFocusTarget ? "ring-2 ring-inset ring-brand-400" : ""
                } ${isFailure(ev) ? "border-danger-200 bg-danger-50/40" : ""}`}
              >
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : ev.id)}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-ink-50"
                >
                  <span className="shrink-0 font-mono text-micro text-ink-400">#{ev.seq}</span>
                  <RoleTag role={ev.role} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink-800">
                      {ev.event_type}
                      {/* A failed run's exception type is promoted into the collapsed
                          row. A 5000-row ledger has exactly one row worth finding
                          when a user reports "agent 又失败了", and requiring a click
                          per row to find it is why these failures went undiagnosed. */}
                      {failureSummary(ev) ? (
                        <span className="ml-1.5 font-mono text-micro font-normal text-danger-600">
                          {failureSummary(ev)}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block text-micro text-ink-500">{formatDateTime(ev.created_at)}</span>
                  </span>
                </button>
                {expanded ? (
                  <div className="border-t border-surface-border bg-surface-sunken px-3 py-2">
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all font-mono text-micro text-ink-700">
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
