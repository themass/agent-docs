"use client";

import { useEffect, useRef, useState } from "react";

import { getElevatePreview, listResumeTracks, localizeProfile, type ElevatePreview, type ResumeTrack, type TrackState } from "@/lib/api/resume";
import type { AgentUiFocus } from "@/lib/ui-context";

import { ElevationChangesPanel } from "./ElevationChangesPanel";
import { ResumeStructuredPreview } from "./ResumeStructuredPreview";

type Props = {
  profileId: string;
  canExport: boolean;
  onPreviewLoaded?: (info: {
    draftId: string;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  }) => void;
  onExported?: () => void;
  autoLoad?: boolean;
  generateTick?: number;
  onBusyChange?: (busy: boolean) => void;
  jobId?: string | null;
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

const LEVELS = [
  { id: "conservative" as const, label: "保守", desc: "贴近原文，微调措辞" },
  { id: "standard" as const, label: "标准", desc: "适度优化，突出职责" },
  { id: "elevated" as const, label: "强化", desc: "强化成果与影响力" },
];

const TRACKS = [
  { id: "zh-CN" as const, label: "中文简历" },
  { id: "en-US" as const, label: "英文简历" },
  { id: "zh-en" as const, label: "双语对照" },
];

function previewErrorMessage(err: unknown): string {
  const raw = err instanceof Error ? err.message : "优化预览失败";
  if (/ECONNRESET|hang up|Failed to proxy|timeout/i.test(raw)) {
    return "英文预览请求中断。英文稿由写作模型按英文重写（有译文会先套用）；请切回「中文简历」导出，或稍后重试英文。";
  }
  return raw;
}

export function ElevatePreviewPanel({
  profileId,
  canExport: _canExport,
  onPreviewLoaded,
  onExported: _onExported,
  autoLoad = false,
  generateTick = 0,
  onBusyChange,
  jobId = null,
  focusPath = null,
  onUiFocus,
}: Props) {
  const [level, setLevel] = useState<"conservative" | "standard" | "elevated">("elevated");
  const [locale, setLocale] = useState<ResumeTrack>("zh-CN");
  const [tracks, setTracks] = useState<Record<ResumeTrack, TrackState> | null>(null);
  const [localizeBusy, setLocalizeBusy] = useState(false);
  const [preview, setPreview] = useState<ElevatePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"structured" | "preview" | "changes">("structured");
  const loadedRef = useRef(false);
  const trackInitRef = useRef(true);

  useEffect(() => {
    loadedRef.current = false;
    trackInitRef.current = true;
    setPreview(null);
    setTracks(null);
    setError(null);
  }, [profileId]);

  async function refreshTracks() {
    try {
      const res = await listResumeTracks(profileId, level);
      setTracks(res.tracks);
    } catch {
      setTracks(null);
    }
  }

  async function loadPreview() {
    setBusy(true);
    onBusyChange?.(true);
    setError(null);
    try {
      await refreshTracks();
      const data = await getElevatePreview(profileId, level, locale, jobId ?? undefined);
      setPreview(data);
      onPreviewLoaded?.({
        draftId: data.draft.id,
        locale,
        level: (data.draft.elevation_level as "conservative" | "standard" | "elevated") || level,
      });
      await refreshTracks();
    } catch (err) {
      setError(previewErrorMessage(err));
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  }

  useEffect(() => {
    if (!autoLoad || loadedRef.current) return;
    loadedRef.current = true;
    void loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial auto-load only
  }, [autoLoad, profileId]);

  useEffect(() => {
    if (generateTick > 0) {
      loadedRef.current = true;
      void loadPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- external trigger only
  }, [generateTick]);

  useEffect(() => {
    if (trackInitRef.current) {
      trackInitRef.current = false;
      return;
    }
    loadedRef.current = true;
    void loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when user switches track/level
  }, [locale, level]);

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="shrink-0 rounded-xl border border-surface-border bg-white p-3 shadow-card">
        <div className="flex flex-wrap items-center gap-2">
          {TRACKS.map((opt) => {
            const state = tracks?.[opt.id];
            const blocked = opt.id === "zh-en" && state?.status === "blocked";
            const pending = state?.status === "pending" || state?.status === "stale";
            return (
              <button
                key={opt.id}
                type="button"
                disabled={blocked}
                onClick={() => setLocale(opt.id)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
                  locale === opt.id
                    ? "bg-slate-900 text-white"
                    : "border border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
                title={blocked ? "请先生成中文稿和英文稿" : undefined}
              >
                {opt.label}
                {pending ? "（生成中）" : null}
                {blocked ? "（未就绪）" : null}
              </button>
            );
          })}
          <button
            type="button"
            disabled={localizeBusy}
            onClick={() => {
              setLocalizeBusy(true);
              void localizeProfile(profileId)
                .then(() => loadPreview())
                .catch((err) => setError(err instanceof Error ? err.message : "重译失败"))
                .finally(() => setLocalizeBusy(false));
            }}
            className="rounded-md border border-dashed border-slate-300 px-2.5 py-1 text-[11px] text-slate-500 hover:bg-slate-50 disabled:opacity-50"
          >
            {localizeBusy ? "重译中…" : "重新生成译文"}
          </button>
          <span className="mx-1 hidden h-4 w-px bg-slate-200 sm:inline" aria-hidden />
          {LEVELS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setLevel(opt.id)}
              title={opt.desc}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium ${
                level === opt.id
                  ? "bg-brand-600 text-white"
                  : "border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
      </div>

      <div className="flex shrink-0 gap-1 rounded-xl border border-surface-border bg-white p-1">
        {(["structured", "preview", "changes"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setView(tab)}
            className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition ${
              view === tab ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            {tab === "structured" ? "结构化要点" : tab === "preview" ? "HTML 预览" : "变更对比"}
          </button>
        ))}
      </div>

      {view === "changes" ? (
        <ElevationChangesPanel draft={preview?.draft ?? null} />
      ) : view === "structured" ? (
        <ResumeStructuredPreview
          draft={preview?.draft ?? null}
          focusPath={focusPath}
          onUiFocus={onUiFocus}
        />
      ) : preview ? (
        <iframe
          title="resume-preview"
          className="h-[min(72vh,900px)] w-full rounded-xl border border-surface-border bg-white shadow-inner"
          srcDoc={preview.html}
        />
      ) : (
        <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 py-16 text-center text-sm text-slate-500">
          {busy ? "正在生成优化预览…" : "选择档位后点击顶部「生成预览」"}
        </p>
      )}

      {error && locale !== "zh-CN" ? (
        <p className="text-xs text-slate-500">
          英文稿由写作模型按英文重写（有译文会先套用）。失败不影响已生成的中文稿，顶部导出仍用上次成功预览。
        </p>
      ) : null}
    </div>
  );
}
