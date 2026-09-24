"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { login } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email, password });
      await refresh();
      router.push("/resume-agent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-xl border border-neutral-200 bg-white p-8">
      <h1 className="text-xl font-semibold">登录</h1>
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
        <label className="block text-sm">
          密码
          <input
            type="password"
            required
            minLength={8}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-neutral-900 py-2 text-white disabled:opacity-50"
        >
          {busy ? "登录中…" : "登录"}
        </button>
        {process.env.NODE_ENV === "development" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              const email = "demo@jobcome.local";
              const password = "Demo1234!";
              setEmail(email);
              setPassword(password);
              setBusy(true);
              setError(null);
              void login({ email, password })
                .then(() => refresh())
                .then(() => router.push("/resume-agent"))
                .catch((err) => setError(err instanceof Error ? err.message : "登录失败"))
                .finally(() => setBusy(false));
            }}
            className="w-full rounded-lg border border-dashed border-neutral-300 py-2 text-sm text-neutral-600 hover:bg-neutral-50 disabled:opacity-50"
          >
            一键登录演示账号（需先跑 scripts/seed_demo.py）
          </button>
        ) : null}
      </form>
      <p className="mt-3 text-center text-sm">
        <Link href="/auth/forgot-password" className="text-neutral-600 underline">
          忘记密码？
        </Link>
      </p>
      <p className="mt-4 text-center text-sm text-neutral-600">
        没有账号？{" "}
        <Link href="/auth/register" className="text-neutral-900 underline">
          注册
        </Link>
      </p>
    </div>
  );
}
