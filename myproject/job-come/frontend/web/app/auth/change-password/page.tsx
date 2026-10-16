"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
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
      setTimeout(() => router.push("/settings/account"), 1500);
    } catch (err) {
      setError(userFacingApiError(err, "修改失败"));
    } finally {
      setBusy(false);
    }
  }

  if (context?.actor !== "user") {
    return (
      <AuthShell title="修改密码" subtitle="这个页面需要先登录。">
        <Link href="/auth/login" className="btn btn-md btn-primary w-full">
          去登录
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="修改密码"
      subtitle="修改后当前设备仍保持登录，其他设备需要重新登录。"
      footer={
        <Link
          href="/settings/account"
          className="font-medium text-brand-700 hover:text-brand-800"
        >
          返回账户设置
        </Link>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <AuthField
          label="当前密码"
          type="password"
          required
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <AuthField
          label="新密码"
          hint="至少 8 位。"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />

        {msg ? (
          <div className="notice notice-success" role="status">
            <span>{msg}</span>
          </div>
        ) : null}
        {error ? (
          <div className="notice notice-danger" role="alert">
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
          {busy ? "提交中…" : "确认修改"}
        </button>
      </form>
    </AuthShell>
  );
}
