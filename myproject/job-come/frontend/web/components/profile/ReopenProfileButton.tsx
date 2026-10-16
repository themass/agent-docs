"use client";

import { userFacingApiError } from "@/lib/api/user-error";

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
            setError(userFacingApiError(err, "退回失败"));
          } finally {
            setBusy(false);
          }
        }}
        className="btn btn-sm btn-secondary"
        title="退回后可继续编辑档案"
      >
        {busy ? "处理中…" : "退回修改"}
      </button>
      {error ? <span className="text-xs text-danger-600">{error}</span> : null}
    </div>
  );
}
