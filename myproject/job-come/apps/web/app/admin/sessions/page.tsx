"use client";

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
      setError(e instanceof Error ? e.message : "加载失败");
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
        .catch((e) => setError(e instanceof Error ? e.message : "加载库存失败"))
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
        setError(e instanceof Error ? e.message : "加载详情失败");
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [selectedId, tab]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-50">
      <div className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-slate-900">Session 审计</h1>
          <p className="text-[11px] text-slate-500">Turn 日志 · Checkpoint prompt · MCP / Tool / Skill</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Admin token（可选）"
            className="w-40 rounded-md border border-slate-200 px-2 py-1 text-[12px]"
          />
          <button
            type="button"
            className="cursor-pointer rounded-md bg-slate-900 px-3 py-1 text-[12px] text-white hover:bg-slate-800"
            onClick={() => {
              setAdminToken(tokenInput.trim());
              void loadSessions();
            }}
          >
            应用
          </button>
        </div>
      </div>

      {error ? <p className="shrink-0 bg-rose-50 px-4 py-1.5 text-[12px] text-rose-700">{error}</p> : null}

      <div className="flex min-h-0 flex-1">
        <aside className="w-72 shrink-0 overflow-y-auto border-r border-slate-200 bg-white">
          <p className="sticky top-0 z-10 border-b border-slate-100 bg-white px-3 py-2 text-[11px] text-slate-500">
            {loading ? "加载中…" : `${sessions.length} / ${total} sessions`}
          </p>
          <ul>
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full cursor-pointer border-b border-slate-50 px-3 py-2 text-left hover:bg-slate-50 ${
                    selectedId === s.id ? "bg-brand-50" : ""
                  }`}
                >
                  <p className="truncate font-mono text-[11px] font-medium text-slate-800">{s.id}</p>
                  <p className="truncate text-[10px] text-slate-500">
                    {s.skill_hint ?? s.kind} · {s.message_count} msgs
                  </p>
                  <p className="text-[10px] text-slate-400">{fmtTime(s.updated_at)}</p>
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
                className={`cursor-pointer rounded-full px-3 py-1 text-[12px] transition ${
                  tab === t
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {t === "timeline" ? "Turn 时间线" : t === "checkpoint" ? "LangGraph Prompt" : "Tool / MCP / Skill"}
              </button>
            ))}
          </div>

          {selected && tab !== "inventory" ? (
            <div className="mb-3 grid gap-x-4 gap-y-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600 sm:grid-cols-2">
              <p>
                <span className="text-slate-400">session</span> <code className="text-slate-800">{selected.id}</code>
              </p>
              <p>
                <span className="text-slate-400">thread</span>{" "}
                <code className="text-slate-800">{selected.deerflow_thread_id}</code>
              </p>
              <p>
                <span className="text-slate-400">user</span> {selected.user_id}
              </p>
              <p>
                <span className="text-slate-400">trace</span> {selected.trace_id ?? "—"}
              </p>
            </div>
          ) : null}

          {detailLoading ? <p className="text-sm text-slate-500">加载详情…</p> : null}

          {tab === "timeline" && !detailLoading ? (
            selectedId ? (
              <TimelinePanel turns={timeline} />
            ) : (
              <p className="text-sm text-slate-500">左侧选择一个 session 查看 Turn 时间线。</p>
            )
          ) : null}

          {tab === "checkpoint" && !detailLoading ? (
            selectedId ? (
              <CheckpointPanel messages={checkpoint} meta={checkpointMeta} />
            ) : (
              <p className="text-sm text-slate-500">左侧选择一个 session 查看 LangGraph Prompt。</p>
            )
          ) : null}

          {tab === "inventory" && !detailLoading && inventory ? <InventoryPanel inventory={inventory} /> : null}
        </main>
      </div>
    </div>
  );
}
