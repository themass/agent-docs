"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AdminDrawer } from "@/components/admin/AdminDrawer";
import { Select } from "@/components/ui/Select";
import { nextSortState, SortableTh, type SortState } from "@/components/ui/SortableTh";
import {
  getAdminLlmCall,
  getAdminLlmUsage,
  listAdminLlmCalls,
  type AdminLlmCallDetail,
  type AdminLlmCallItem,
  type AdminLlmUsageRow,
} from "@/lib/api/admin";
import { formatDateTime } from "@/lib/datetime";
import { userFacingApiError } from "@/lib/api/user-error";

const CHANNEL_LABEL: Record<string, string> = {
  router: "确定性路由",
  harness: "舟卡 Agent",
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "全部" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status === "success" ? "badge-success" : "badge-danger"}`}>
      {status === "success" ? "成功" : "失败"}
    </span>
  );
}

function ChannelBadge({ channel }: { channel: string }) {
  return (
    <span className={`badge ${channel === "harness" ? "badge-brand" : "badge-neutral"}`}>
      {CHANNEL_LABEL[channel] ?? channel}
    </span>
  );
}

function formatTokens(n: number | null): string {
  if (n == null) return "—";
  return n.toLocaleString("zh-CN");
}

function formatCost(microUsd: number | null): string {
  if (microUsd == null) return "—";
  return `$${(microUsd / 1_000_000).toFixed(4)}`;
}

function formatLatency(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Pretty-print one flattened payload block for display.
 *
 * `prompt_text`/`response_text` are stored as `jc.llm.call_log.prompt_text_from_messages`
 * writes them: plain text, one `[role]` header per message, with the message content
 * underneath exactly as it was sent to the model. For the writer/reviewer scenarios that
 * content is itself `json.dumps(...)` on one line (the whole resume payload), which is
 * why this view was unreadable — a raw `<pre>` just wrapped one gigantic line. This
 * re-parses each `[role]` section and, where its body is JSON, re-serializes it indented.
 * Anything that is not valid JSON (plain system prompts, free text) passes through
 * unchanged, so this never hides or corrupts content it cannot classify.
 */
function formatPayloadText(raw: string): string {
  const blocks = raw.split(/\n(?=\[[a-zA-Z_]+\]\n)/g);
  return blocks
    .map((block) => {
      const headerMatch = block.match(/^(\[[a-zA-Z_]+\]\n)([\s\S]*)$/);
      const header = headerMatch ? headerMatch[1] : "";
      const body = headerMatch ? headerMatch[2] : block;
      return header + prettyIfJson(body);
    })
    .join("\n\n");
}

function prettyIfJson(text: string): string {
  const trimmed = text.trim();
  if (!trimmed || (trimmed[0] !== "{" && trimmed[0] !== "[")) return text;
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return text;
  }
}

/** Top usage summary: how many calls, how much it cost, grouped by routing scenario. */
function UsageSummary({ rows, days }: { rows: AdminLlmUsageRow[]; days: number }) {
  const totalCalls = rows.reduce((s, r) => s + r.calls, 0);
  const totalCost = rows.reduce((s, r) => s + r.cost_micro_usd, 0);
  const totalFailed = rows.reduce((s, r) => s + r.failed, 0);
  return (
    <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4">
      <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
        <p className="text-micro text-ink-500">近 {days} 天调用</p>
        <p className="text-lg font-semibold text-ink-900">{totalCalls.toLocaleString("zh-CN")}</p>
      </div>
      <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
        <p className="text-micro text-ink-500">失败次数</p>
        <p className="text-lg font-semibold text-danger-600">{totalFailed.toLocaleString("zh-CN")}</p>
      </div>
      <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
        <p className="text-micro text-ink-500">累计花费</p>
        <p className="text-lg font-semibold text-ink-900">{formatCost(totalCost)}</p>
      </div>
      <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
        <p className="text-micro text-ink-500">分类数</p>
        <p className="text-lg font-semibold text-ink-900">{rows.length}</p>
      </div>
    </div>
  );
}

function AttemptRow({ attempt }: { attempt: AdminLlmCallDetail["attempts"][number] }) {
  return (
    <li className="rounded-xl border border-surface-border bg-surface px-3 py-2 text-xs shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-ink-800">
          #{attempt.attempt_index} <code className="text-ink-600">{attempt.model}</code>
        </span>
        <StatusBadge status={attempt.status} />
      </div>
      <div className="mt-1 grid gap-x-3 gap-y-0.5 text-ink-500 sm:grid-cols-2">
        <p>provider: {attempt.provider ?? "—"}</p>
        <p>耗时: {formatLatency(attempt.latency_ms)}</p>
        <p>tokens: {formatTokens(attempt.total_tokens)}</p>
        <p>花费: {formatCost(attempt.cost_micro_usd)}</p>
      </div>
      {attempt.validator_failed ? (
        <p className="mt-1 text-warn-600">HTTP 200 但响应未通过校验（上游"假成功"）</p>
      ) : null}
      {attempt.error_message ? (
        <p className="mt-1 text-danger-600">
          {attempt.error_code ? `[${attempt.error_code}] ` : ""}
          {attempt.error_message}
        </p>
      ) : null}
    </li>
  );
}

function CallDetailBody({ detail }: { detail: AdminLlmCallDetail }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-surface-border bg-surface-sunken px-3 py-2 shadow-card grid gap-x-4 gap-y-1 text-xs text-ink-600 sm:grid-cols-2">
        <p className="select-text">
          <span className="text-ink-500">scenario</span> {detail.scenario}
        </p>
        <p className="select-text">
          <span className="text-ink-500">caller</span> {detail.caller}
        </p>
        <p className="select-text">
          <span className="text-ink-500">channel</span> <ChannelBadge channel={detail.channel} />
        </p>
        <p className="select-text">
          <span className="text-ink-500">最终模型</span>{" "}
          <code className="text-ink-800">{detail.final_model ?? "—"}</code>
        </p>
        <p className="select-text">
          <span className="text-ink-500">user</span> {detail.user_id ?? "—"}
        </p>
        <p className="select-text">
          <span className="text-ink-500">session</span> <code className="text-ink-800">{detail.session_id ?? "—"}</code>
        </p>
        <p className="select-text">
          <span className="text-ink-500">trace</span> <code className="text-ink-800">{detail.trace_id ?? "—"}</code>
        </p>
        <p className="select-text">
          <span className="text-ink-500">耗时</span> {formatLatency(detail.latency_ms)}
        </p>
      </div>

      {detail.session_id ? (
        <Link
          href={`/admin/sessions?session_id=${detail.session_id}&llm_call_id=${detail.id}`}
          className="btn btn-sm btn-secondary inline-flex items-center gap-1.5"
        >
          查看调用链（跳转到该会话的事件账本，定位这一次调用）
        </Link>
      ) : (
        <p className="text-micro text-ink-400">这次调用没有关联到任何会话（确定性路由调用），没有事件账本可查看。</p>
      )}

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
          <p className="text-micro text-ink-500">Token 消耗</p>
          <p className="text-sm font-semibold text-ink-900">{formatTokens(detail.total_tokens)}</p>
          <p className="text-micro text-ink-400">
            prompt {formatTokens(detail.prompt_tokens)} · completion {formatTokens(detail.completion_tokens)}
            {detail.reasoning_tokens ? ` · reasoning ${formatTokens(detail.reasoning_tokens)}` : ""}
          </p>
        </div>
        <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
          <p className="text-micro text-ink-500">花费</p>
          <p className="text-sm font-semibold text-ink-900">{formatCost(detail.cost_micro_usd)}</p>
        </div>
        <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
          <p className="text-micro text-ink-500">尝试次数</p>
          <p className="text-sm font-semibold text-ink-900">{detail.attempt_count}</p>
        </div>
      </div>

      {detail.error_message ? (
        <p className="notice notice-danger text-xs" role="alert">
          {detail.error_code ? `[${detail.error_code}] ` : ""}
          {detail.error_message}
        </p>
      ) : null}

      <div>
        <p className="mb-1.5 text-xs font-medium text-ink-700">Endpoint 尝试记录（含失败）</p>
        {detail.attempts.length === 0 ? (
          <p className="text-xs text-ink-500">没有记录到具体尝试。</p>
        ) : (
          <ul className="space-y-1.5">
            {detail.attempts.map((a) => (
              <AttemptRow key={a.attempt_index} attempt={a} />
            ))}
          </ul>
        )}
      </div>

      {detail.payload_truncated ||
      detail.prompt_text != null ||
      detail.response_text != null ||
      detail.reasoning_text != null ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-ink-700">调用原文</p>
          {detail.prompt_text != null ? (
            <details className="rounded-xl border border-surface-border bg-surface px-3 py-2 text-xs shadow-card">
              <summary className="cursor-pointer select-none font-medium text-ink-700">Prompt</summary>
              <pre className="mt-1.5 max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-ink-600">
                {formatPayloadText(detail.prompt_text)}
              </pre>
            </details>
          ) : null}
          {detail.reasoning_text != null ? (
            <details className="rounded-xl border border-surface-border bg-surface px-3 py-2 text-xs shadow-card">
              <summary className="cursor-pointer select-none font-medium text-ink-700">思考过程</summary>
              <pre className="mt-1.5 max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-ink-600">
                {formatPayloadText(detail.reasoning_text)}
              </pre>
            </details>
          ) : null}
          {detail.response_text != null ? (
            <details className="rounded-xl border border-surface-border bg-surface px-3 py-2 text-xs shadow-card">
              <summary className="cursor-pointer select-none font-medium text-ink-700">响应</summary>
              <pre className="mt-1.5 max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-ink-600">
                {formatPayloadText(detail.response_text)}
              </pre>
            </details>
          ) : null}
        </div>
      ) : (
        <p className="text-micro text-ink-400">
          未开启 payload 记录（含简历个人信息），只展示结构化指标。
        </p>
      )}
    </div>
  );
}

export default function AdminLlmPage() {
  const [calls, setCalls] = useState<AdminLlmCallItem[]>([]);
  const [total, setTotal] = useState(0);
  const [usage, setUsage] = useState<AdminLlmUsageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [scenarioFilter, setScenarioFilter] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [traceIdFilter, setTraceIdFilter] = useState("");
  const [sort, setSort] = useState<SortState>({ sortBy: "created_at", sortDir: "desc" });

  const [drawerCallId, setDrawerCallId] = useState<string | null>(null);
  const [drawerDetail, setDrawerDetail] = useState<AdminLlmCallDetail | null>(null);
  const [drawerIncludePayload, setDrawerIncludePayload] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [callsRes, usageRes] = await Promise.all([
        listAdminLlmCalls({
          limit: 100,
          status: statusFilter || undefined,
          channel: channelFilter || undefined,
          scenario: scenarioFilter || undefined,
          user_id: userIdFilter.trim() || undefined,
          trace_id: traceIdFilter.trim() || undefined,
          sort_by: sort.sortBy,
          sort_dir: sort.sortDir,
        }),
        getAdminLlmUsage({ days: 7, group_by: "scenario" }),
      ]);
      setCalls(callsRes.calls);
      setTotal(callsRes.total);
      setSort({ sortBy: callsRes.sort_by, sortDir: callsRes.sort_dir });
      setUsage(usageRes.rows);
    } catch (e) {
      setError(userFacingApiError(e, "加载 LLM 调用记录失败"));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, channelFilter, scenarioFilter, userIdFilter, traceIdFilter, sort.sortBy, sort.sortDir]);

  function onSort(columnKey: string) {
    // Text columns read naturally A→Z first; times, durations and sizes are
    // asked about largest-first ("which call was slowest / burned the most").
    const textFirstAsc = ["scenario", "caller", "channel", "status", "final_model", "user_id", "session_id"].includes(
      columnKey,
    );
    setSort((cur) => nextSortState(cur, columnKey, textFirstAsc ? "asc" : "desc"));
  }

  useEffect(() => {
    void loadCalls();
  }, [loadCalls]);

  useEffect(() => {
    if (!drawerCallId) {
      setDrawerDetail(null);
      return;
    }
    setDrawerLoading(true);
    setDrawerError(null);
    void getAdminLlmCall(drawerCallId, drawerIncludePayload)
      .then(setDrawerDetail)
      .catch((e) => setDrawerError(userFacingApiError(e, "加载调用详情失败")))
      .finally(() => setDrawerLoading(false));
  }, [drawerCallId, drawerIncludePayload]);

  function onFilterSubmit(e: React.FormEvent) {
    e.preventDefault();
    void loadCalls();
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <div>
          <h1 className="text-sm font-semibold text-ink-900">LLM 调用审计</h1>
          <p className="text-xs text-ink-500">
            {loading ? "加载中…" : `共 ${total} 条调用`} · 每一行是一次逻辑调用（可能跨多个 endpoint failover）
          </p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              type="button"
              onClick={() => setStatusFilter(f.value)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === f.value
                  ? "bg-brand-50 text-brand-700"
                  : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <UsageSummary rows={usage} days={7} />

      <form
        onSubmit={onFilterSubmit}
        className="flex shrink-0 flex-wrap items-center gap-2"
      >
        <Select
          value={channelFilter}
          onChange={(e) => setChannelFilter(e.target.value)}
          selectClassName="h-8 py-0 text-xs"
        >
          <option value="">全部渠道</option>
          <option value="router">确定性路由</option>
          <option value="harness">舟卡 Agent</option>
        </Select>
        <input
          value={scenarioFilter}
          onChange={(e) => setScenarioFilter(e.target.value)}
          placeholder="分类 scenario"
          className="field h-8 w-32 py-0 text-xs"
        />
        <input
          value={userIdFilter}
          onChange={(e) => setUserIdFilter(e.target.value)}
          placeholder="user_id"
          className="field h-8 w-32 py-0 text-xs"
        />
        <input
          value={traceIdFilter}
          onChange={(e) => setTraceIdFilter(e.target.value)}
          placeholder="trace_id"
          className="field h-8 w-36 py-0 text-xs"
        />
        <button type="submit" className="btn btn-sm btn-secondary">
          筛选
        </button>
      </form>

      {error ? (
        <p className="notice notice-warn shrink-0 text-xs" role="alert">
          {error}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-surface-border bg-surface shadow-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-surface-sunken text-xs text-ink-500">
            <tr>
              <SortableTh columnKey="created_at" label="时间" sort={sort} onSort={onSort} />
              <SortableTh columnKey="user_id" label="用户" sort={sort} onSort={onSort} />
              <SortableTh columnKey="scenario" label="分类 / 调用方" sort={sort} onSort={onSort} />
              <SortableTh columnKey="session_id" label="session" sort={sort} onSort={onSort} />
              <SortableTh columnKey="channel" label="渠道" sort={sort} onSort={onSort} />
              <SortableTh columnKey="final_model" label="最终模型" sort={sort} onSort={onSort} />
              <SortableTh columnKey="status" label="状态" sort={sort} onSort={onSort} />
              <SortableTh columnKey="attempt_count" label="尝试" sort={sort} onSort={onSort} align="right" />
              <SortableTh columnKey="latency_ms" label="耗时" sort={sort} onSort={onSort} align="right" />
              <SortableTh columnKey="total_tokens" label="tokens" sort={sort} onSort={onSort} align="right" />
              <SortableTh columnKey="cost_micro_usd" label="花费" sort={sort} onSort={onSort} align="right" />
            </tr>
          </thead>
          <tbody>
            {calls.map((c) => (
              <tr
                key={c.id}
                onClick={() => {
                  setDrawerCallId(c.id);
                  setDrawerIncludePayload(false);
                }}
                className="cursor-pointer border-t border-surface-border transition hover:bg-ink-50"
              >
                <td className="whitespace-nowrap px-3 py-2 text-xs text-ink-500">{formatDateTime(c.created_at)}</td>
                <td className="max-w-[12rem] px-3 py-2">
                  {c.user_id ? (
                    <>
                      <p className="truncate text-ink-900">
                        {c.user_display_name ?? c.user_email ?? "—"}
                      </p>
                      <p className="select-text truncate font-mono text-xs text-ink-500">{c.user_id}</p>
                    </>
                  ) : (
                    // System-scenario calls carry no user. Said plainly so an empty cell
                    // does not read as missing data.
                    <p className="text-xs text-ink-400">系统调用</p>
                  )}
                </td>
                <td className="px-3 py-2">
                  <p className="text-ink-900">{c.scenario}</p>
                  <p className="text-xs text-ink-500">{c.caller}</p>
                </td>
                <td className="px-3 py-2">
                  {c.session_id ? (
                    // Stops the row click from also opening this call's drawer: the two
                    // targets are different, and the cell is the more specific intent.
                    <Link
                      href={`/admin/sessions?session_id=${c.session_id}&llm_call_id=${c.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="select-text font-mono text-xs text-brand-600 underline-offset-2 hover:underline"
                      title="跳转到该会话的事件账本"
                    >
                      {c.session_id}
                    </Link>
                  ) : (
                    <span className="text-xs text-ink-400">—</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <ChannelBadge channel={c.channel} />
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <code className="text-xs text-ink-700">{c.final_model ?? "—"}</code>
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={c.status} />
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-ink-700">{c.attempt_count}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {formatLatency(c.latency_ms)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {formatTokens(c.total_tokens)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {formatCost(c.cost_micro_usd)}
                </td>
              </tr>
            ))}
            {!loading && calls.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-3 py-8 text-center text-sm text-ink-500">
                  没有匹配的调用记录
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <AdminDrawer
        open={drawerCallId !== null}
        onClose={() => setDrawerCallId(null)}
        title={drawerCallId ?? ""}
        subtitle={drawerDetail ? `${drawerDetail.scenario} · ${drawerDetail.caller}` : undefined}
      >
        {drawerLoading ? <p className="text-sm text-ink-500">加载中…</p> : null}
        {drawerError ? (
          <p className="notice notice-warn text-xs" role="alert">
            {drawerError}
          </p>
        ) : null}
        {!drawerLoading && drawerDetail ? (
          <div className="space-y-3">
            <label className="flex items-center gap-1.5 text-xs text-ink-500">
              <input
                type="checkbox"
                checked={drawerIncludePayload}
                onChange={(e) => setDrawerIncludePayload(e.target.checked)}
              />
              显示 prompt / 响应 / 思考原文（含简历个人信息）
            </label>
            <CallDetailBody detail={drawerDetail} />
          </div>
        ) : null}
      </AdminDrawer>
    </div>
  );
}
