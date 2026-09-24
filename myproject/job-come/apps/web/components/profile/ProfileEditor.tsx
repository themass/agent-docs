"use client";

import { useState } from "react";

import { updateProfile, type Profile } from "@/lib/api/profile";

type Props = {
  profile: Profile;
  onSaved: (profile: Profile) => void;
};

export function ProfileEditor({ profile, onSaved }: Props) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState(profile.payload.summary ?? "");
  const [name, setName] = useState(profile.payload.contact.name ?? "");
  const [email, setEmail] = useState(profile.payload.contact.email ?? "");
  const [phone, setPhone] = useState(profile.payload.contact.phone ?? "");
  const [location, setLocation] = useState(profile.payload.contact.location ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const next = await updateProfile(
        profile.id,
        {
          ...profile.payload,
          summary,
          contact: {
            ...profile.payload.contact,
            name,
            email: email || null,
            phone: phone || null,
            location: location || null,
          },
        },
        profile.version,
      );
      onSaved(next);
      setMessage("已保存");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-surface-border bg-white shadow-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
        aria-expanded={open}
      >
        <div>
          <p className="font-medium text-slate-900">快速编辑</p>
          <p className="text-xs text-slate-500">修改姓名、联系方式与个人总结</p>
        </div>
        <svg
          className={`h-5 w-5 text-slate-400 transition ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open ? (
        <div className="space-y-4 border-t border-surface-border px-5 pb-5 pt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">姓名</span>
              <input
                className="w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">所在地</span>
              <input
                className="w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">邮箱</span>
              <input
                type="email"
                className="w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">手机</span>
              <input
                className="w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">个人总结</span>
            <textarea
              className="min-h-24 w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </label>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {busy ? "保存中…" : "保存修改"}
            </button>
            {message ? <p className="text-sm text-slate-600">{message}</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
