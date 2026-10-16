"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconInbox, IconSpark } from "@/components/ui/Icon";
import {
  listApplications,
  patchApplication,
  type ApplicationRow,
  type ApplicationStatus,
} from "@/lib/api/jobs";
import { userFacingApiError } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";

/**
 * Column accent is a 2px top rule rather than a filled header: six filled
 * headers side by side turn the board into a colour chart and drown the cards.
 */
const COLUMNS: { id: ApplicationStatus; label: string; accent: string }[] = [
  { id: "evaluated", label: "已评估", accent: "bg-ink-300" },
  { id: "skipped", label: "不投", accent: "bg-ink-200" },
  { id: "applied", label: "已投", accent: "bg-brand-400" },
  { id: "interviewing", label: "面试中", accent: "bg-brand-600" },
  { id: "rejected", label: "未通过", accent: "bg-danger-200" },
  { id: "offer", label: "Offer", accent: "bg-success-600" },
];

const REC_LABEL: Record<string, string> = {
  go: "建议主攻",
  caution: "适合练手",
  no: "匹配偏低",
};

const REC_BADGE: Record<string, string> = {
  go: "badge badge-success",
  caution: "badge badge-warn",
  no: "badge badge-neutral",
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
      .catch((err) => setError(userFacingApiError(err, "加载失败")));
  }, [profileId, context?.actor]);

  async function onPatch(row: ApplicationRow, patch: Parameters<typeof patchApplication>[2]) {
    if (!profileId) return;
    setBusyId(row.id);
    setError(null);
    try {
      const next = await patchApplication(profileId, row.id, patch);
      setRows((prev) => prev.map((r) => (r.id === next.id ? next : r)));
    } catch (err) {
      setError(userFacingApiError(err, "更新失败"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-section">
      <PageHeader
        eyebrow="行动"
        title="投递看板"
        description="评估过的岗位都会落在这里。状态由你自己标记，系统不会代投，也不会替你外发任何材料。"
        actions={
          rows.length ? (
            <span className="badge badge-neutral tabular-nums">{rows.length} 个机会</span>
          ) : null
        }
      />

      {context?.actor !== "user" ? (
        <EmptyState
          icon={<IconSpark />}
          title="登录后查看你的漏斗"
          description="投递状态属于你的个人数据，需要登录才能读写。"
          action={
            <Link href="/auth/login" className="btn btn-md btn-primary">
              去登录
              <IconArrowRight className="h-4 w-4" />
            </Link>
          }
        />
      ) : !profileId ? (
        <EmptyState
          icon={<IconSpark />}
          title="先建好你的档案"
          action={
            <Link href="/resume-agent" className="btn btn-md btn-primary">
              去上传简历
            </Link>
          }
        />
      ) : (
        <>
          {error ? (
            <p className="notice notice-danger" role="alert">
              {error}
            </p>
          ) : null}

          {rows.length === 0 ? (
            <EmptyState
              icon={<IconInbox />}
              title="漏斗还是空的"
              description="去定向岗位页粘贴一份 JD 并计算匹配，它就会出现在「已评估」这一列。"
              action={
                <Link href="/jobs" className="btn btn-md btn-primary">
                  添加第一个岗位
                  <IconArrowRight className="h-4 w-4" />
                </Link>
              }
            />
          ) : (
            <div className="scroll-area -mx-1 flex gap-3 overflow-x-auto px-1 pb-3">
              {COLUMNS.map((col) => {
                const items = rows.filter((r) => (r.status ?? "evaluated") === col.id);
                return (
                  <section
                    key={col.id}
                    className="card flex w-[240px] shrink-0 flex-col overflow-hidden"
                  >
                    <span className={`h-0.5 w-full shrink-0 ${col.accent}`} aria-hidden />
                    <h2 className="flex shrink-0 items-center justify-between gap-2 px-3 py-2.5 text-sm font-semibold text-ink-800">
                      {col.label}
                      <span className="badge badge-neutral tabular-nums">{items.length}</span>
                    </h2>
                    <ul className="scroll-area max-h-[60vh] space-y-2 overflow-y-auto px-2 pb-2">
                      {items.map((r) => (
                        <ApplicationCard
                          key={r.id}
                          row={r}
                          busy={busyId === r.id}
                          onStatus={(status) => void onPatch(r, { status })}
                          onFollowUp={(value) => void onPatch(r, { follow_up_on: value })}
                        />
                      ))}
                      {items.length === 0 ? (
                        <li className="rounded-lg border border-dashed border-surface-border py-5 text-center text-micro text-ink-500">
                          空
                        </li>
                      ) : null}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
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
    <li
      className={`card-sunken p-2.5 transition ${busy ? "opacity-60" : "hover:bg-surface hover:shadow-xs"}`}
    >
      <p className="text-sm font-medium leading-snug text-ink-900">{row.company ?? "—"}</p>
      <p className="mt-0.5 truncate text-xs text-ink-600">{row.title ?? row.job_id}</p>

      <p className="mt-2 flex flex-wrap items-center gap-1.5">
        {row.fit_score != null ? (
          <span className="badge badge-neutral tabular-nums">{row.fit_score}</span>
        ) : (
          <span className="badge badge-neutral">未打分</span>
        )}
        {rec ? (
          <span className={REC_BADGE[rec] ?? "badge badge-neutral"}>{REC_LABEL[rec] ?? rec}</span>
        ) : null}
      </p>

      <div className="mt-2.5 space-y-1.5">
        <label className="block">
          <span className="label-meta">状态</span>
          <select
            className="field mt-1 px-2 py-1 text-xs"
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
        <label className="block">
          <span className="label-meta">跟进日</span>
          <input
            type="date"
            className="field mt-1 px-2 py-1 text-xs"
            disabled={busy}
            value={row.follow_up_on ?? ""}
            onChange={(e) => onFollowUp(e.target.value)}
          />
        </label>
      </div>

      <div className="mt-2.5 flex flex-col gap-1 border-t border-surface-border pt-2">
        <Link
          href={`/resume-agent?job_id=${encodeURIComponent(row.job_id)}`}
          className="text-xs font-medium text-brand-700 hover:text-brand-800"
        >
          按该岗位优化简历
        </Link>
        <Link
          href={`/coach-agent?job_id=${encodeURIComponent(row.job_id)}`}
          className="text-xs font-medium text-brand-700 hover:text-brand-800"
        >
          针对该岗模拟面
        </Link>
      </div>
    </li>
  );
}
