"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
import { forgotPassword } from "@/lib/api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  // Success and failure are separate state. Sharing one `message` meant the copy and the
  // styling could disagree, and a red box that says 「已发送」 tells the user nothing.
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setSent(null);
    setError(null);
    try {
      const res = await forgotPassword({ email });
      setSent(res.message);
    } catch (err) {
      setError(userFacingApiError(err, "没能发出重置邮件，请稍后重试。"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="忘记密码"
      subtitle="输入注册邮箱，我们会发送一个重置链接。"
      footer={
        <Link href="/auth/login" className="font-medium text-brand-700 hover:text-brand-800">
          返回登录
        </Link>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <AuthField
          label="邮箱"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        {sent ? (
          <div className="notice notice-success" role="status">
            <div className="min-w-0">
              <p className="font-medium">{sent}</p>
              <p className="mt-0.5 text-xs leading-relaxed opacity-80">
                没收到的话先看一下垃圾邮件，或者过几分钟重发一次。
              </p>
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="notice notice-danger" role="alert">
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
          {busy ? "发送中…" : sent ? "重新发送" : "发送重置邮件"}
        </button>
      </form>
    </AuthShell>
  );
}
