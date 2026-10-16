"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
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
      setError(userFacingApiError(err, "注册失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="注册"
      subtitle="上传一份简历就能开始，整个过程不需要填表。"
      footer={
        <>
          已有账号？{" "}
          <Link href="/auth/login" className="font-medium text-brand-700 hover:text-brand-800">
            登录
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
        <AuthField
          label="昵称"
          hint="可选，用于界面称呼。"
          autoComplete="nickname"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <AuthField
          label="密码"
          hint="至少 8 位。"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error ? (
          <div className="notice notice-danger" role="alert">
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" disabled={busy} className="btn btn-md btn-primary-emphasis w-full">
          {busy ? "注册中…" : "创建账号"}
        </button>
        <p className="text-xs leading-relaxed text-ink-500">
          注册后会向这个邮箱发送一封验证邮件，验证后才能导出简历。
        </p>
      </form>
    </AuthShell>
  );
}
