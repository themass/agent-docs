"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
import { forgotPassword } from "@/lib/api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const res = await forgotPassword({ email });
      setMessage(res.message);
      setSent(true);
    } catch (err) {
      setMessage(userFacingApiError(err, "请求失败"));
      setSent(false);
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

        {message ? (
          <div className={`notice ${sent ? "notice-success" : "notice-danger"}`} role="status">
            <span>{message}</span>
          </div>
        ) : null}

        <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
          {busy ? "发送中…" : "发送重置邮件"}
        </button>
      </form>
    </AuthShell>
  );
}
