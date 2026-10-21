"use client";

import { userFacingApiError, userFacingElevateError } from "@/lib/api/user-error";
import { excerpt } from "@/lib/excerpt";

import { useEffect, useRef, useState } from "react";

import { advancePreviewProgress, type PreviewProgress } from "@/lib/preview-progress";
import { getElevatePreview, listResumeTracks, localizeProfile, type ElevatePreview, type ResumeTrack, type TrackState } from "@/lib/api/resume";
import { LEVEL_GUIDE, summarizeTechniques } from "@/lib/elevation-techniques";
import type { AgentUiFocus } from "@/lib/ui-context";

import { BlueprintPanel } from "./BlueprintPanel";
import { ElevationChangesPanel } from "./ElevationChangesPanel";
import {
  ELEVATE_PREVIEW_TIMEOUT_MS,
  ElevatePreviewGenerating,
} from "./ElevatePreviewGenerating";
import { ResumeStructuredPreview } from "./ResumeStructuredPreview";

type Props = {
  profileId: string;
  /** Invalidate cached preview after confirmed profile edits. */
  profileVersion?: number;
  canExport: boolean;
  onPreviewLoaded?: (info: {
    draftId: string;
    profileVersion: number;
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
  /** Opens the evidence questions, which is how most unmet blueprint items get fixed. */
  onGoToEvidence?: () => void;
  /**
   * Called by the rail when the user focuses a specific bullet, so this panel can scroll
   * the document column to it.
   *
   * The two columns cannot line up: they hold different content at different heights, so
   * `align-items: start` is the only honest arrangement and the first card in each lands
   * 47px apart (measured). Users read that gap as a layout defect because the side-by-side
   * arrangement implies a correspondence. Rather than fake the alignment, the panels link:
   * focusing a question scrolls the matching bullet into view and highlights it, which is
   * the correspondence the layout was promising.
   */
  railFocusPath?: string | null;
  /**
   * Panels that belong to this step but are owned by the caller (writing options,
   * evidence questions). They render at the top of the left rail rather than above the
   * whole panel, so they can never push the document out of view — which is the one
   * thing this step may not do.
   */
  rail?: React.ReactNode;
  /** Height constraint from the step shell; the two columns scroll inside it. */
  className?: string;
  /**
   * Optimization strength, controlled by the caller so the same choice can live in the
   * sticky toolbar (`ResumeWorkflowActions`) and stay visible on any screen width.
   *
   * Before this, the selector lived only inside `.studio-rail`, which collapses below
   * the document at container widths under 48rem (see `.studio-columns` in
   * `globals.css`) — on a laptop-width split with the chat panel open, that is most
   * screens. The control for "which version to generate" was reachable only by
   * scrolling past the whole resume, which from the user's side looked like it had
   * been removed. Lifting the state up does not change the rail explanation card below
   * (`LEVEL_GUIDE[level].summary/detail`), only which component owns the toggle itself.
   */
  level?: ElevationLevel;
  onLevelChange?: (level: ElevationLevel) => void;
};

export type ElevationLevel = "conservative" | "standard" | "elevated";

const LEVELS: ElevationLevel[] = ["conservative", "standard", "elevated"];

const TRACKS = [
  { id: "zh-CN" as const, label: "中文简历" },
  { id: "en-US" as const, label: "英文简历" },
  { id: "zh-en" as const, label: "双语对照" },
];

export function ElevatePreviewPanel({
  profileId,
  profileVersion,
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
  onGoToEvidence,
  rail,
  railFocusPath = null,
  className = "",
  level: controlledLevel,
  onLevelChange,
}: Props) {
  const [internalLevel, setInternalLevel] = useState<ElevationLevel>("standard");
  // Controlled when the caller passes `level` (sticky toolbar owns the choice);
  // falls back to local state so existing callers that do not pass it keep working.
  const level = controlledLevel ?? internalLevel;
  const setLevel = onLevelChange ?? setInternalLevel;
  const [locale, setLocale] = useState<ResumeTrack>("zh-CN");
  const [tracks, setTracks] = useState<Record<ResumeTrack, TrackState> | null>(null);
  const [localizeBusy, setLocalizeBusy] = useState(false);
  const [progress, setProgress] = useState<PreviewProgress>({});
  const [preview, setPreview] = useState<ElevatePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [awaitingFirstPreview, setAwaitingFirstPreview] = useState(() => autoLoad);
  const [loadStartedAt, setLoadStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [view, setView] = useState<"structured" | "preview" | "changes">("structured");
  const lastGenerateTickRef = useRef(generateTick);
  // Callback identity is not document identity. ResumeStudio passes an inline
  // callback that changes whenever busy state re-renders its parent.
  const busyCallbackRef = useRef(onBusyChange);
  busyCallbackRef.current = onBusyChange;
  const requestRef = useRef(0);
  const docRef = useRef<HTMLDivElement | null>(null);

  // Scroll the document column to the bullet the rail is asking about.
  //
  // Only the structured view carries `data-path`, so a focus arriving while the HTML
  // preview or the change list is showing switches back to it: silently doing nothing
  // would make the link look broken, and the structured view is the one that can answer
  // "where is this bullet".
  useEffect(() => {
    if (!railFocusPath) return;
    if (view !== "structured") {
      setView("structured");
      return;
    }
    const container = docRef.current;
    if (!container) return;
    // After the view has painted. The selector is CSS.escape'd because a profile path
    // contains brackets (`experiences[0].highlights[2]`), which are syntax here.
    const id = requestAnimationFrame(() => {
      const target = container.querySelector(
        `[data-path="${CSS.escape(railFocusPath)}"]`,
      );
      // `nearest` rather than `center`: the column is its own scroller now, and yanking
      // an already-visible bullet to the middle is motion the user did not ask for.
      target?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [railFocusPath, view]);

  useEffect(() => {
    requestRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setPreview(null);
    setTracks(null);
    setError(null);
    setLoadStartedAt(null);
    setAwaitingFirstPreview(autoLoad);
    setBusy(false);
    busyCallbackRef.current?.(false);
    return () => {
      requestRef.current += 1;
      abortRef.current?.abort();
    };
  }, [profileId, profileVersion, autoLoad]);

  async function refreshTracks(request: number) {
    try {
      const res = await listResumeTracks(profileId, level);
      if (request === requestRef.current) setTracks(res.tracks);
    } catch {
      if (request === requestRef.current) setTracks(null);
    }
  }

  async function loadPreview(options: { force?: boolean } = {}) {
    const request = ++requestRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), ELEVATE_PREVIEW_TIMEOUT_MS);
    setProgress({});
    setLoadStartedAt(Date.now());
    setBusy(true);
    busyCallbackRef.current?.(true);
    setError(null);
    try {
      // Track metadata is optional; it must not block the SSE generation stream.
      void refreshTracks(request);
      const data = await getElevatePreview(profileId, level, locale, jobId ?? undefined, {
        signal: controller.signal,
        force: options.force,
        onProgress: (event) => {
          if (request === requestRef.current) setProgress((state) => advancePreviewProgress(state, event));
        },
      });
      if (request !== requestRef.current) return;
      setPreview(data);
      onPreviewLoaded?.({
        draftId: data.draft.id,
        profileVersion: data.draft.profile_version,
        locale,
        level: (data.draft.elevation_level as ElevationLevel) || level,
      });
      void refreshTracks(request);
    } catch (err) {
      if (request === requestRef.current) setError(userFacingElevateError(err));
    } finally {
      window.clearTimeout(timeoutId);
      if (request === requestRef.current) {
        setBusy(false);
        busyCallbackRef.current?.(false);
        setAwaitingFirstPreview(false);
        setLoadStartedAt(null);
        abortRef.current = null;
      }
    }
  }

  useEffect(() => {
    // A counter is an edge-trigger, not a persisted command. On remount its
    // current value has already been consumed; only a NEW click forces writing.
    const regenerate = generateTick > lastGenerateTickRef.current;
    lastGenerateTickRef.current = generateTick;
    if (autoLoad || regenerate) void loadPreview({ force: regenerate });
    // Language/level/profile/job changes use server freshness checks, never force.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoLoad, profileId, profileVersion, jobId, locale, level, generateTick]);

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
  const previewGenerating =
    busy || (awaitingFirstPreview && !preview && !error);

  const draftBehindProfile =
    preview &&
    profileVersion != null &&
    preview.draft.profile_version < profileVersion;

  const lengthWarning = diag
    ? diag.estimated_pages < 0.6
      ? "偏薄：回到左侧待补充项，把成果写进要点比留白更能说明你做过什么。"
      : diag.estimated_pages > 2.2
        ? "偏长：招聘方首轮通常只扫第一页，把最强的经历和要点排到最前面。"
        : null
    : null;

  // The document column, assembled before the return so the layout below reads as
  // two columns rather than as one tree with a conditional in the middle.
  const documentColumn = (
    <div className="flex min-h-0 flex-col gap-3">
    {draftBehindProfile ? (
      <div
        className="notice notice-warn flex flex-wrap items-center justify-between gap-2 shrink-0"
        role="status"
      >
        <p className="text-xs leading-relaxed">
          档案已更新，当前预览仍基于旧版本。请点「重新生成」以同步最新确认内容。
        </p>
        <button
          type="button"
          onClick={() => void loadPreview({ force: true })}
          disabled={previewGenerating}
          className="btn btn-sm btn-secondary shrink-0"
        >
          重新生成
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

    {error && !previewGenerating ? (
      <div className="notice notice-danger flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" role="alert">
        <div className="min-w-0 text-left">
          <p className="text-sm font-medium">预览没有生成成功</p>
          <p className="mt-1 text-xs leading-relaxed opacity-90">{error}</p>
        </div>
        <button
          type="button"
          onClick={() => void loadPreview({ force: true })}
          className="btn btn-sm btn-secondary shrink-0"
        >
          重新生成
        </button>
      </div>
    ) : null}

    {!previewGenerating && typeof (preview?.draft.sections.generation as { warning?: unknown } | undefined)?.warning === "string" ? (
      <div className="notice notice-warning" role="status">
        {String((preview?.draft.sections.generation as { warning: string }).warning)}
      </div>
    ) : null}

    {view === "changes" ? (
      <ElevationChangesPanel
        draft={preview?.draft ?? null}
        progress={progress}
        generating={previewGenerating}
        loadStartedAt={loadStartedAt}
        onRetry={() => void loadPreview({ force: true })}
      />
    ) : view === "structured" ? (
      <ResumeStructuredPreview
        draft={preview?.draft ?? null}
        progress={progress}
        generating={previewGenerating}
        loadStartedAt={loadStartedAt}
        onRetry={() => void loadPreview({ force: true })}
        // The rail's focus wins while it is set: it is the more recent, more specific
        // intent, and it is the only one with a visible cause on screen.
        focusPath={railFocusPath ?? focusPath}
        onUiFocus={onUiFocus}
      />
    ) : previewGenerating ? (
      <ElevatePreviewGenerating
        progress={progress}
        startedAt={loadStartedAt}
        onRetry={() => void loadPreview({ force: true })}
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
        <div>
          <p className="text-sm font-medium text-ink-800">还没有优化稿</p>
          <p className="mt-1 text-xs text-ink-500">
            先在上方选好语言轨与优化强度，然后点顶部「生成预览」。
          </p>
        </div>
      </div>
    )}
    </div>
  );

  return (
    /*
     * Two columns, and the document owns one of them.
     *
     * Everything on this step used to stack in a single column with the controls, the
     * evidence prompts and the checklist above the resume — so each panel pushed the
     * document further down, and the first screen showed no resume at all. Collapsing
     * panels only delayed that; any panel the user opens re-creates it.
     *
     * The column rules live in `globals.css` as a container query rather than as
     * `xl:` utilities, because this pane is resizable and viewport width does not
     * describe the space it actually has. See the `.studio-columns` comment there.
     */
    <div className={`studio-columns ${className}`}>
      <div className="studio-columns-inner scroll-area">
      <div className="studio-doc scroll-area" ref={docRef}>
        {documentColumn}
      </div>

      <div className="studio-rail scroll-area">
      {rail}

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
                .then(() => loadPreview({ force: true }))
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
        /*
         * What got left out, and whether that matters.
         *
         * This used to lead with 「档案里有 22 条经历要点，这份稿只写进了 16 条」, which is
         * our bookkeeping, not the user's question: nobody knows what a 「经历要点」is, what
         * 22 counts, or what to do about the gap. It also printed each dropped line cut at
         * 20 characters, mid-word, which read as a rendering bug.
         *
         * So: name the content, not the count; quote on a phrase boundary; and state both
         * branches of the decision, because dropping a duplicate is a legitimate outcome
         * and a user who cannot tell the two apart treats every such notice as an error.
         * The dropped lines are listed in full rather than summarised, since recognising
         * one's own sentence is the whole act being asked for.
         */
        <div className="shrink-0 notice notice-warn" role="status">
          <div className="min-w-0">
            <p className="text-xs font-medium">
              {coverage.projects_missing
                ? "项目经历整节没有写进来"
                : `有 ${coverage.dropped.length} 段经历没写进这份简历`}
            </p>
            {coverage.projects_missing ? (
              <p className="mt-1 text-xs leading-relaxed opacity-90">
                这通常是生成异常，不是取舍。重新生成一次即可。
              </p>
            ) : (
              <>
                <ul className="mt-1.5 space-y-1">
                  {coverage.dropped.slice(0, 3).map((d) => (
                    <li key={`${d.where}-${d.text}`} className="text-xs leading-relaxed">
                      <span className="opacity-70">{d.where}：</span>
                      <span className="opacity-95">{excerpt(d.text, 32)}</span>
                    </li>
                  ))}
                </ul>
                {coverage.dropped.length > 3 ? (
                  <p className="mt-1 text-micro opacity-75">
                    另有 {coverage.dropped.length - 3} 段未列出
                  </p>
                ) : null}
                <p className="mt-1.5 text-xs leading-relaxed opacity-90">
                  如果其中有你想让面试官看到的内容，重新生成一次，或在档案里把它排到更前面；
                  如果它和别的要点说的是同一件事，可以不用管。
                </p>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => void loadPreview({ force: true })}
            disabled={previewGenerating}
            className="btn btn-sm btn-secondary shrink-0"
          >
            {previewGenerating ? "生成中…" : "重新生成"}
          </button>
        </div>
      ) : null}

      {/* The document-level report: the bar for this role family, and which parts of it
          this draft clears. Placed above the sentence-level technique summary because it
          is the larger claim — reading "4 处强化手段" before knowing whether the document
          is structurally sound is what made the whole step read as wording polish. */}
      <BlueprintPanel
        blueprint={preview?.blueprint ?? null}
        structure={preview?.structure ?? null}
        onGoToEvidence={onGoToEvidence}
        onGoToChanges={() => setView("changes")}
      />

      {/* What the draft did, at the sentence level. */}
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
                内容检查已在本页自动进行。下一步复用检查结果，选择 PDF / Word / 网页版下载。
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
      </div>
    </div>
  );
}
