"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useCallback, useEffect, useState } from "react";

import { CheckpointPanel, InventoryPanel, TimelinePanel } from "@/components/admin/SessionAuditPanels";
import {
  getAdminCheckpoint,
  getAdminInventory,
  getAdminTimeline,
  getAdminToken,
  listAdminSessions,
  setAdminToken,
  type AdminCheckpointMessage,
  type AdminInventory,
  type AdminSessionListItem,
  type AdminTimelineTurn,
} from "@/lib/api/admin";

type Tab = "timeline" | "checkpoint" | "inventory";

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

export default function AdminSessionsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState(() => getAdminToken());
  const [sessions, setSessions] = useState<AdminSessionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("timeline");
  const [timeline, setTimeline] = useState<AdminTimelineTurn[]>([]);
  const [checkpoint, setCheckpoint] = useState<AdminCheckpointMessage[]>([]);
  const [checkpointMeta, setCheckpointMeta] = useState<{ count: number; thread: string } | null>(null);
  const [inventory, setInventory] = useState<AdminInventory | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const selected = sessions.find((s) => s.id === selectedId) ?? null;

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAdminSessions({ limit: 100 });
      setSessions(res.sessions);
      setTotal(res.total);
    } catch (e) {
      setError(userFacingApiError(e, "加载失败"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (tab === "inventory") {
      setDetailLoading(true);
      setError(null);
      void getAdminInventory()
        .then(setInventory)
        .catch((e) => setError(userFacingApiError(e, "加载库存失败")))
        .finally(() => setDetailLoading(false));
      return;
    }
    if (!selectedId) return;
    setDetailLoading(true);
    setError(null);
    void (async () => {
      try {
        if (tab === "timeline") {
          const res = await getAdminTimeline(selectedId);
          setTimeline(res.turns);
        } else {
          const res = await getAdminCheckpoint(selectedId);
          setCheckpoint(res.messages);
          setCheckpointMeta({ count: res.checkpoint_count, thread: res.deerflow_thread_id });
        }
      } catch (e) {
        setError(userFacingApiError(e, "加载详情失败"));
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [selectedId, tab]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl bg-surface-sunken shadow-card ring-1 ring-inset ring-surface-border">
      <div className="flex shrink-0 items-center gap-3 border-b border-surface-border bg-surface px-4 py-2">
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-ink-900">Session 审计</h1>
          <p className="text-xs text-ink-500">Turn 日志 · Checkpoint prompt · MCP / Tool / Skill</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Admin token（可选）"
            className="field h-7 w-40 py-0 text-xs"
          />
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={() => {
              setAdminToken(tokenInput.trim());
              void loadSessions();
            }}
          >
            应用
          </button>
        </div>
      </div>

      {error ? <p className="shrink-0 bg-danger-50 px-4 py-1.5 text-xs text-danger-700" role="alert">
          {error}
        </p> : null}

      <div className="flex min-h-0 flex-1">
        <aside className="w-72 shrink-0 overflow-y-auto border-r border-surface-border bg-surface">
          <p className="sticky top-0 z-10 border-b border-surface-border bg-surface px-3 py-2 text-xs text-ink-500">
            {loading ? "加载中…" : `${sessions.length} / ${total} sessions`}
          </p>
          <ul>
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full cursor-pointer border-b border-surface-border px-3 py-2 text-left transition hover:bg-ink-50 ${
                    selectedId === s.id
                      ? "bg-brand-50 shadow-[inset_2px_0_0_0_theme(colors.brand.600)]"
                      : ""
                  }`}
                >
                  <p className="truncate font-mono text-xs font-medium text-ink-800">{s.id}</p>
                  <p className="truncate text-micro text-ink-500">
                    {s.skill_hint ?? s.kind} · {s.message_count} msgs
                  </p>
                  <p className="text-micro text-ink-500">{fmtTime(s.updated_at)}</p>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {(["timeline", "checkpoint", "inventory"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={`cursor-pointer rounded-md px-3 py-1 text-xs font-medium transition ${
                  tab === t
                    ? "bg-brand-600 text-white shadow-xs"
                    : "bg-surface text-ink-600 ring-1 ring-inset ring-surface-border hover:bg-ink-50"
                }`}
              >
                {t === "timeline" ? "Turn 时间线" : t === "checkpoint" ? "LangGraph Prompt" : "Tool / MCP / Skill"}
              </button>
            ))}
          </div>

          {selected && tab !== "inventory" ? (
            <div className="card mb-3 grid gap-x-4 gap-y-1 px-3 py-2 text-xs text-ink-600 sm:grid-cols-2">
              <p>
                <span className="text-ink-500">session</span> <code className="text-ink-800">{selected.id}</code>
              </p>
              <p>
                <span className="text-ink-500">thread</span>{" "}
                <code className="text-ink-800">{selected.deerflow_thread_id}</code>
              </p>
              <p>
                <span className="text-ink-500">user</span> {selected.user_id}
              </p>
              <p>
                <span className="text-ink-500">trace</span> {selected.trace_id ?? "—"}
              </p>
            </div>
          ) : null}

          {detailLoading ? <p className="text-sm text-ink-500">加载详情…</p> : null}

          {tab === "timeline" && !detailLoading ? (
            selectedId ? (
              <TimelinePanel turns={timeline} />
            ) : (
              <p className="text-sm text-ink-500">左侧选择一个 session 查看 Turn 时间线。</p>
            )
          ) : null}

          {tab === "checkpoint" && !detailLoading ? (
            selectedId ? (
              <CheckpointPanel messages={checkpoint} meta={checkpointMeta} />
            ) : (
              <p className="text-sm text-ink-500">左侧选择一个 session 查看 LangGraph Prompt。</p>
            )
          ) : null}

          {tab === "inventory" && !detailLoading && inventory ? <InventoryPanel inventory={inventory} /> : null}
        </main>
      </div>
    </div>
  );
}
