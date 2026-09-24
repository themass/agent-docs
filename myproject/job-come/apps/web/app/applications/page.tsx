"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listApplications, type ApplicationRow } from "@/lib/api/jobs";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function ApplicationsPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id;
  const [rows, setRows] = useState<ApplicationRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId || context?.actor !== "user") return;
    void listApplications(profileId)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [profileId, context?.actor]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">投递记录</h1>
      {context?.actor !== "user" ? (
        <p className="text-sm text-amber-700">
          请 <Link href="/auth/login" className="underline">登录</Link> 后查看归档。
        </p>
      ) : !profileId ? (
        <p className="text-sm text-neutral-600">请先创建档案。</p>
      ) : (
        <>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.id} className="rounded border p-3 text-sm">
                <p className="font-medium">
                  {r.company ?? "—"} · {r.title ?? r.job_id}
                </p>
                <p className="text-neutral-500">
                  投递日 {r.applied_at ?? "—"} · 简历稿 {r.resume_variant_id ?? "—"}
                </p>
                <Link
                  href={`/coach-agent?job_id=${encodeURIComponent(r.job_id)}`}
                  className="mt-1 inline-block text-sky-700 underline"
                >
                  针对该岗模拟面
                </Link>
              </li>
            ))}
            {rows.length === 0 ? (
              <li className="text-neutral-500">
                暂无记录。在{" "}
                <Link href="/jobs" className="underline">
                  定向岗位
                </Link>{" "}
                完成「定向申请」后会自动归档。
              </li>
            ) : null}
          </ul>
        </>
      )}
    </div>
  );
}
