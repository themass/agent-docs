"use client";

import Link from "next/link";
import { useState } from "react";

import { forgotPassword } from "@/lib/api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const res = await forgotPassword({ email });
      setMessage(res.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-xl border border-neutral-200 bg-white p-8">
      <h1 className="text-xl font-semibold">忘记密码</h1>
      <p className="mt-2 text-sm text-neutral-600">输入注册邮箱，我们将发送重置链接。</p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm">
          邮箱
          <input
            type="email"
            required
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        {message ? <p className="text-sm text-neutral-700">{message}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-neutral-900 py-2 text-white disabled:opacity-50"
        >
          {busy ? "发送中…" : "发送重置邮件"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-neutral-600">
        <Link href="/auth/login" className="underline">
          返回登录
        </Link>
      </p>
    </div>
  );
}
