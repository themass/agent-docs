"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useCallback, useState } from "react";

import { ProfileParseProgress } from "@/components/profile/ProfileParseProgress";
import {
  createProfile,
  ingestProfileText,
  uploadProfileWithProgress,
  type Profile,
} from "@/lib/api/profile";
import { hasProfileFacts, isProfileParseInFlight, latestProfileSource } from "@/lib/profile-parse";
import { ZHOUKA_NAME } from "@/lib/brand";

/**
 * How the user chose to build an empty profile.
 *
 * Both routes existed before, but one button offered them: 「用对话建一份简历」 opened
 * the structured question panel, which is a form — not the conversation the label
 * promised. They are different tools for different people, so they are now different
 * choices.
 */
export type StartMode = "chat" | "interview";

type Props = {
  onUploaded: (profile: Profile) => void;
  hasProfile?: boolean;
  profile?: Profile | null;
  /**
   * Start an empty profile and build it by talking or by answering questions, instead
   * of by upload. Without this the product had exactly one way in, and a user with no
   * resume — or one too old to be worth uploading — had nothing to do here.
   */
  onStartInterview?: (profile: Profile, mode: StartMode) => void;
};

/** Mirrors the server floor in `ProfileIngestService.validate_text`. */
const MIN_PASTE_CHARS = 80;

const ACCEPTED_RESUME_TYPES = ".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp";
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export function ProfileUploader({
  onUploaded,
  hasProfile = false,
  profile = null,
  onStartInterview,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<StartMode | null>(null);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");

  async function startWithoutResume(mode: StartMode) {
    if (!onStartInterview) return;
    setStarting(mode);
    setError(null);
    try {
      onStartInterview(await createProfile(), mode);
    } catch (err) {
      setError(userFacingApiError(err, "无法创建空档案"));
    } finally {
      setStarting(null);
    }
  }

  const pasteChars = pasteText.trim().length;

  async function submitPaste() {
    if (pasteChars < MIN_PASTE_CHARS) return;
    setBusy(true);
    setError(null);
    try {
      // Same hand-off as upload: the profile comes back with its source still
      // parsing, so the caller switches to the progress card rather than waiting
      // out a model call behind a spinner.
      const nextProfile = await ingestProfileText(pasteText);
      setPasteText("");
      setPasteOpen(false);
      onUploaded(nextProfile);
    } catch (err) {
      setError(userFacingApiError(err, "这段内容没能建档，请补充一些信息再试。"));
    } finally {
      setBusy(false);
    }
  }

  const handleFile = useCallback(
    async (file: File) => {
      if (file.size > MAX_UPLOAD_BYTES) {
        setError("文件超过 15 MB，请压缩后再上传。");
        return;
      }
      setBusy(true);
      setUploadPercent(0);
      setError(null);
      try {
        const nextProfile = await uploadProfileWithProgress(file, setUploadPercent);
        onUploaded(nextProfile);
      } catch (err) {
        setError(userFacingApiError(err, "上传失败"));
      } finally {
        setBusy(false);
        setUploadPercent(null);
      }
    },
    [onUploaded],
  );

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // Clear synchronously: a successful upload can unmount this input.
    // It also lets selecting the same file fire change after a failed attempt.
    e.currentTarget.value = "";
    await handleFile(file);
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) await handleFile(file);
  }

  if (isProfileParseInFlight(profile)) {
    return (
      <ProfileParseProgress
        source={latestProfileSource(profile)}
        replacing={busy}
        error={error}
        onFileSelected={onChange}
      />
    );
  }

  const failedSource = latestProfileSource(profile);
  if (failedSource?.parse_status === "failed") {
    return (
      <section className="rounded-2xl border border-red-200 bg-red-50/60 p-5" role="alert">
        <h3 className="text-sm font-semibold text-red-900">简历解析未完成</h3>
        <p className="mt-2 break-words text-sm text-red-800">{failedSource.parse_error || "解析服务暂时未完成处理，原文件已保留。请稍后重试。"}</p>
        <p className="mt-2 text-xs text-ink-600">
          {hasProfileFacts(profile) ? "原有档案未被覆盖，仍可查看和编辑。" : "本次没有生成可确认的档案，不会将空内容视为解析成功。"}
        </p>
        <label className="btn btn-sm btn-secondary mt-4 cursor-pointer">
          {busy ? "上传中…" : "重新上传解析"}
          <input type="file" className="sr-only" accept={ACCEPTED_RESUME_TYPES} disabled={busy} onChange={onChange} />
        </label>
        {onStartInterview ? (
          <div className="mt-4 border-t border-red-200 pt-4">
            <p className="text-xs text-ink-600">也可以先从空白简历开始，不必等待解析服务恢复。</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" disabled={starting !== null || busy} onClick={() => void startWithoutResume("interview")} className="btn btn-sm btn-secondary">
                {starting === "interview" ? "正在准备…" : "从零填写简历"}
              </button>
              <button type="button" disabled={starting !== null || busy} onClick={() => void startWithoutResume("chat")} className="btn btn-sm btn-ghost">
                {starting === "chat" ? "正在准备…" : `和${ZHOUKA_NAME}聊着写`}
              </button>
            </div>
          </div>
        ) : null}
        {error ? <p className="mt-2 text-sm text-red-800">{error}</p> : null}
      </section>
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
        开始准备你的简历
      </h2>
      <p className="relative mx-auto mt-2 max-w-prose text-sm leading-relaxed text-ink-500">
        没有简历可以从零创建；已有完整、半成品或旧简历，可以上传后继续补全。
      </p>
      {onStartInterview ? (
        <section className="relative mx-auto mt-6 w-full max-w-2xl rounded-2xl border border-brand-200 bg-brand-50/70 p-4 text-left shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink-900">没有简历？也可以从零开始</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-600">
                直接补全经历，舟卡会帮你整理成可编辑的简历草稿；已有旧简历也可以先上传再补充。
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <button type="button" onClick={() => void startWithoutResume("chat")} disabled={starting !== null} className="btn btn-sm btn-primary">
                {starting === "chat" ? "正在准备…" : `和${ZHOUKA_NAME}聊着写`}
              </button>
              <button type="button" onClick={() => void startWithoutResume("interview")} disabled={starting !== null} className="btn btn-sm btn-secondary">
                {starting === "interview" ? "正在准备…" : "按问题填写"}
              </button>
            </div>
          </div>
        </section>
      ) : null}
      <p className="relative mt-5 text-xs text-ink-500">已有简历或很久没更新？上传后可以继续补全和修改</p>
      <label className="btn btn-lg btn-primary-emphasis relative mt-2 cursor-pointer">
        {busy ? (
          uploadPercent === null
            ? "正在创建档案…"
            : uploadPercent >= 100
              ? "文件已传完，正在保存…"
              : `上传中 ${uploadPercent}%`
        ) : "选择文件"}
        <input
          type="file"
          className="sr-only"
          accept={ACCEPTED_RESUME_TYPES}
          disabled={busy}
          onChange={onChange}
        />
      </label>
      {busy && uploadPercent !== null ? (
        <div className="relative mx-auto mt-3 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-brand-100" aria-label={`文件上传进度 ${uploadPercent}%`}>
          <div className="h-full rounded-full bg-brand-600 transition-[width] duration-150" style={{ width: `${uploadPercent}%` }} />
        </div>
      ) : null}
      <p className="relative mt-3 text-xs text-ink-500">或把文件拖到这片区域</p>

      {/* Second way in: text. A resume that lives in a chat message, or a paragraph the
          user would rather type than save as a file, used to require creating a `.txt`
          first. Same parse pipeline as upload once submitted. */}
      <div className="relative mx-auto mt-6 max-w-prose border-t border-surface-border pt-5 text-left">
        {!pasteOpen ? (
          <div className="text-center">
            <button
              type="button"
              onClick={() => setPasteOpen(true)}
              className="btn btn-md btn-secondary"
            >
              粘贴简历内容
            </button>
            <p className="mt-2 text-xs text-ink-500">
              手上没有文件也行，直接把旧简历原文或一段自述贴进来
            </p>
          </div>
        ) : (
          <div>
            <label
              htmlFor="profile-paste"
              className="block text-sm font-medium text-ink-800"
            >
              粘贴简历原文，或写一段你做过什么
            </label>
            <p className="mt-1 text-xs leading-relaxed text-ink-500">
              带上公司、时间和具体做的事。信息越全，整理出的档案越准。
            </p>
            <textarea
              id="profile-paste"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              rows={8}
              disabled={busy}
              placeholder={
                "示例：\n2019.03-2024.08 字节跳动 推荐架构组 技术专家\n负责召回链路重构，QPS 从 3 万提升到 12 万，P99 下降 40%\n带 6 人小组完成特征平台迁移"
              }
              className="field mt-3 min-h-[11rem] w-full resize-y leading-relaxed"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-ink-500">
                {pasteChars === 0
                  ? `至少 ${MIN_PASTE_CHARS} 字`
                  : pasteChars < MIN_PASTE_CHARS
                    ? `还差 ${MIN_PASTE_CHARS - pasteChars} 字`
                    : `${pasteChars} 字`}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPasteOpen(false);
                    setError(null);
                  }}
                  disabled={busy}
                  className="btn btn-sm btn-ghost"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => void submitPaste()}
                  disabled={busy || pasteChars < MIN_PASTE_CHARS}
                  className="btn btn-sm btn-primary"
                >
                  {busy ? "正在建档…" : "开始整理"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

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
