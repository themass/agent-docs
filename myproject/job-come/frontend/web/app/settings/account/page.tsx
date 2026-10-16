"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  getAccount,
  logout,
  resendVerification,
  updateAccount,
  verifyEmailCode,
  type Account,
} from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";

function errorMessage(error: unknown, fallback: string) {
  return userFacingApiError(error, fallback);
}

export default function AccountSettingsPage() {
  const router = useRouter();
  const { context, loading, refresh } = useAuth();
  const [account, setAccount] = useState<Account | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [locale, setLocale] = useState<Account["locale"]>("zh-CN");
  const [elevation, setElevation] = useState<Account["default_elevation_level"]>("elevated");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (context?.actor !== "user") return;
    void getAccount()
      .then((data) => {
        setAccount(data);
        setDisplayName(data.display_name ?? "");
        setLocale(data.locale);
        setElevation(data.default_elevation_level);
      })
      .catch((err) => setError(errorMessage(err, "无法读取账户设置")));
  }, [context?.actor]);

  if (loading) return <p className="text-sm text-ink-500">正在加载账户设置…</p>;
  if (context?.actor !== "user") {
    return (
      <div className="card bg-sheen mx-auto max-w-md px-6 py-10 text-center">
        <p className="text-sm text-ink-600">
          请先{" "}
          <Link className="font-medium text-brand-700 hover:text-brand-800" href="/auth/login">
            登录
          </Link>{" "}
          后管理账户设置。
        </p>
      </div>
    );
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const updated = await updateAccount({
        display_name: displayName,
        locale,
        default_elevation_level: elevation,
      });
      setAccount(updated);
      setNotice("账户设置已保存。");
      await refresh();
    } catch (err) {
      setError(errorMessage(err, "保存账户设置失败"));
    } finally {
      setSaving(false);
    }
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    setVerifying(true);
    setNotice(null);
    setError(null);
    try {
      const result = await verifyEmailCode({ code });
      setNotice(result.message);
      setCode("");
      await refresh();
      setAccount((current) => (current ? { ...current, email_verified: true } : current));
    } catch (err) {
      setError(errorMessage(err, "验证失败"));
    } finally {
      setVerifying(false);
    }
  }

  async function sendAgain() {
    setResending(true);
    setNotice(null);
    setError(null);
    try {
      const result = await resendVerification();
      setNotice(`${result.message} 邮件内同时包含验证链接和 4 位验证码。`);
    } catch (err) {
      setError(errorMessage(err, "发送失败"));
    } finally {
      setResending(false);
    }
  }

  async function signOut() {
    await logout();
    await refresh();
    router.push("/auth/login");
  }

  const verified = account?.email_verified ?? context.user?.email_verified;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-section">
      <PageHeader
        title="账户设置"
        description="管理个人资料、邮箱验证与登录安全。"
      />

      {notice ? (
        <div className="notice notice-success" role="status">
          <span>{notice}</span>
        </div>
      ) : null}
      {error ? (
        <div className="notice notice-danger" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      <form onSubmit={saveProfile} className="card card-pad space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink-900">个人资料</h2>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            邮箱在 V1 中不能直接修改；如需变更请联系支持。
          </p>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink-800">显示名称</span>
          <input
            className="field mt-1.5"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            maxLength={128}
            placeholder="例如：李明"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink-800">界面语言</span>
            <select
              className="field mt-1.5"
              value={locale}
              onChange={(event) => setLocale(event.target.value as Account["locale"])}
            >
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink-800">默认表达力度</span>
            <select
              className="field mt-1.5"
              value={elevation}
              onChange={(event) =>
                setElevation(event.target.value as Account["default_elevation_level"])
              }
            >
              <option value="conservative">保守：只做清晰表达</option>
              <option value="standard">标准：突出结果与影响</option>
              <option value="elevated">进阶：更主动地组织高价值表达</option>
            </select>
            <span className="mt-1 block text-xs text-ink-500">
              新建优化稿时的默认档位，每次仍可单独调整。
            </span>
          </label>
        </div>
        <div className="border-t border-surface-border pt-4">
          <button className="btn btn-md btn-primary" disabled={saving} type="submit">
            {saving ? "保存中…" : "保存个人配置"}
          </button>
        </div>
      </form>

      <section className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-ink-900">邮箱验证</h2>
            <p className="mt-1 truncate text-sm text-ink-600">{context.user?.email}</p>
          </div>
          <span className={`badge ${verified ? "badge-success" : "badge-warn"}`}>
            {verified ? "已验证" : "未验证"}
          </span>
        </div>
        {verified ? (
          <p className="mt-3 text-sm text-ink-500">这个邮箱已完成验证，可以正常导出简历。</p>
        ) : (
          <>
            <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-600">
              验证邮件提供两种方式：点击邮件里的链接，或在下面输入邮件中的 4 位数字验证码。
            </p>
            <form className="mt-4 flex flex-wrap items-center gap-2" onSubmit={submitCode}>
              <input
                aria-label="4 位邮箱验证码"
                className="field w-32 text-center font-mono text-lg tracking-[0.4em]"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={4}
                onChange={(event) =>
                  setCode(event.target.value.replace(/\D/g, "").slice(0, 4))
                }
                placeholder="0000"
                value={code}
              />
              <button
                className="btn btn-md btn-primary"
                disabled={verifying || code.length !== 4}
                type="submit"
              >
                {verifying ? "验证中…" : "验证"}
              </button>
              <button
                className="btn btn-md btn-ghost"
                disabled={resending}
                onClick={() => void sendAgain()}
                type="button"
              >
                {resending ? "发送中…" : "重新发送邮件"}
              </button>
            </form>
          </>
        )}
      </section>

      <section className="card card-pad">
        <h2 className="text-base font-semibold text-ink-900">登录安全</h2>
        <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
          定期更新密码可以提升账户安全性。
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Link className="btn btn-md btn-secondary" href="/auth/change-password">
            修改密码
          </Link>
          <button
            className="btn btn-md btn-ghost text-danger-700 hover:bg-danger-50 hover:text-danger-700"
            onClick={() => void signOut()}
            type="button"
          >
            退出登录
          </button>
        </div>
      </section>
    </div>
  );
}
