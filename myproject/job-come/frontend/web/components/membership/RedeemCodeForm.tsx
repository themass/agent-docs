"use client";

import { useState, type FormEvent } from "react";

import { redeemMembershipCode, type Membership } from "@/lib/api/membership";
import { userFacingApiError } from "@/lib/api/user-error";

export function RedeemCodeForm({
  onRedeemed,
  compact = false,
}: {
  onRedeemed: (membership: Membership) => void;
  compact?: boolean;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!code.trim() || busy) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const membership = await redeemMembershipCode(code);
      setCode("");
      setSuccess("兑换成功，会员已开通。");
      onRedeemed(membership);
    } catch (err) {
      setError(userFacingApiError(err, "兑换失败，请稍后再试。"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className={compact ? "space-y-2" : "space-y-2.5"}>
      <label className="block">
        <span className="label-meta mb-1.5 block">兑换码</span>
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="例如 ABCD-EFGH-JKLM-NPQR"
            autoComplete="off"
            spellCheck={false}
            className="field font-mono tracking-wider"
            disabled={busy}
          />
          <button type="submit" className="btn btn-sm btn-primary shrink-0" disabled={busy || !code.trim()}>
            {busy ? "兑换中…" : "兑换"}
          </button>
        </div>
      </label>
      <p className="text-xs leading-relaxed text-ink-500">
        兑换码每个只能使用一次，大小写和横线都可以不填。
      </p>
      {error ? (
        <p className="notice notice-warn text-xs" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="notice text-xs" role="status">
          {success}
        </p>
      ) : null}
    </form>
  );
}
