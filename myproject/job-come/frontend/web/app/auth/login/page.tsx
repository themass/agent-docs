"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
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
      setError(userFacingApiError(err, "登录失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="登录"
      subtitle="继续完善你的职业档案和简历优化稿。"
      footer={
        <>
          没有账号？{" "}
          <Link href="/auth/register" className="font-medium text-brand-700 hover:text-brand-800">
            注册
          </Link>
        </>
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
        <div>
          <AuthField
            label="密码"
            type="password"
            required
            minLength={8}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="mt-1.5 text-right">
            <Link
              href="/auth/forgot-password"
              className="text-xs font-medium text-ink-500 hover:text-ink-800"
            >
              忘记密码？
            </Link>
          </p>
        </div>

        {error ? (
          <div className="notice notice-danger" role="alert">
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
          {busy ? "登录中…" : "登录"}
        </button>

        {process.env.NODE_ENV === "development" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              const demoEmail = "demo@jc.local";
              const demoPassword = "Demo1234!";
              setEmail(demoEmail);
              setPassword(demoPassword);
              setBusy(true);
              setError(null);
              void login({ email: demoEmail, password: demoPassword })
                .then(() => refresh())
                .then(() => router.push("/resume-agent"))
                .catch((err) => setError(userFacingApiError(err, "登录失败")))
                .finally(() => setBusy(false));
            }}
            className="w-full rounded-md border border-dashed border-surface-border-strong py-2 text-xs text-ink-500 transition hover:bg-ink-50 disabled:opacity-50"
          >
            一键登录演示账号（需先跑 scripts/seed_demo.py）
          </button>
        ) : null}
      </form>
    </AuthShell>
  );
}
