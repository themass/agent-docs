"use client";

import { userFacingApiError, userFacingElevateError } from "@/lib/api/user-error";

import { useEffect, useRef, useState } from "react";

import { getElevatePreview, listResumeTracks, localizeProfile, type ElevatePreview, type ResumeTrack, type TrackState } from "@/lib/api/resume";
import { LEVEL_GUIDE, summarizeTechniques } from "@/lib/elevation-techniques";
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
  onGoToExport?: () => void;
  onExported?: () => void;
  autoLoad?: boolean;
  generateTick?: number;
  onBusyChange?: (busy: boolean) => void;
  jobId?: string | null;
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

type ElevationLevel = "conservative" | "standard" | "elevated";

const LEVELS: ElevationLevel[] = ["conservative", "standard", "elevated"];

const TRACKS = [
  { id: "zh-CN" as const, label: "中文简历" },
  { id: "en-US" as const, label: "英文简历" },
  { id: "zh-en" as const, label: "双语对照" },
];

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
  onGoToExport,
}: Props) {
  const [level, setLevel] = useState<ElevationLevel>("standard");
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
        level: (data.draft.elevation_level as ElevationLevel) || level,
      });
      await refreshTracks();
    } catch (err) {
      setError(userFacingElevateError(err));
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

  const techniqueSummary = summarizeTechniques(
    (preview?.draft.elevation_map ?? []) as Array<{ techniques?: unknown }>,
  );
  const coverage = preview?.coverage ?? null;
  // Shown only when something is missing. On a complete draft this panel would be
  // noise between the controls and the document itself.
  const coverageGap = Boolean(
    coverage && (coverage.projects_missing || coverage.dropped.length > 0),
  );
  // Only the length half of diagnostics belongs here. Keyword gaps are acted on by
  // editing the profile against a JD, which is step 4's job; length is acted on right
  // here by regenerating, changing the angle, or answering an evidence question.
  const diag = preview?.diagnostics ?? null;
  const lengthWarning = diag
    ? diag.estimated_pages < 0.6
      ? "偏薄：回到左侧待补充项，把成果写进要点比留白更能说明你做过什么。"
      : diag.estimated_pages > 2.2
        ? "偏长：招聘方首轮通常只扫第一页，把最强的经历和要点排到最前面。"
        : null
    : null;

  return (
    <div className="flex min-h-0 flex-col gap-3">
      {/* Controls: language track + elevation level, grouped in one panel. */}
      <div className="shrink-0 card card-pad">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="label-meta">语言轨</span>
          <div className="segment">
            {TRACKS.map((opt) => {
              const state = tracks?.[opt.id];
              const blocked = opt.id === "zh-en" && state?.status === "blocked";
              const pending = state?.status === "pending" || state?.status === "stale";
              const active = locale === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  disabled={blocked}
                  onClick={() => setLocale(opt.id)}
                  aria-pressed={active}
                  className={`segment-item ${active ? "segment-item-active" : ""}`}
                  title={blocked ? "请先生成中文稿和英文稿" : undefined}
                >
                  {opt.label}
                  {pending ? (
                    <span className="ml-1 text-ink-500">生成中</span>
                  ) : null}
                  {blocked ? (
                    <span className="ml-1 text-ink-500">未就绪</span>
                  ) : null}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            disabled={localizeBusy}
            onClick={() => {
              setLocalizeBusy(true);
              void localizeProfile(profileId)
                .then(() => loadPreview())
                .catch((err) => setError(userFacingApiError(err, "重译失败")))
                .finally(() => setLocalizeBusy(false));
            }}
            className="btn btn-sm btn-ghost"
          >
            {localizeBusy ? "重译中…" : "重新生成译文"}
          </button>
        </div>

        <div className="mt-4 border-t border-surface-border pt-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="label-meta">优化强度</span>
            <div className="segment">
              {LEVELS.map((id) => {
                const active = level === id;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setLevel(id)}
                    aria-pressed={active}
                    className={`segment-item ${active ? "segment-item-active" : ""}`}
                  >
                    {LEVEL_GUIDE[id].label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="card-sunken mt-3 p-3">
            <p className="text-sm font-medium text-ink-900">{LEVEL_GUIDE[level].summary}</p>
            <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-600">
              {LEVEL_GUIDE[level].detail}
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-ink-500">
              <svg
                viewBox="0 0 16 16"
                aria-hidden="true"
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400"
                fill="currentColor"
              >
                <path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm0 2.75a.9.9 0 1 1 0 1.8.9.9 0 0 1 0-1.8ZM7.2 7.2h1.6v4.4H7.2V7.2Z" />
              </svg>
              三档控制的是措辞离原文多远，任何一档都不会替你编造没发生过的事实。
            </p>
          </div>
        </div>

        {error ? (
          <div className="notice notice-danger mt-3" role="alert">
            <span>{error}</span>
          </div>
        ) : null}
      </div>

      {/* Coverage warning. Surfaced here rather than only at export because this is
          the screen where the user can do something about it: regenerate, change the
          angle, or answer an evidence question. */}
      {coverageGap && coverage ? (
        <div className="shrink-0 notice notice-warn" role="status">
          <div className="min-w-0">
            <p className="text-xs font-medium">
              档案里有 {coverage.source_highlights} 条经历要点，这份稿只写进了 {coverage.covered} 条
            </p>
            <p className="mt-1 text-xs leading-relaxed opacity-90">
              {coverage.projects_missing
                ? "项目经历整节缺失，建议重新生成。"
                : `未出现：${coverage.dropped
                    .slice(0, 3)
                    .map((d) => d.text.slice(0, 20))
                    .join("；")}${coverage.dropped.length > 3 ? " 等" : ""}。重复表述可忽略。`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadPreview()}
            disabled={busy}
            className="btn btn-sm btn-secondary shrink-0"
          >
            {busy ? "生成中…" : "重新生成"}
          </button>
        </div>
      ) : null}

      {/* View switcher */}
      <div className="segment shrink-0 self-start">
        {(["structured", "preview", "changes"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setView(tab)}
            aria-pressed={view === tab}
            className={`segment-item px-3 py-1.5 ${view === tab ? "segment-item-active" : ""}`}
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
        <div className="overflow-hidden rounded-2xl border border-surface-border bg-surface-sunken shadow-card">
          <div className="flex items-center justify-between gap-2 border-b border-surface-border bg-surface/80 px-3.5 py-2 backdrop-blur">
            <span className="text-xs text-ink-500">
              A4 版式预览，导出的 PDF / 网页版与此一致
            </span>
            {onGoToExport ? (
              <button
                type="button"
                onClick={onGoToExport}
                className="btn btn-sm btn-ghost text-brand-700 hover:text-brand-800"
              >
                去导出 →
              </button>
            ) : null}
          </div>
          <iframe
            title="resume-preview"
            className="h-[min(74vh,980px)] w-full border-0 bg-surface-sunken"
            srcDoc={preview.html}
          />
        </div>
      ) : (
        <div className="card-sunken bg-sheen flex flex-col items-center justify-center gap-3 py-20 text-center">
          {busy ? (
            <>
              <svg
                viewBox="0 0 24 24"
                aria-hidden="true"
                className="h-6 w-6 animate-spin text-brand-500"
                fill="none"
              >
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
              <div>
                <p className="text-sm font-medium text-ink-800">正在生成优化预览</p>
                <p className="mt-1 text-xs text-ink-500">写作模型正在逐条重写要点，通常需要十几秒。</p>
              </div>
            </>
          ) : (
            <div>
              <p className="text-sm font-medium text-ink-800">还没有优化稿</p>
              <p className="mt-1 text-xs text-ink-500">
                先在上方选好语言轨与优化强度，然后点顶部「生成预览」。
              </p>
            </div>
          )}
        </div>
      )}

      {/* What the draft did, read after the document rather than before it: these
          answer "what changed" and are not worth pushing the resume below the fold. */}
      {techniqueSummary.length ? (
        <div className="shrink-0 card card-pad">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink-900">本稿用到的强化手段</h3>
            <button
              type="button"
              onClick={() => setView("changes")}
              className="btn btn-sm btn-ghost text-brand-700 hover:text-brand-800"
            >
              逐条查看改动 →
            </button>
          </div>
          <ul className="mt-2.5 flex flex-wrap gap-1.5">
            {techniqueSummary.map((t) => (
              <li key={t.id} title={t.hint} className="badge badge-brand">
                {t.label}
                <span className="text-brand-600/70">{t.count} 处</span>
              </li>
            ))}
          </ul>
          {/* Length lives on the same card instead of a fourth panel: step 3 is already
              dense, and this is one line of information, not a section. */}
          {diag ? (
            <p
              className={`mt-3 border-t border-surface-border pt-2.5 text-xs leading-relaxed ${
                lengthWarning ? "text-warn-900" : "text-ink-500"
              }`}
            >
              估算篇幅约 {diag.estimated_pages} 页 · {diag.bullet_count} 条要点
              {lengthWarning ? ` · ${lengthWarning}` : ""}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Hand-off to step 4 */}
      {onGoToExport ? (
        <div className="shrink-0 card bg-sheen card-pad">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink-900">内容满意了？</p>
              <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
                下一步会做一次导出前质检，然后选 PDF / Word / 网页版下载。
              </p>
            </div>
            <button
              type="button"
              onClick={onGoToExport}
              disabled={!preview}
              className="btn btn-md btn-primary-emphasis"
            >
              内容定稿，去导出
            </button>
          </div>
          {!preview ? (
            <p className="mt-2.5 text-xs text-ink-500">先生成一份优化稿才能进入导出。</p>
          ) : null}
        </div>
      ) : null}

      {error && locale !== "zh-CN" ? (
        <p className="max-w-prose text-xs leading-relaxed text-ink-500">
          英文稿由写作模型按英文重写（有译文会先套用）。失败不影响已生成的中文稿，顶部导出仍用上次成功预览。
        </p>
      ) : null}
    </div>
  );
}
