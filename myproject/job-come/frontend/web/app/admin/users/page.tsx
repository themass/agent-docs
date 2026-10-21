"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminDrawer } from "@/components/admin/AdminDrawer";
import { AdminProfileDetail } from "@/components/admin/AdminProfileDetail";
import { nextSortState, SortableTh, type SortState } from "@/components/ui/SortableTh";
import {
  getAdminUser,
  listAdminUsers,
  type AdminUserDetail,
  type AdminUserListItem,
} from "@/lib/api/admin";
import { formatDateTime } from "@/lib/datetime";
import { userFacingApiError } from "@/lib/api/user-error";

function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`badge ${role === "admin" ? "badge-brand" : "badge-neutral"}`}>
      {role === "admin" ? "管理员" : "用户"}
    </span>
  );
}

function VerifiedBadge({ verified }: { verified: boolean }) {
  return (
    <span className={`badge ${verified ? "badge-success" : "badge-warn"}`}>
      {verified ? "已验证" : "未验证"}
    </span>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  // Mirrors the server's echoed order, so a rejected sort cannot leave the
  // header arrow pointing at a column the rows are not ordered by.
  const [sort, setSort] = useState<SortState>({ sortBy: "created_at", sortDir: "desc" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [profileDrawerId, setProfileDrawerId] = useState<string | null>(null);

  const loadUsers = useCallback(async (searchTerm: string, order: SortState) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAdminUsers({
        limit: 100,
        search: searchTerm || undefined,
        sort_by: order.sortBy,
        sort_dir: order.sortDir,
      });
      setUsers(res.users);
      setTotal(res.total);
      setSort({ sortBy: res.sort_by, sortDir: res.sort_dir });
    } catch (e) {
      setError(userFacingApiError(e, "加载用户列表失败"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers(search.trim(), sort);
    // Re-fetch on sort change only; search is submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort.sortBy, sort.sortDir]);

  function onSort(columnKey: string) {
    const textFirstAsc = ["email", "display_name", "role"].includes(columnKey);
    setSort((cur) => nextSortState(cur, columnKey, textFirstAsc ? "asc" : "desc"));
  }

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    void getAdminUser(selectedId)
      .then(setDetail)
      .catch((e) => setDetailError(userFacingApiError(e, "加载用户详情失败")))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    void loadUsers(search.trim(), sort);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <div>
          <h1 className="text-sm font-semibold text-ink-900">用户目录</h1>
          <p className="text-xs text-ink-500">
            {loading ? "加载中…" : `共 ${total} 位用户`}
          </p>
        </div>
        <form onSubmit={onSearchSubmit} className="ml-auto flex items-center gap-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="按邮箱或显示名搜索"
            className="field h-8 w-56 py-0 text-xs"
          />
          <button type="submit" className="btn btn-sm btn-secondary">
            搜索
          </button>
        </form>
      </div>

      {error ? (
        <p className="notice notice-warn shrink-0 text-xs" role="alert">
          {error}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-surface-border bg-surface shadow-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-surface-sunken text-xs text-ink-500">
            <tr>
              <SortableTh columnKey="email" label="邮箱" sort={sort} onSort={onSort} />
              <SortableTh columnKey="display_name" label="显示名" sort={sort} onSort={onSort} />
              <SortableTh columnKey="role" label="角色" sort={sort} onSort={onSort} />
              <SortableTh columnKey="email_verified_at" label="邮箱验证" sort={sort} onSort={onSort} />
              {/* Counts are aggregated per page, not a column SQL can order by. */}
              <SortableTh columnKey="profile_count" label="档案数" sort={sort} onSort={onSort} align="right" sortable={false} />
              <SortableTh columnKey="session_count" label="会话数" sort={sort} onSort={onSort} align="right" sortable={false} />
              <SortableTh columnKey="created_at" label="注册时间" sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr
                key={u.id}
                onClick={() => setSelectedId(u.id)}
                className="cursor-pointer border-t border-surface-border transition hover:bg-ink-50"
              >
                <td className="px-3 py-2 text-ink-900">{u.email}</td>
                <td className="px-3 py-2 text-ink-700">{u.display_name ?? "—"}</td>
                <td className="px-3 py-2">
                  <RoleBadge role={u.role} />
                </td>
                <td className="px-3 py-2">
                  <VerifiedBadge verified={u.email_verified} />
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {u.profile_count}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {u.session_count}
                </td>
                <td className="px-3 py-2 text-xs text-ink-500">{formatDateTime(u.created_at)}</td>
              </tr>
            ))}
            {!loading && users.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-ink-500">
                  没有匹配的用户
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <AdminDrawer
        open={selectedId !== null}
        onClose={() => setSelectedId(null)}
        title={detail?.email ?? selectedId ?? ""}
        subtitle={detail ? `${detail.id} · ${detail.role === "admin" ? "管理员" : "用户"}` : undefined}
      >
        {detailLoading ? <p className="text-sm text-ink-500">加载中…</p> : null}
        {detailError ? (
          <p className="notice notice-warn text-xs" role="alert">
            {detailError}
          </p>
        ) : null}
        {detail && !detailLoading ? (
          <div className="space-y-4">
            <section className="card grid gap-x-4 gap-y-1.5 px-3 py-2.5 text-xs text-ink-600 sm:grid-cols-2">
              <p>
                <span className="text-ink-500">状态</span> {detail.status}
              </p>
              <p>
                <span className="text-ink-500">语言</span> {detail.locale ?? "—"}
              </p>
              <p>
                <span className="text-ink-500">表达力度</span> {detail.default_elevation_level ?? "—"}
              </p>
              <p>
                <span className="text-ink-500">最近更新</span> {formatDateTime(detail.updated_at)}
              </p>
            </section>

            <section>
              <p className="label-meta mb-2">简历档案（{detail.profiles.length}）</p>
              {detail.profiles.length === 0 ? (
                <p className="text-sm text-ink-500">该用户还没有简历档案。</p>
              ) : (
                <ul className="space-y-2">
                  {detail.profiles.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => setProfileDrawerId(p.id)}
                        className="card block w-full px-3 py-2.5 text-left transition hover:bg-ink-50"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium text-ink-800">
                            {p.contact_name || p.summary_text || p.id}
                          </p>
                          <span
                            className={`badge ${p.status === "confirmed" ? "badge-success" : "badge-neutral"}`}
                          >
                            {p.status === "confirmed" ? "已确认" : "草稿"}
                          </span>
                        </div>
                        <p className="mt-1 text-micro text-ink-500">
                          v{p.version} · {p.locale} · 更新于 {formatDateTime(p.updated_at)}
                        </p>
                        <p className="mt-0.5 select-text font-mono text-micro text-ink-400">{p.id}</p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}
      </AdminDrawer>

      {/* Opened from inside the user-detail drawer, so it has to stack above it
          explicitly rather than relying on JSX order. */}
      <AdminDrawer
        open={profileDrawerId !== null}
        onClose={() => setProfileDrawerId(null)}
        title="简历档案详情"
        subtitle={profileDrawerId ?? undefined}
        layer={1}
      >
        {profileDrawerId ? <AdminProfileDetail profileId={profileDrawerId} /> : null}
      </AdminDrawer>
    </div>
  );
}
