"use client";

import { useState } from "react";

import { reopenProfile, type Profile } from "@/lib/api/profile";

type Props = {
  profile: Profile;
  onReopened: (profile: Profile) => void;
};

export function ReopenProfileButton({ profile, onReopened }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (profile.status !== "confirmed") return null;

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const next = await reopenProfile(profile.id);
            onReopened(next);
          } catch (err) {
            setError(err instanceof Error ? err.message : "退回失败");
          } finally {
            setBusy(false);
          }
        }}
        className="rounded-full border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        title="退回后可继续编辑档案"
      >
        {busy ? "处理中…" : "退回修改"}
      </button>
      {error ? <span className="text-xs text-red-600">{error}</span> : null}
    </div>
  );
}
