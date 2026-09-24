"use client";

import { useCallback, useState } from "react";

import { uploadProfile, type Profile } from "@/lib/api/profile";

type Props = {
  onUploaded: (profile: Profile) => void;
  hasProfile?: boolean;
};

export function ProfileUploader({ onUploaded, hasProfile = false }: Props) {
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      try {
        const profile = await uploadProfile(file);
        onUploaded(profile);
      } catch (err) {
        setError(err instanceof Error ? err.message : "上传失败");
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

  if (hasProfile) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed border-brand-200 bg-brand-50/40 px-4 py-3">
        <p className="text-sm text-brand-800">需要替换简历？拖拽新文件到此处或点击上传</p>
        <label className="inline-flex cursor-pointer items-center rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-brand-700 shadow-sm ring-1 ring-brand-100 hover:bg-brand-50">
          {busy ? "上传中…" : "重新上传"}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
            disabled={busy}
            onChange={onChange}
          />
        </label>
        {error ? <p className="w-full text-sm text-red-600">{error}</p> : null}
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
      className={`relative overflow-hidden rounded-2xl border-2 border-dashed p-10 text-center transition-all ${
        dragOver
          ? "border-brand-500 bg-brand-50/80"
          : "border-slate-200 bg-gradient-to-b from-white to-slate-50/80"
      }`}
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-brand-100/60 blur-2xl" />
      <div className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-lg shadow-brand-600/25">
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      </div>
      <h2 className="relative mt-5 text-lg font-semibold text-slate-900">上传你的简历</h2>
      <p className="relative mt-2 text-sm text-slate-500">
        支持 PDF、Word、图片。解析后将自动提取工作经历、项目与技能。
      </p>
      <label className="relative mt-6 inline-flex cursor-pointer items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-medium text-white shadow-md shadow-brand-600/20 transition hover:bg-brand-700">
        {busy ? "解析中…" : "选择文件"}
        <input
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
          disabled={busy}
          onChange={onChange}
        />
      </label>
      <p className="relative mt-3 text-xs text-slate-400">或拖拽文件到此区域</p>
      {error ? <p className="relative mt-3 text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
