"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useCallback, useState } from "react";

import { ProfileParseProgress } from "@/components/profile/ProfileParseProgress";
import { uploadProfile, type Profile } from "@/lib/api/profile";
import { isProfileParseInFlight } from "@/lib/profile-parse";

type Props = {
  onUploaded: (profile: Profile) => void;
  hasProfile?: boolean;
  profile?: Profile | null;
};

const ACCEPTED_RESUME_TYPES = ".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp";

export function ProfileUploader({ onUploaded, hasProfile = false, profile = null }: Props) {
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      try {
        // The upload endpoint creates a profile/source synchronously; parsing continues in the background.
        // Switch to the progress card immediately rather than keeping the user on an indeterminate upload state.
        const nextProfile = await uploadProfile(file);
        onUploaded(nextProfile);
      } catch (err) {
        setError(userFacingApiError(err, "上传失败"));
      } finally {
        setBusy(false);
      }
    },
    [onUploaded],
  );

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await handleFile(file);
    e.target.value = "";
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) await handleFile(file);
  }

  if (hasProfile && isProfileParseInFlight(profile)) {
    return (
      <ProfileParseProgress
        source={profile?.sources[0]}
        replacing={busy}
        error={error}
        onFileSelected={onChange}
      />
    );
  }

  if (hasProfile) {
    return (
      <div className="card-sunken flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <p className="text-sm text-ink-600">需要替换简历？拖拽新文件到此处或点击上传</p>
        <label className="btn btn-sm btn-secondary cursor-pointer">
          {busy ? "上传中…" : "重新上传"}
          <input
            type="file"
            className="sr-only"
            accept={ACCEPTED_RESUME_TYPES}
            disabled={busy}
            onChange={onChange}
          />
        </label>
        {error ? (
          <div className="notice notice-danger w-full" role="alert">
            <span>{error}</span>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={`relative overflow-hidden rounded-2xl border border-dashed p-10 text-center transition ${
        dragOver
          ? "border-brand-400 bg-brand-50/70 shadow-raised"
          : "border-surface-border-strong bg-sheen shadow-card"
      }`}
    >
      {/* Soft brand glow, kept well under the content so text contrast is unaffected. */}
      <div
        className="pointer-events-none absolute -top-16 left-1/2 h-48 w-[28rem] -translate-x-1/2 rounded-full bg-brand-200/35 blur-3xl"
        aria-hidden
      />
      <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-brand">
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      </div>
      <h2 className="relative mt-5 text-xl font-semibold tracking-tight text-ink-900">
        上传你的简历
      </h2>
      <p className="relative mx-auto mt-2 max-w-prose text-sm leading-relaxed text-ink-500">
        支持 PDF、Word、图片。解析后自动提取工作经历、项目与技能，整理成可编辑的职业档案。
      </p>
      <label className="btn btn-lg btn-primary-emphasis relative mt-6 cursor-pointer">
        {busy ? "上传中…" : "选择文件"}
        <input
          type="file"
          className="sr-only"
          accept={ACCEPTED_RESUME_TYPES}
          disabled={busy}
          onChange={onChange}
        />
      </label>
      <p className="relative mt-3 text-xs text-ink-500">或把文件拖到这片区域</p>

      {/* What happens next: removes the "I uploaded, now what?" gap. */}
      <ul className="relative mx-auto mt-8 flex max-w-xl flex-wrap items-center justify-center gap-x-5 gap-y-2 border-t border-surface-border pt-5">
        {[
          "解析并整理成结构化档案",
          "你逐段确认事实",
          "按岗位生成优化稿",
        ].map((text, idx) => (
          <li key={text} className="flex items-center gap-1.5 text-xs text-ink-500">
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-ink-100 text-micro font-semibold text-ink-500">
              {idx + 1}
            </span>
            {text}
          </li>
        ))}
      </ul>

      {error ? (
        <div className="notice notice-danger relative mt-5 text-left" role="alert">
          <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}
