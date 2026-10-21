"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { Suspense, useCallback, useEffect, useState } from "react";

import { Select } from "@/components/ui/Select";
import { useSearchParams } from "next/navigation";

import { AdminDrawer } from "@/components/admin/AdminDrawer";
import { CheckpointPanel, InventoryPanel, TimelinePanel } from "@/components/admin/SessionAuditPanels";
import { MessageListPanel, TraceListPanel } from "@/components/admin/SessionDrawerPanels";
import {
  getAdminCheckpoint,
  getAdminInventory,
  getAdminSession,
  getAdminTimeline,
  listAdminSessions,
  type AdminCheckpointMessage,
  type AdminInventory,
  type AdminSessionListItem,
  type AdminTimelineTurn,
} from "@/lib/api/admin";
import { formatDateTime } from "@/lib/datetime";

type Tab = "timeline" | "checkpoint" | "inventory";
type DrawerTab = "messages" | "trace";

function AdminSessionsInner() {
  const searchParams = useSearchParams();
  const focusSessionId = searchParams.get("session_id");
  const focusLlmCallId = searchParams.get("llm_call_id");

  const [selectedId, setSelectedId] = useState<string | null>(focusSessionId);
  const [sessions, setSessions] = useState<AdminSessionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  // The session list is a card rail, not a table, so the order is picked from
  // a control rather than by clicking a column header.
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("timeline");
  const [timeline, setTimeline] = useState<AdminTimelineTurn[]>([]);
  const [checkpoint, setCheckpoint] = useState<AdminCheckpointMessage[]>([]);
  const [checkpointMeta, setCheckpointMeta] = useState<{ count: number; thread: string } | null>(null);
  const [inventory, setInventory] = useState<AdminInventory | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // A `?llm_call_id=` deep link (from the LLM 调用 admin page's "查看调用链"
  // button) opens straight into the trace drawer instead of leaving the
  // operator to find the right session and click into it manually.
  const [drawerSessionId, setDrawerSessionId] = useState<string | null>(
    focusLlmCallId ? focusSessionId : null,
  );
  const [drawerTab, setDrawerTab] = useState<DrawerTab>(focusLlmCallId ? "trace" : "messages");

  const selected = sessions.find((s) => s.id === selectedId) ?? null;
  const drawerSession = sessions.find((s) => s.id === drawerSessionId) ?? null;

  const loadSessions = useCallback(
    async (searchTerm: string, order: { sortBy: string; sortDir: "asc" | "desc" }) => {
      setLoading(true);
      setError(null);
      try {
        const res = await listAdminSessions({
          limit: 100,
          search: searchTerm || undefined,
          sort_by: order.sortBy,
          sort_dir: order.sortDir,
        });
        setSessions(res.sessions);
        setTotal(res.total);
        setSortBy(res.sort_by);
        setSortDir(res.sort_dir);
        // A link from elsewhere (e.g. 舟卡's own history drawer) can point at a
        // session outside the first page. Fetch it directly and splice it in so
        // the deep link always resolves instead of silently landing on nothing.
        if (!searchTerm && focusSessionId && !res.sessions.some((s) => s.id === focusSessionId)) {
          try {
            const found = await getAdminSession(focusSessionId);
            setSessions((prev) => [found, ...prev]);
          } catch {
            setError(`未找到 session ${focusSessionId}，可能已被清理或 id 有误。`);
          }
        }
      } catch (e) {
        setError(userFacingApiError(e, "加载失败"));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [focusSessionId],
  );

  useEffect(() => {
    void loadSessions(search.trim(), { sortBy, sortDir });
    // Search is submitted explicitly; this re-runs on order changes only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadSessions, sortBy, sortDir]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    void loadSessions(search.trim(), { sortBy, sortDir });
  }

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
        <form onSubmit={onSearchSubmit} className="ml-auto flex items-center gap-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="按 session id / thread id / 用户邮箱搜索"
            className="field h-8 w-64 py-0 text-xs"
          />
          <button type="submit" className="btn btn-sm btn-secondary">
            搜索
          </button>
          <Select
            aria-label="排序字段"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="w-32"
            selectClassName="h-8 py-0 text-xs"
          >
            <option value="updated_at">最近活跃</option>
            <option value="created_at">创建时间</option>
            <option value="status">状态</option>
            <option value="kind">类型</option>
            <option value="skill_hint">技能</option>
            <option value="user_id">用户</option>
            <option value="id">session id</option>
          </Select>
          <button
            type="button"
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
            className="btn btn-sm btn-secondary"
            aria-label={sortDir === "desc" ? "当前为降序，点击改为升序" : "当前为升序，点击改为降序"}
            title={sortDir === "desc" ? "降序" : "升序"}
          >
            {sortDir === "desc" ? "↓" : "↑"}
          </button>
        </form>
      </div>

      {error ? (
        <p className="shrink-0 bg-danger-50 px-4 py-1.5 text-xs text-danger-700" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <aside className="w-72 shrink-0 overflow-y-auto border-r border-surface-border bg-surface">
          <p className="sticky top-0 z-10 border-b border-surface-border bg-surface px-3 py-2 text-xs text-ink-500">
            {loading ? "加载中…" : `${sessions.length} / ${total} sessions`}
          </p>
          <ul>
            {sessions.map((s) => (
              <li key={s.id}>
                <div
                  className={`group flex items-stretch border-b border-surface-border transition hover:bg-ink-50 ${
                    selectedId === s.id
                      ? "bg-brand-50 shadow-[inset_2px_0_0_0_theme(colors.brand.600)]"
                      : ""
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedId(s.id)}
                    className="min-w-0 flex-1 cursor-pointer px-3 py-2 text-left"
                  >
                    <p className="select-text truncate font-mono text-xs font-medium text-ink-800">
                      {s.id}
                    </p>
                    <p className="select-text truncate text-micro text-ink-600">
                      {s.user_display_name ?? s.user_email ?? s.user_id}
                    </p>
                    <p className="truncate text-micro text-ink-500">
                      {s.skill_hint ?? s.kind} · {s.message_count} msgs
                    </p>
                    <p className="select-text text-micro text-ink-500">{formatDateTime(s.updated_at)}</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(s.id);
                      setDrawerSessionId(s.id);
                      setDrawerTab("messages");
                    }}
                    title="查看消息 / 事件账本"
                    className="shrink-0 px-2 text-ink-400 transition hover:text-brand-600"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                      <path d="M6 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm0 4a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm0 4a1 1 0 011-1h4a1 1 0 110 2H7a1 1 0 01-1-1z" />
                    </svg>
                  </button>
                </div>
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
              <p className="select-text">
                <span className="text-ink-500">session</span> <code className="text-ink-800">{selected.id}</code>
              </p>
              <p className="select-text">
                <span className="text-ink-500">thread</span>{" "}
                <code className="text-ink-800">{selected.deerflow_thread_id}</code>
              </p>
              <p className="select-text">
                <span className="text-ink-500">user</span> {selected.user_id}
              </p>
              <p className="select-text">
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

      <AdminDrawer
        open={drawerSessionId !== null}
        onClose={() => setDrawerSessionId(null)}
        title={drawerSessionId ?? ""}
        subtitle={
          drawerSession
            ? [
                drawerSession.skill_hint ?? drawerSession.kind,
                drawerSession.user_display_name ?? drawerSession.user_email,
                drawerSession.user_id,
              ]
                .filter(Boolean)
                .join(" · ")
            : undefined
        }
      >
        <div className="mb-1.5 segment">
          {(["messages", "trace"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setDrawerTab(t)}
              className={`segment-item ${drawerTab === t ? "segment-item-active" : ""}`}
            >
              {t === "messages" ? "Message 列表" : "Trace 列表"}
            </button>
          ))}
        </div>
        <p className="mb-3 text-micro text-ink-500">
          {drawerTab === "messages"
            ? "面向展示的会话记录：每条是一次用户/舟卡回复，内容是可读文本，适合快速看对话走向。"
            : "完整事件账本：每个事件（含工具调用、思考、错误）按发生顺序记录，带 trace_id / llm_call_id，用于排障和还原调用链。"}
        </p>
        {drawerSessionId ? (
          drawerTab === "messages" ? (
            <MessageListPanel sessionId={drawerSessionId} />
          ) : (
            <TraceListPanel
              sessionId={drawerSessionId}
              focusLlmCallId={drawerSessionId === focusSessionId ? focusLlmCallId : null}
            />
          )
        ) : null}
      </AdminDrawer>
    </div>
  );
}

export default function AdminSessionsPage() {
  return (
    <Suspense fallback={<p className="p-4 text-sm text-ink-500">加载中…</p>}>
      <AdminSessionsInner />
    </Suspense>
  );
}
