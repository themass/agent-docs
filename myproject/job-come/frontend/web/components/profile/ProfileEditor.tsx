"use client";

import { userFacingApiError } from "@/lib/api/user-error";

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
      setMessage(userFacingApiError(err, "保存失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-xl px-4 py-3.5 text-left transition hover:bg-ink-50 sm:px-5"
        aria-expanded={open}
      >
        <div>
          <p className="text-sm font-semibold text-ink-900">快速编辑</p>
          <p className="mt-0.5 text-xs text-ink-500">修改姓名、联系方式与个人总结</p>
        </div>
        <svg
          className={`h-5 w-5 text-ink-400 transition ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open ? (
        <div className="space-y-4 border-t border-surface-border px-4 pb-5 pt-4 sm:px-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink-800">姓名</span>
              <input
                className="field"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink-800">所在地</span>
              <input
                className="field"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink-800">邮箱</span>
              <input
                type="email"
                className="field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink-800">手机</span>
              <input
                className="field"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-ink-800">个人总结</span>
            <textarea
              className="field min-h-28 leading-relaxed"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </label>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="btn btn-md btn-primary"
            >
              {busy ? "保存中…" : "保存修改"}
            </button>
            {message ? (
              <p
                className={`text-sm ${message === "已保存" ? "text-success-700" : "text-danger-700"}`}
                role="status"
              >
                {message}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
