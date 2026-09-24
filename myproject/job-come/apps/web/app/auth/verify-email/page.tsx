"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { verifyEmail } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

function VerifyEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const { refresh } = useAuth();
  const token = params.get("token") ?? "";
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setMessage("链接无效：缺少 token");
      return;
    }
    void verifyEmail({ token })
      .then(async (res) => {
        setMessage(res.message);
        await refresh();
        setTimeout(() => router.push("/resume-agent"), 1500);
      })
      .catch((err) => {
        setMessage(err instanceof Error ? err.message : "验证失败");
      });
  }, [token, refresh, router]);

  return (
    <p className="mt-4 text-sm text-neutral-700">{message ?? "正在验证邮箱…"}</p>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-neutral-200 bg-white p-8">
      <h1 className="text-xl font-semibold">邮箱验证</h1>
      <Suspense fallback={<p className="mt-4 text-sm text-neutral-500">加载中…</p>}>
        <VerifyEmailContent />
      </Suspense>
      <p className="mt-4 text-center text-sm text-neutral-600">
        <Link href="/resume-agent" className="underline">
          返回首页
        </Link>
      </p>
    </div>
  );
}
