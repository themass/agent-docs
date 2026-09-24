"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { changePassword } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function ChangePasswordPage() {
  const router = useRouter();
  const { context } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (context?.actor !== "user") {
    return (
      <p className="text-sm">
        请先 <Link href="/auth/login" className="underline">登录</Link>。
      </p>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await changePassword({
        current_password: current,
        new_password: next,
      });
      setMsg(res.message);
      setTimeout(() => router.push("/resume-agent"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-semibold">修改密码</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <input
          type="password"
          className="w-full rounded border px-3 py-2 text-sm"
          placeholder="当前密码"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <input
          type="password"
          className="w-full rounded border px-3 py-2 text-sm"
          placeholder="新密码（至少 8 位）"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          minLength={8}
          required
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-neutral-900 py-2 text-sm text-white disabled:opacity-50"
        >
          {busy ? "提交中…" : "确认修改"}
        </button>
      </form>
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
