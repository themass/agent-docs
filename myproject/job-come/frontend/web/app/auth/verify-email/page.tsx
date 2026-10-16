"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthShell } from "@/components/auth/AuthShell";
import { verifyEmail } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

type State = "pending" | "ok" | "failed";

function VerifyEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const { refresh } = useAuth();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<State>("pending");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("failed");
      setMessage("链接无效：缺少 token。你也可以在账户设置里输入邮件中的 4 位验证码。");
      return;
    }
    void verifyEmail({ token })
      .then(async (res) => {
        setState("ok");
        setMessage(res.message);
        await refresh();
        setTimeout(() => router.push("/resume-agent"), 1500);
      })
      .catch((err) => {
        setState("failed");
        setMessage(userFacingApiError(err, "验证失败"));
      });
  }, [token, refresh, router]);

  if (state === "pending") {
    return (
      <div className="flex items-center gap-2.5" role="status">
        <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4 animate-spin text-brand-500" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
          <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
        <span className="text-sm text-ink-600">正在验证邮箱…</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div
        className={`notice ${state === "ok" ? "notice-success" : "notice-danger"}`}
        role={state === "ok" ? "status" : "alert"}
      >
        <span>{message}</span>
      </div>
      {state === "ok" ? (
        <p className="text-xs text-ink-500">正在带你回到简历工作台…</p>
      ) : (
        <Link href="/settings/account" className="btn btn-md btn-primary w-full">
          去账户设置输入验证码
        </Link>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell
      title="邮箱验证"
      subtitle="验证通过后即可导出简历。"
      footer={
        <Link href="/resume-agent" className="font-medium text-brand-700 hover:text-brand-800">
          返回简历工作台
        </Link>
      }
    >
      <Suspense fallback={<div className="skeleton h-10 w-full" />}>
        <VerifyEmailContent />
      </Suspense>
    </AuthShell>
  );
}
