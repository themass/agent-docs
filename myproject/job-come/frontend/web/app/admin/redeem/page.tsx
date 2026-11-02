"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  createRedeemBatch,
  deleteRedeemCode,
  downloadRedeemCodesCsv,
  getPurchaseUrlSetting,
  listRedeemCodes,
  setPurchaseUrlSetting,
  updateRedeemNote,
  voidRedeemCode,
  type RedeemCodeBatch,
  type RedeemCodeFilters,
  type RedeemCodeItem,
  type RedeemCodeList,
  type RedeemCodeStatus,
} from "@/lib/api/admin-redeem";
import { userFacingApiError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";

const PAGE_SIZE = 50;

const STATUS_LABEL: Record<RedeemCodeStatus, string> = {
  unused: "未使用",
  redeemed: "已兑换",
  void: "已作废",
};

const STATUS_BADGE: Record<RedeemCodeStatus, string> = {
  unused: "badge-brand",
  redeemed: "badge-success",
  void: "badge-neutral",
};

function NoteCell({ item, onSaved, onError }: {
  item: RedeemCodeItem;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(item.note ?? "");

  async function save() {
    setEditing(false);
    if ((item.note ?? "") === value) return;
    try {
      await updateRedeemNote(item.id, value.trim() || null);
      onSaved();
    } catch (err) {
      onError(userFacingApiError(err, "备注保存失败。"));
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="max-w-[16rem] truncate text-left text-xs text-ink-600 hover:text-ink-900"
        title="点击修改备注"
      >
        {item.note || <span className="text-ink-400">添加备注</span>}
      </button>
    );
  }
  return (
    <input
      autoFocus
      value={value}
      maxLength={255}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => void save()}
      onKeyDown={(event) => {
        if (event.key === "Enter") void save();
        if (event.key === "Escape") {
          setValue(item.note ?? "");
          setEditing(false);
        }
      }}
      className="field h-7 w-56 py-0 text-xs"
    />
  );
}

export default function AdminRedeemPage() {
  const [stats, setStats] = useState<RedeemCodeList["stats"] | null>(null);
  const [filters, setFilters] = useState<RedeemCodeFilters>({ status: "", batchId: "", search: "" });
  const [applied, setApplied] = useState<RedeemCodeFilters>({});
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<RedeemCodeList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [count, setCount] = useState(20);
  const [batchNote, setBatchNote] = useState("");
  const [batchExpiry, setBatchExpiry] = useState("");
  const [generating, setGenerating] = useState(false);
  const [lastBatch, setLastBatch] = useState<RedeemCodeBatch | null>(null);

  const [purchaseUrl, setPurchaseUrl] = useState("");
  const [savingUrl, setSavingUrl] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listRedeemCodes(applied, { limit: PAGE_SIZE, offset });
      setData(next);
      setStats(next.stats);
    } catch (err) {
      setError(userFacingApiError(err, "加载失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  }, [applied, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    getPurchaseUrlSetting()
      .then((setting) => setPurchaseUrl(setting.url ?? ""))
      .catch(() => setPurchaseUrl(""));
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const batch = await createRedeemBatch({
        count,
        note: batchNote.trim() || undefined,
        expires_at: batchExpiry ? new Date(`${batchExpiry}T23:59:59+08:00`).toISOString() : undefined,
      });
      setLastBatch(batch);
      setBatchNote("");
      setNotice(`已生成 ${batch.count} 个兑换码，批次 ${batch.batch_id}。`);
      setApplied({ status: "", batchId: batch.batch_id, search: "" });
      setFilters({ status: "", batchId: batch.batch_id, search: "" });
      setOffset(0);
    } catch (err) {
      setError(userFacingApiError(err, "生成失败，请稍后重试。"));
    } finally {
      setGenerating(false);
    }
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setApplied({ ...filters });
    setOffset(0);
  }

  async function saveUrl(event: FormEvent) {
    event.preventDefault();
    setSavingUrl(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await setPurchaseUrlSetting(purchaseUrl.trim() || null);
      setPurchaseUrl(saved.url ?? "");
      setNotice(saved.url ? "购买入口已更新。" : "购买入口已清空，用户将看到“暂未开放”。");
    } catch (err) {
      setError(userFacingApiError(err, "保存失败，请检查链接格式。"));
    } finally {
      setSavingUrl(false);
    }
  }

  async function voidItem(item: RedeemCodeItem) {
    if (!window.confirm(`作废兑换码 ${item.code}？作废后无法恢复。`)) return;
    try {
      await voidRedeemCode(item.id);
      setNotice("已作废。");
      void load();
    } catch (err) {
      setError(userFacingApiError(err, "作废失败。"));
    }
  }

  async function removeItem(item: RedeemCodeItem) {
    if (!window.confirm(`删除兑换码 ${item.code}？仅用于生成错误的码，删除后无法恢复。`)) return;
    try {
      await deleteRedeemCode(item.id);
      setNotice("已删除。");
      void load();
    } catch (err) {
      setError(userFacingApiError(err, "删除失败。"));
    }
  }

  async function exportCsv() {
    setError(null);
    try {
      await downloadRedeemCodesCsv(applied);
    } catch (err) {
      setError(userFacingApiError(err, "导出失败，请稍后重试。"));
    }
  }

  async function copyLastBatch() {
    if (!lastBatch) return;
    try {
      await navigator.clipboard.writeText(lastBatch.codes.join("\n"));
      setNotice("已复制到剪贴板。");
    } catch {
      setError("复制失败，请手动选择文本复制。");
    }
  }

  const total = data?.total ?? 0;
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <div>
          <h1 className="text-sm font-semibold text-ink-900">兑换码</h1>
          <p className="text-xs text-ink-500">
            月会员 25 元 / 30 天。一码一次，咸鱼发货时从这里导出对照。
          </p>
        </div>
        {stats ? (
          <div className="ml-auto flex flex-wrap gap-1.5 text-xs">
            <span className="badge badge-neutral">共 {stats.total}</span>
            <span className="badge badge-brand">未使用 {stats.unused}</span>
            <span className="badge badge-success">已兑换 {stats.redeemed}</span>
            <span className="badge badge-neutral">已作废 {stats.void}</span>
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="notice notice-warn shrink-0 text-xs" role="alert">{error}</p>
      ) : null}
      {notice ? (
        <p className="notice shrink-0 text-xs" role="status">{notice}</p>
      ) : null}

      <div className="grid shrink-0 gap-3 lg:grid-cols-2">
        <section className="card card-pad">
          <h2 className="text-sm font-semibold text-ink-900">批量生成</h2>
          <form onSubmit={generate} className="mt-3 grid gap-2.5 sm:grid-cols-2">
            <label className="text-xs text-ink-600">
              数量（1–500）
              <input
                type="number"
                min={1}
                max={500}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                className="field mt-1 h-8 py-0 text-xs"
              />
            </label>
            <label className="text-xs text-ink-600">
              码的有效期（可不填）
              <input
                type="date"
                value={batchExpiry}
                onChange={(event) => setBatchExpiry(event.target.value)}
                className="field mt-1 h-8 py-0 text-xs"
              />
            </label>
            <label className="text-xs text-ink-600 sm:col-span-2">
              备注（如：咸鱼 第一批）
              <input
                value={batchNote}
                maxLength={255}
                onChange={(event) => setBatchNote(event.target.value)}
                className="field mt-1 h-8 py-0 text-xs"
              />
            </label>
            <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
              <button type="submit" className="btn btn-sm btn-primary" disabled={generating}>
                {generating ? "生成中…" : "生成兑换码"}
              </button>
              {lastBatch ? (
                <>
                  <button type="button" onClick={() => void copyLastBatch()} className="btn btn-sm btn-secondary">
                    复制本批次
                  </button>
                  <span className="text-xs text-ink-500">刚生成的码已在下方列表中，可直接导出。</span>
                </>
              ) : null}
            </div>
          </form>
        </section>

        <section className="card card-pad">
          <h2 className="text-sm font-semibold text-ink-900">购买入口</h2>
          <p className="mt-1 text-xs text-ink-500">
            会员页和下载弹窗中的“去咸鱼购买”按钮指向这个链接。留空则显示“暂未开放”。
          </p>
          <form onSubmit={saveUrl} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={purchaseUrl}
              onChange={(event) => setPurchaseUrl(event.target.value)}
              placeholder="https://m.tb.cn/…"
              className="field h-8 py-0 text-xs"
            />
            <button type="submit" className="btn btn-sm btn-secondary shrink-0" disabled={savingUrl}>
              {savingUrl ? "保存中…" : "保存"}
            </button>
          </form>
        </section>
      </div>

      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-surface-border bg-surface shadow-card">
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-surface-border p-3">
          <form onSubmit={applyFilters} className="flex flex-wrap items-center gap-2">
            <select
              value={filters.status ?? ""}
              onChange={(event) => setFilters({ ...filters, status: event.target.value as RedeemCodeStatus | "" })}
              className="field h-8 w-28 py-0 text-xs"
            >
              <option value="">全部状态</option>
              <option value="unused">未使用</option>
              <option value="redeemed">已兑换</option>
              <option value="void">已作废</option>
            </select>
            <input
              value={filters.batchId ?? ""}
              onChange={(event) => setFilters({ ...filters, batchId: event.target.value })}
              placeholder="批次 ID"
              className="field h-8 w-44 py-0 font-mono text-xs"
            />
            <input
              value={filters.search ?? ""}
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
              placeholder="兑换码或备注"
              className="field h-8 w-44 py-0 text-xs"
            />
            <button type="submit" className="btn btn-sm btn-secondary">筛选</button>
          </form>
          <button type="button" onClick={() => void exportCsv()} className="btn btn-sm btn-primary ml-auto">
            导出 CSV
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-surface-sunken text-xs text-ink-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">兑换码</th>
                <th className="px-3 py-2 text-left font-medium">状态</th>
                <th className="px-3 py-2 text-left font-medium">批次</th>
                <th className="px-3 py-2 text-left font-medium">备注</th>
                <th className="px-3 py-2 text-left font-medium">生成时间</th>
                <th className="px-3 py-2 text-left font-medium">兑换账号 / 时间</th>
                <th className="px-3 py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((item) => (
                <tr key={item.id} className="border-t border-surface-border align-middle">
                  <td className="px-3 py-2 font-mono text-xs tracking-wide text-ink-900">{item.code}</td>
                  <td className="px-3 py-2">
                    <span className={`badge ${STATUS_BADGE[item.status as RedeemCodeStatus] ?? "badge-neutral"}`}>
                      {STATUS_LABEL[item.status as RedeemCodeStatus] ?? item.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-ink-500">{item.batch_id}</td>
                  <td className="px-3 py-2">
                    <NoteCell
                      item={item}
                      onSaved={() => void load()}
                      onError={(message) => setError(message)}
                    />
                  </td>
                  <td className="px-3 py-2 text-xs text-ink-600">{formatDateTime(item.created_at)}</td>
                  <td className="px-3 py-2 text-xs text-ink-600">
                    {item.redeemed_by_email ? (
                      <>
                        <div>{item.redeemed_by_email}</div>
                        <div className="text-ink-400">{formatDateTime(item.redeemed_at)}</div>
                      </>
                    ) : (
                      <span className="text-ink-400">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {item.status === "unused" ? (
                      <div className="flex justify-end gap-1.5">
                        <button type="button" onClick={() => void voidItem(item)} className="btn btn-sm btn-ghost">
                          作废
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeItem(item)}
                          className="btn btn-sm btn-ghost text-danger-700 hover:bg-danger-50 hover:text-danger-700"
                        >
                          删除
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-ink-400">只读</span>
                    )}
                  </td>
                </tr>
              ))}
              {data && data.items.length === 0 && !loading ? (
                <tr>
                  <td colSpan={7} className="px-3 py-10 text-center text-sm text-ink-500">
                    没有符合条件的兑换码。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-surface-border px-3 py-2 text-xs text-ink-500">
          <span>{loading ? "加载中…" : `第 ${pageStart}–${pageEnd} 条，共 ${total} 条`}</span>
          <div className="flex gap-1.5">
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              disabled={offset === 0 || loading}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              上一页
            </button>
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              disabled={offset + PAGE_SIZE >= total || loading}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              下一页
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
