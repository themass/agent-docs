"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
import { resetPassword } from "@/lib/api/auth";

function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setMessage("链接无效：缺少 token");
      setOk(false);
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await resetPassword({ token, password });
      setMessage(res.message);
      setOk(true);
      setTimeout(() => router.push("/auth/login"), 1500);
    } catch (err) {
      setMessage(userFacingApiError(err, "重置失败"));
      setOk(false);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="notice notice-danger" role="alert">
        <span>链接无效或已过期，请重新申请重置密码。</span>
      </div>
    );
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <AuthField
        label="新密码"
        hint="至少 8 位。"
        type="password"
        required
        minLength={8}
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      {message ? (
        <div className={`notice ${ok ? "notice-success" : "notice-danger"}`} role="status">
          <span>{message}</span>
        </div>
      ) : null}

      <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
        {busy ? "提交中…" : "设置新密码"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="重置密码"
      footer={
        <Link href="/auth/login" className="font-medium text-brand-700 hover:text-brand-800">
          返回登录
        </Link>
      }
    >
      <Suspense fallback={<div className="skeleton h-24 w-full" />}>
        <ResetPasswordForm />
      </Suspense>
    </AuthShell>
  );
}
