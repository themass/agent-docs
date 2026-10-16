"use client";

import { useState } from "react";

import { resendVerification } from "@/lib/api/auth";
import { userFacingApiError } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";
import { IconInfo } from "@/components/ui/Icon";

export function EmailVerificationBanner() {
  const { context } = useAuth();
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (context?.actor !== "user" || context.user?.email_verified) return null;

  async function onResend() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await resendVerification();
      setMsg(res.message);
    } catch (err) {
      setMsg(userFacingApiError(err, "发送失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="notice notice-info">
      <IconInfo className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <span>邮箱尚未验证，部分功能可能受限。</span>
        <button
          type="button"
          onClick={() => void onResend()}
          disabled={busy}
          className="ml-2 font-medium underline decoration-brand-300 underline-offset-2 hover:decoration-brand-600 disabled:opacity-50"
        >
          {busy ? "发送中…" : "重发验证邮件"}
        </button>
        {msg ? <p className="mt-1 text-xs text-brand-700">{msg}</p> : null}
      </div>
    </div>
  );
}
