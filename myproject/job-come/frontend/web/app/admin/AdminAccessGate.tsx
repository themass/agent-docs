"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AdminSubNav } from "@/components/admin/AdminSubNav";
import { useAuth } from "@/lib/auth/AuthProvider";

/**
 * Admin routes are only reachable with the `admin` capability (see
 * `AuthService.build_context` — granted when `User.role == "admin"`).
 * This is a client-side convenience redirect, not the security boundary:
 * every `/admin/*` API call is independently re-checked by `require_admin`
 * against the DB role, so a stale or forged client state cannot read data,
 * it can only momentarily render this shell before the API calls 403.
 */
export function AdminAccessGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { context, loading } = useAuth();
  const isAdmin = context?.capabilities.includes("admin") ?? false;

  useEffect(() => {
    if (!loading && !isAdmin) {
      router.replace("/resume-agent");
    }
  }, [loading, isAdmin, router]);

  if (loading) {
    return <p className="p-6 text-sm text-ink-500">加载中…</p>;
  }
  if (!isAdmin) {
    return null;
  }
  return (
    <div className="-mx-4 -my-4 flex min-h-0 flex-1 flex-col sm:-my-5">
      <AdminSubNav />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-4">{children}</div>
    </div>
  );
}
