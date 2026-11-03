"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  deleteResumeVersion,
  listResumeVersions,
  resumeVersionViewUrl,
  type ResumeVersionExport,
  type ResumeVersionGroup,
  type ResumeVersionItem,
} from "@/lib/api/resume-versions";
import { useAuth } from "@/lib/auth/AuthProvider";
import { userFacingApiError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";

const FORMAT_LABEL: Record<ResumeVersionExport["format"], string> = {
  pdf: "PDF",
  docx: "Word",
  html: "网页版",
};

const LEVEL_LABEL: Record<ResumeVersionItem["elevation_level"], string> = {
  conservative: "保守",
  standard: "标准",
  elevated: "强化",
};

const REVIEW_LABEL: Record<ResumeVersionItem["reviewer_status"], { text: string; tone: string }> = {
  passed: { text: "质检通过", tone: "badge-success" },
  failed: { text: "质检未通过", tone: "badge-warn" },
  pending: { text: "未质检", tone: "badge-neutral" },
};

function ExportChip({ item }: { item: ResumeVersionExport }) {
  const name = FORMAT_LABEL[item.format];
  if (item.status === "done" && item.download_url) {
    return (
      <a href={item.download_url} className="btn btn-sm btn-secondary" download>
        下载 {name}
      </a>
    );
  }
  if (item.status === "processing" || item.status === "pending") {
    return <span className="badge badge-brand">{name} 生成中</span>;
  }
  return (
    <span className="badge badge-warn" title={item.error_message ?? undefined}>
      {name} 生成失败
    </span>
  );
}

function VersionRow({
  version,
  busy,
  onDelete,
}: {
  version: ResumeVersionItem;
  busy: boolean;
  onDelete: (version: ResumeVersionItem) => void;
}) {
  const review = REVIEW_LABEL[version.reviewer_status];
  return (
    <li className="flex flex-col gap-2 border-t border-surface-border py-3 first:border-t-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink-900">
          {version.job ? `${version.job.title} · ${version.job.company}` : "通用版本（未针对岗位）"}
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-500">
          <span>{formatDateTime(version.created_at)}</span>
          <span>{LEVEL_LABEL[version.elevation_level]}档</span>
          <span>{version.locale}</span>
          <span className={`badge ${review.tone}`}>{review.text}</span>
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {version.exports.length === 0 ? (
            <span className="text-xs text-ink-400">还没有导出过文件</span>
          ) : (
            version.exports.map((item) => <ExportChip key={item.id} item={item} />)
          )}
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <a href={resumeVersionViewUrl(version.id)} target="_blank" rel="noreferrer" className="btn btn-sm btn-ghost">
          查看
        </a>
        <button
          type="button"
          onClick={() => onDelete(version)}
          disabled={busy}
          className="btn btn-sm btn-ghost text-danger-700 hover:bg-danger-50 hover:text-danger-700"
        >
          删除
        </button>
      </div>
    </li>
  );
}

function ProfileGroup({
  group,
  busyId,
  onDelete,
}: {
  group: ResumeVersionGroup;
  busyId: string | null;
  onDelete: (version: ResumeVersionItem) => void;
}) {
  const name = group.contact_name?.trim() || "未命名档案";
  return (
    <section className="card card-pad">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-ink-900">{name}</h2>
        {group.is_active ? <span className="badge badge-brand">当前档案</span> : null}
        <span className="ml-auto text-xs text-ink-500">共 {group.versions.length} 个版本</span>
      </header>
      {group.versions.length === 0 ? (
        <p className="mt-3 text-sm text-ink-500">这份档案还没有优化过简历。</p>
      ) : (
        <ul className="mt-2">
          {group.versions.map((version) => (
            <VersionRow key={version.id} version={version} busy={busyId === version.id} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ResumeVersionsPage() {
  const { context, loading: authLoading } = useAuth();
  const signedIn = context?.actor === "user";
  const [groups, setGroups] = useState<ResumeVersionGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await listResumeVersions();
      setGroups(data.groups);
    } catch (err) {
      setError(userFacingApiError(err, "加载失败，请稍后重试。"));
    }
  }, []);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  async function remove(version: ResumeVersionItem) {
    const label = version.job ? `${version.job.title} · ${version.job.company}` : "这个通用版本";
    const exported = version.exports.length > 0;
    const message = exported
      ? `删除「${label}」？它导出过的文件也会一并删除，无法恢复。`
      : `删除「${label}」？删除后无法恢复。`;
    if (!window.confirm(message)) return;
    setBusyId(version.id);
    setError(null);
    setNotice(null);
    try {
      await deleteResumeVersion(version.id);
      setGroups((prev) =>
        prev?.map((g) => ({ ...g, versions: g.versions.filter((v) => v.id !== version.id) })) ?? prev,
      );
      setNotice("已删除。");
    } catch (err) {
      setError(userFacingApiError(err, "删除失败，请稍后重试。"));
    } finally {
      setBusyId(null);
    }
  }

  if (authLoading) return <p className="text-sm text-ink-500">正在加载…</p>;
  if (!signedIn) {
    return (
      <div className="card bg-sheen mx-auto max-w-md px-6 py-10 text-center">
        <p className="text-sm text-ink-600">
          请先{" "}
          <Link className="font-medium text-brand-700 hover:text-brand-800" href="/auth/login">
            登录
          </Link>{" "}
          再查看你的简历版本。
        </p>
      </div>
    );
  }

  const total = groups?.reduce((sum, g) => sum + g.versions.length, 0) ?? 0;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-ink-900">简历版本</h1>
          <p className="mt-1 text-xs text-ink-500">
            每次优化都会保存一个版本，可以按岗位回看、下载导出过的文件，或删除不再需要的版本。
          </p>
        </div>
        <Link href="/resume-agent" className="btn btn-sm btn-primary">
          去优化简历
        </Link>
      </div>

      {error ? (
        <p className="notice notice-danger text-sm" role="alert">{error}</p>
      ) : null}
      {notice ? (
        <p className="notice notice-success text-sm" role="status">{notice}</p>
      ) : null}

      {groups === null && !error ? <p className="text-sm text-ink-500">正在加载版本…</p> : null}

      {groups !== null && total === 0 ? (
        <div className="card card-pad text-center">
          <p className="text-sm text-ink-600">还没有简历版本。</p>
          <p className="mt-1 text-xs text-ink-500">在简历优化里完成一次优化，它就会出现在这里。</p>
        </div>
      ) : null}

      {total > 0
        ? groups?.map((group) => (
            <ProfileGroup key={group.profile_id} group={group} busyId={busyId} onDelete={remove} />
          ))
        : null}
    </div>
  );
}
