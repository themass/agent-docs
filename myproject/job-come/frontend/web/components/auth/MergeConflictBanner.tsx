"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useState } from "react";

import { resolveMerge } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

type MergeConflict = {
  guest_profile: { id: string; contact_name: string | null; updated_at: string };
  account_profile: { id: string; contact_name: string | null; updated_at: string };
};

export function MergeConflictBanner() {
  const { context, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const conflict = context?.merge_conflict as MergeConflict | null | undefined;
  if (!conflict) return null;

  async function choose(choice: "keep_guest" | "keep_account") {
    setBusy(true);
    setError(null);
    try {
      await resolveMerge(choice);
      await refresh();
    } catch (err) {
      setError(userFacingApiError(err, "合并失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl bg-warn-50 p-4 text-sm ring-1 ring-inset ring-warn-200">
      <p className="font-medium text-warn-900">检测到两份档案，请选择保留哪一份：</p>
      <ul className="mt-2 space-y-1 text-warn-900">
        <li>访客：{conflict.guest_profile.contact_name ?? conflict.guest_profile.id}</li>
        <li>账号：{conflict.account_profile.contact_name ?? conflict.account_profile.id}</li>
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void choose("keep_guest")}
          className="btn btn-md bg-warn-700 text-white shadow-xs hover:bg-warn-900"
        >
          保留访客档案
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void choose("keep_account")}
          className="btn btn-md bg-surface text-warn-900 shadow-xs ring-1 ring-inset ring-warn-200 hover:bg-warn-100"
        >
          保留账号档案
        </button>
      </div>
      {error ? <p className="mt-2 text-danger-700" role="alert">
          {error}
        </p> : null}
    </div>
  );
}
