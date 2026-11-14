"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { BarList, HistogramBars, StatTile, formatCompact } from "@/components/admin/metrics/MetricsCharts";
import {
  getAdminMetrics,
  type AdminMetricsFamily,
  type AdminMetricsPeer,
  type AdminMetricsSnapshot,
} from "@/lib/api/admin";
import { userFacingApiError } from "@/lib/api/user-error";

/** Auto-refresh interval. Metrics are in-process counters, so they only move when polled. */
const REFRESH_MS = 15_000;

const PHASE_LABEL: Record<string, string> = {
  ttft: "首字（发送→第一个 token）",
  generate: "生成（首字→结束）",
  turn: "整回合",
  build: "建图",
  tool: "工具调用",
};

function familyOf(peer: AdminMetricsPeer | undefined, name: string): AdminMetricsFamily | undefined {
  return peer?.families?.[name];
}

/** Sum of a counter across all series, or null when the metric does not exist yet. */
function counterTotal(family: AdminMetricsFamily | undefined): number | null {
  if (!family) return null;
  return family.series
    .filter((s) => s.suffix === "total" || s.suffix === "value")
    .reduce((sum, s) => sum + (s.value ?? 0), 0);
}

/**
 * Cumulative histogram buckets, aggregated across every label combination.
 *
 * A histogram here is per-scenario and per-model; the panel's first question is
 * "how slow is this service", which is the sum. The per-label breakdown sits in
 * the bar list beneath.
 */
function histogramBuckets(family: AdminMetricsFamily | undefined): Array<{ upper: number; count: number }> {
  if (!family) return [];
  const byLe = new Map<string, number>();
  for (const series of family.series) {
    if (series.suffix !== "bucket") continue;
    const le = series.labels.le ?? "+Inf";
    byLe.set(le, (byLe.get(le) ?? 0) + (series.value ?? 0));
  }
  return [...byLe.entries()]
    .map(([le, count]) => ({ upper: le === "+Inf" ? Infinity : Number(le), count }))
    .sort((a, b) => a.upper - b.upper);
}

/** Mean latency from a histogram's sum and count — the number a person quotes. */
function histogramMean(family: AdminMetricsFamily | undefined): number | null {
  if (!family) return null;
  let sum = 0;
  let count = 0;
  for (const series of family.series) {
    if (series.suffix === "sum") sum += series.value ?? 0;
    if (series.suffix === "count") count += series.value ?? 0;
  }
  return count > 0 ? sum / count : null;
}

/** Per-label mean for one histogram family, ranked slowest first. */
function histogramByLabel(
  family: AdminMetricsFamily | undefined,
  labelKey: string,
): Array<{ label: string; value: number; display: string }> {
  if (!family) return [];
  const acc = new Map<string, { sum: number; count: number }>();
  for (const series of family.series) {
    if (series.suffix !== "sum" && series.suffix !== "count") continue;
    const key = series.labels[labelKey];
    if (!key) continue;
    const row = acc.get(key) ?? { sum: 0, count: 0 };
    if (series.suffix === "sum") row.sum += series.value ?? 0;
    else row.count += series.value ?? 0;
    acc.set(key, row);
  }
  return [...acc.entries()]
    .filter(([, v]) => v.count > 0)
    .map(([label, v]) => ({
      label,
      value: v.sum / v.count,
      display: formatCompact(v.sum / v.count),
    }))
    .sort((a, b) => b.value - a.value);
}

/** Counter totals split by one label — "which scenario is failing most". */
function counterByLabel(
  family: AdminMetricsFamily | undefined,
  labelKey: string,
): Array<{ label: string; value: number }> {
  if (!family) return [];
  const acc = new Map<string, number>();
  for (const series of family.series) {
    if (series.suffix !== "total" && series.suffix !== "value") continue;
    const key = series.labels[labelKey];
    if (!key) continue;
    acc.set(key, (acc.get(key) ?? 0) + (series.value ?? 0));
  }
  return [...acc.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

export default function AdminMetricsPage() {
  const [snapshot, setSnapshot] = useState<AdminMetricsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [includePeers, setIncludePeers] = useState(true);
  const [activePeer, setActivePeer] = useState<string | null>(null);

  const load = useCallback(async (withPeers: boolean) => {
    try {
      const data = await getAdminMetrics({ include_peers: withPeers });
      setSnapshot(data);
      setError(null);
      // Keep the selection only while that peer still exists; otherwise fall back
      // to the first answering one, so a removed peer cannot leave a blank panel.
      setActivePeer((current) => {
        if (current && data.peers.some((p) => p.name === current)) return current;
        return data.peers.find((p) => p.ok)?.name ?? data.peers[0]?.name ?? null;
      });
    } catch (err) {
      setError(userFacingApiError(err, "读取监控指标失败"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(includePeers);
  }, [load, includePeers]);

  useEffect(() => {
    const timer = window.setInterval(() => void load(includePeers), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load, includePeers]);

  const peer = useMemo(
    () => snapshot?.peers.find((p) => p.name === activePeer),
    [snapshot, activePeer],
  );

  const llmCalls = counterTotal(familyOf(peer, "llm_calls"));
  const llmFailures = counterByLabel(familyOf(peer, "llm_calls"), "status").find(
    (r) => r.label === "error",
  );
  const agentTurns = counterTotal(familyOf(peer, "agent_turns"));
  const inflight = counterTotal(familyOf(peer, "agent_turns_in_flight"));
  const ttft = histogramMean(familyOf(peer, "agent_phase_duration_seconds"));

  const phaseFamily = familyOf(peer, "agent_phase_duration_seconds");
  const phaseRows = useMemo(() => histogramByLabel(phaseFamily, "phase"), [phaseFamily]);

  return (
    <div className="mx-auto w-full max-w-6xl px-3 py-4 sm:px-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-base font-semibold text-ink-900">监控面板</h1>
          <p className="text-micro text-ink-500">
            每 {REFRESH_MS / 1000} 秒刷新 · 数据来自各服务的进程内计数器，重启后归零
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-ink-600">
            <input
              type="checkbox"
              checked={includePeers}
              onChange={(e) => setIncludePeers(e.target.checked)}
              className="size-3.5 accent-brand-600"
            />
            包含其它服务
          </label>
          <button type="button" className="btn btn-sm" onClick={() => void load(includePeers)}>
            刷新
          </button>
        </div>
      </div>

      {error ? <p className="notice notice-danger mb-3 text-xs">{error}</p> : null}

      {loading && !snapshot ? <p className="py-16 text-center text-sm text-ink-500">加载中…</p> : null}

      {snapshot ? (
        <>
          <ServiceTabs
            peers={snapshot.peers}
            active={activePeer}
            onSelect={setActivePeer}
            sharing={snapshot.sharing_across_processes}
            unavailable={snapshot.unavailable}
          />

          {peer && !peer.ok ? (
            <div className="notice notice-danger mb-3 text-xs">
              {peer.name} 无法访问（{peer.error ?? "未知错误"}，{peer.latency_ms}ms）。这一行保留在这里而不是消失，
              因为「没有数据」和「服务挂了」是两件事。
            </div>
          ) : null}

          {peer?.ok ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <StatTile
                  label="模型调用"
                  value={llmCalls == null ? "—" : llmCalls.toLocaleString("zh-CN")}
                  hint="进程启动至今"
                />
                <StatTile
                  label="模型失败"
                  value={llmFailures ? llmFailures.value.toLocaleString("zh-CN") : "0"}
                  tone={llmFailures && llmFailures.value > 0 ? "danger" : "default"}
                  hint="含重试后仍失败"
                />
                <StatTile
                  label="回合数"
                  value={agentTurns == null ? "—" : agentTurns.toLocaleString("zh-CN")}
                />
                <StatTile
                  label="在途回合"
                  value={inflight == null ? "—" : inflight.toLocaleString("zh-CN")}
                  hint="长期不降 = 有回合卡住"
                  tone={inflight != null && inflight > 0 ? "warn" : "default"}
                />
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <Panel title="模型调用耗时分布" hint="一次逻辑调用，含网关排队">
                  <HistogramBars buckets={histogramBuckets(familyOf(peer, "llm_call_duration_seconds"))} />
                </Panel>

                <Panel
                  title="回合分段耗时"
                  hint={
                    ttft == null
                      ? "暂无回合数据"
                      : `平均首字 ${formatCompact(ttft)} · 这一段最该盯`
                  }
                >
                  <BarList
                    data={phaseRows.map((r) => ({
                      label: PHASE_LABEL[r.label] ?? r.label,
                      value: r.value,
                      display: r.display,
                    }))}
                  />
                </Panel>

                <Panel title="按场景的模型耗时" hint="哪个场景在拖慢">
                  <BarList
                    data={histogramByLabel(familyOf(peer, "llm_call_duration_seconds"), "scenario").map(
                      (r) => ({ label: r.label, value: r.value, display: r.display }),
                    )}
                  />
                </Panel>

                <Panel title="按模型的调用次数" hint="谁在实际提供服务">
                  <BarList
                    data={counterByLabel(familyOf(peer, "llm_calls"), "model").map((r) => ({
                      label: r.label,
                      value: r.value,
                    }))}
                  />
                </Panel>

                <Panel title="故障转移次数" hint="一次调用跨了几个端点；>1 说明主链路不稳">
                  <HistogramBars buckets={histogramBuckets(familyOf(peer, "llm_attempts_per_call"))} />
                </Panel>

                <Panel title="失败原因" hint="按错误类型">
                  <BarList
                    data={counterByLabel(familyOf(peer, "llm_calls"), "error_type")
                      .filter((r) => r.label)
                      .map((r) => ({ label: r.label, value: r.value, tone: "danger" as const }))}
                    emptyLabel="没有失败记录"
                  />
                </Panel>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

/**
 * One tab per service.
 *
 * A tab rather than a merged view on purpose: counters from two processes cannot
 * be summed into a meaningful total (they started at different times), and a
 * merged chart would show a number no service ever produced. Switching keeps
 * every figure attributable to exactly one process group.
 */
function ServiceTabs({
  peers,
  active,
  onSelect,
  sharing,
  unavailable,
}: {
  peers: AdminMetricsPeer[];
  active: string | null;
  onSelect: (name: string) => void;
  sharing: boolean;
  unavailable: number;
}) {
  if (peers.length === 0) {
    return <p className="notice notice-info mb-3 text-xs">还没有任何服务的指标数据。</p>;
  }
  return (
    <div className="mb-3 space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {peers.map((p) => (
          <button
            key={p.name}
            type="button"
            onClick={() => onSelect(p.name)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
              p.name === active
                ? "border-brand-300 bg-brand-50 text-brand-700"
                : "border-surface-border bg-surface text-ink-700 hover:bg-ink-50"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${p.ok ? "bg-success-500" : "bg-danger-500"}`}
              aria-hidden
            />
            {p.name}
            {!p.ok ? <span className="text-danger-600">不可达</span> : null}
          </button>
        ))}
      </div>
      {unavailable > 0 ? (
        <p className="text-micro text-danger-600">
          {unavailable} 个服务不可达。它们仍留在列表里，避免「没有数据」被当成「运行正常」。
        </p>
      ) : null}
      {!sharing ? (
        <p className="text-micro text-warn-600">
          本服务的计数器按进程独立统计。后端以多 worker 运行时，这里只反映其中一个 worker
          （配置 JC_METRICS_MULTIPROCESS_DIR 可合并）。
        </p>
      ) : null}
    </div>
  );
}

function Panel({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-surface-border bg-surface p-3 shadow-card">
      <header className="mb-2">
        <h2 className="text-xs font-semibold text-ink-800">{title}</h2>
        {hint ? <p className="text-micro text-ink-500">{hint}</p> : null}
      </header>
      {children}
    </section>
  );
}
