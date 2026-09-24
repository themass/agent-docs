"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { register } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function RegisterPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ email, password, display_name: displayName || undefined });
      await refresh();
      router.push("/resume-agent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-xl border border-neutral-200 bg-white p-8">
      <h1 className="text-xl font-semibold">注册</h1>
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
          昵称（可选）
          <input
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          密码（至少 8 位）
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
          {busy ? "注册中…" : "注册"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-neutral-600">
        已有账号？{" "}
        <Link href="/auth/login" className="text-neutral-900 underline">
          登录
        </Link>
      </p>
    </div>
  );
}
