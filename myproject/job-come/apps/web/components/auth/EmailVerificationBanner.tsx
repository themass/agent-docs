"use client";

import { useState } from "react";

import { resendVerification } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

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
      setMsg(err instanceof Error ? err.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
      <span>邮箱尚未验证，部分功能可能受限。</span>
      <button
        type="button"
        onClick={() => void onResend()}
        disabled={busy}
        className="ml-3 underline disabled:opacity-50"
      >
        重发验证邮件
      </button>
      {msg ? <span className="ml-2 text-sky-700">{msg}</span> : null}
    </div>
  );
}
