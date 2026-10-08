"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  listApplications,
  patchApplication,
  type ApplicationRow,
  type ApplicationStatus,
} from "@/lib/api/jobs";
import { useAuth } from "@/lib/auth/AuthProvider";

const COLUMNS: { id: ApplicationStatus; label: string }[] = [
  { id: "evaluated", label: "已评估" },
  { id: "skipped", label: "不投" },
  { id: "applied", label: "已投" },
  { id: "interviewing", label: "面试中" },
  { id: "rejected", label: "未通过" },
  { id: "offer", label: "Offer" },
];

const REC_LABEL: Record<string, string> = {
  go: "建议主攻",
  caution: "适合练手",
  no: "匹配偏低",
};

export default function ApplicationsPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id;
  const [rows, setRows] = useState<ApplicationRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId || context?.actor !== "user") return;
    void listApplications(profileId)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [profileId, context?.actor]);

  async function onStatus(row: ApplicationRow, status: ApplicationStatus) {
    if (!profileId) return;
    setBusyId(row.id);
    setError(null);
    try {
      const next = await patchApplication(profileId, row.id, { status });
      setRows((prev) => prev.map((r) => (r.id === next.id ? next : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新失败");
    } finally {
      setBusyId(null);
    }
  }

  async function onFollowUp(row: ApplicationRow, value: string) {
    if (!profileId) return;
    setBusyId(row.id);
    setError(null);
    try {
      const next = await patchApplication(profileId, row.id, { follow_up_on: value });
      setRows((prev) => prev.map((r) => (r.id === next.id ? next : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新日期失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">投递看板</h1>
        <p className="mt-1 text-sm text-slate-600">
          匹配过的岗位会出现在这里。状态由你标记，系统不会代投或外发。
        </p>
      </div>
      {context?.actor !== "user" ? (
        <p className="text-sm text-amber-700">
          请{" "}
          <Link href="/auth/login" className="underline">
            登录
          </Link>{" "}
          后查看漏斗。
        </p>
      ) : !profileId ? (
        <p className="text-sm text-slate-600">请先创建档案。</p>
      ) : (
        <>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <div className="grid gap-3 overflow-x-auto pb-2 lg:grid-cols-6">
            {COLUMNS.map((col) => {
              const items = rows.filter((r) => (r.status ?? "evaluated") === col.id);
              return (
                <section
                  key={col.id}
                  className="min-w-[220px] rounded-2xl border border-surface-border bg-white p-3 shadow-card"
                >
                  <h2 className="flex items-center justify-between text-sm font-semibold text-slate-800">
                    {col.label}
                    <span className="text-xs font-normal text-slate-400">{items.length}</span>
                  </h2>
                  <ul className="mt-3 space-y-2">
                    {items.map((r) => (
                      <ApplicationCard
                        key={r.id}
                        row={r}
                        busy={busyId === r.id}
                        onStatus={(status) => void onStatus(r, status)}
                        onFollowUp={(value) => void onFollowUp(r, value)}
                      />
                    ))}
                    {items.length === 0 ? (
                      <li className="text-xs text-slate-400">空</li>
                    ) : null}
                  </ul>
                </section>
              );
            })}
          </div>
          {rows.length === 0 ? (
            <p className="text-sm text-slate-500">
              还没有记录。去{" "}
              <Link href="/jobs" className="text-brand-700 underline">
                定向岗位
              </Link>{" "}
              粘贴 JD 并计算匹配后会出现在「已评估」。
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function ApplicationCard({
  row,
  busy,
  onStatus,
  onFollowUp,
}: {
  row: ApplicationRow;
  busy: boolean;
  onStatus: (status: ApplicationStatus) => void;
  onFollowUp: (value: string) => void;
}) {
  const rec = row.fit_recommendation;
  return (
    <li className="rounded-xl border border-slate-200 p-3 text-sm">
      <p className="font-medium text-slate-900">
        {row.company ?? "—"} · {row.title ?? row.job_id}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {row.fit_score != null ? `匹配 ${row.fit_score}` : "未打分"}
        {rec ? ` · ${REC_LABEL[rec] ?? rec}` : ""}
      </p>
      <label className="mt-2 block text-[11px] text-slate-500">
        状态
        <select
          className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-xs"
          disabled={busy}
          value={row.status ?? "evaluated"}
          onChange={(e) => onStatus(e.target.value as ApplicationStatus)}
        >
          {COLUMNS.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label className="mt-2 block text-[11px] text-slate-500">
        跟进日
        <input
          type="date"
          className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-xs"
          disabled={busy}
          value={row.follow_up_on ?? ""}
          onChange={(e) => onFollowUp(e.target.value)}
        />
      </label>
      <div className="mt-2 flex flex-col gap-1 text-xs">
        <Link
          href={`/resume-agent?job_id=${encodeURIComponent(row.job_id)}`}
          className="text-brand-700 underline"
        >
          按该岗位优化简历
        </Link>
        <Link
          href={`/coach-agent?job_id=${encodeURIComponent(row.job_id)}`}
          className="text-brand-700 underline"
        >
          针对该岗模拟面
        </Link>
      </div>
    </li>
  );
}
