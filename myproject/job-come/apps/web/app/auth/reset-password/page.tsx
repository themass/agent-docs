"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { resetPassword } from "@/lib/api/auth";

function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setMessage("链接无效：缺少 token");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await resetPassword({ token, password });
      setMessage(res.message);
      setTimeout(() => router.push("/auth/login"), 1500);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "重置失败");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return <p className="text-sm text-red-600">链接无效或已过期，请重新申请重置密码。</p>;
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={onSubmit}>
      <label className="block text-sm">
        新密码
        <input
          type="password"
          required
          minLength={8}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {message ? <p className="text-sm text-neutral-700">{message}</p> : null}
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-neutral-900 py-2 text-white disabled:opacity-50"
      >
        {busy ? "提交中…" : "设置新密码"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-neutral-200 bg-white p-8">
      <h1 className="text-xl font-semibold">重置密码</h1>
      <Suspense fallback={<p className="mt-4 text-sm text-neutral-500">加载中…</p>}>
        <ResetPasswordForm />
      </Suspense>
      <p className="mt-4 text-center text-sm text-neutral-600">
        <Link href="/auth/login" className="underline">
          返回登录
        </Link>
      </p>
    </div>
  );
}
