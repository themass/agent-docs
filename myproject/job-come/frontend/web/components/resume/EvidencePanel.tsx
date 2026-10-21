"use client";

import { useCallback, useEffect, useState } from "react";

import {
  GAP_KIND_LABELS,
  listEvidenceGaps,
  submitEvidenceAnswers,
  type EvidenceGap,
  type EvidenceGapsResponse,
} from "@/lib/api/evidence";
import { userFacingApiError } from "@/lib/api/user-error";
import { useSkeletonInsert } from "@/lib/hooks/useSkeletonInsert";

import { MetricChips } from "./MetricChips";

type Props = {
  profileId: string;
  jobId?: string | null;
  /** Called after answers are saved so the caller can refresh the profile/draft. */
  onAnswersSaved?: (stored: number) => void;
  /**
   * Bumped by the caller when the role family changes elsewhere. The questions are
   * derived per family, so a stale list would ask a designer for QPS figures.
   */
  reloadTick?: number;
  /**
   * Bumped by the caller to ask this panel to open — the blueprint checklist links here
   * when a requirement is unmet. A counter rather than a controlled `expanded` prop so
   * the panel keeps owning its own state: the parent is making a request, not dictating
   * a value, and the user can still close it afterwards.
   */
  openTick?: number;
  /**
   * Which bullet the user is currently working on, reported up so the document column can
   * scroll to it. The two columns hold different content and cannot be made to line up,
   * so this link is what the side-by-side layout actually promises.
   *
   * `field_path` is already the same path the structured preview puts in `data-path`, so
   * no mapping is needed — and nothing new has to be kept in sync for it to stay true.
   */
  onFocusPath?: (path: string | null) => void;
};

/**
 * Collect the facts that would make this resume provable.
 *
 * The honest way to make a resume look stronger is not to embellish it — an invented
 * metric passes the screen and then collapses under questioning, and the cost lands on
 * the candidate. Most resumes are weak because the strongest evidence was never written
 * down: the user knows the number, nobody ever asked. So this panel asks, one bullet at
 * a time, and stores the user's own words as source facts the writer may then use.
 */
export function EvidencePanel({
  profileId,
  jobId = null,
  onAnswersSaved,
  reloadTick = 0,
  openTick = 0,
  onFocusPath,
}: Props) {
  const [data, setData] = useState<EvidenceGapsResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  // Collapsed by default. Three advisory panels stacked above the document pushed the
  // resume itself below the fold, and a user who cannot see their resume reads the
  // screen as "I do not know what I am supposed to do here". The count is enough to
  // decide whether to open it; the questions are a task, not a status.
  const [expanded, setExpanded] = useState(false);
  // Clicking a sentence shape inserts it and puts the caret on the blank. Shared with
  // the intake panel: the caret placement has a commit-ordering subtlety that must not
  // exist in two copies.
  const { inputs, insert: applySkeleton } = useSkeletonInsert(setDrafts);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listEvidenceGaps(profileId, { jobId, limit: 12 });
      setData(res);
    } catch (err) {
      setError(userFacingApiError(err, "无法加载待补充项"));
    } finally {
      setLoading(false);
    }
  }, [profileId, jobId]);

  useEffect(() => {
    setDrafts({});
    setSavedCount(0);
    void load();
  }, [load, reloadTick]);

  useEffect(() => {
    if (openTick > 0) setExpanded(true);
  }, [openTick]);

  // A collapsed panel is not working on anything, so a stale highlight left on the
  // document would point at a question the user can no longer see.
  useEffect(() => {
    if (!expanded) onFocusPath?.(null);
  }, [expanded, onFocusPath]);

  function keyOf(gap: EvidenceGap): string {
    return `${gap.field_path}::${gap.question}`;
  }

  const filled = Object.entries(drafts).filter(([, v]) => v.trim().length > 0);

  async function handleSave() {
    if (!data || filled.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const byKey = new Map(data.gaps.map((g) => [keyOf(g), g]));
      const answers = filled.flatMap(([key, value]) => {
        const gap = byKey.get(key);
        if (!gap) return [];
        return [
          {
            field_path: gap.field_path,
            question: gap.question,
            answer: value.trim(),
            kind: gap.kind,
          },
        ];
      });
      const res = await submitEvidenceAnswers(profileId, answers);
      setSavedCount((n) => n + res.stored);
      setDrafts({});
      setExpanded(false);
      onAnswersSaved?.(res.stored);
      await load();
    } catch (err) {
      setError(userFacingApiError(err, "保存失败"));
    } finally {
      setSaving(false);
    }
  }

  if (loading && !data) {
    return (
      <div className="card card-pad">
        <div className="skeleton h-4 w-48" />
        <div className="skeleton mt-3 h-16 w-full" />
      </div>
    );
  }

  if (!data) {
    return error ? (
      <div className="notice notice-danger">
        <span className="text-xs">{error}</span>
      </div>
    ) : null;
  }

  return (
    <section className="card card-pad" aria-labelledby="evidence-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 id="evidence-heading" className="text-sm font-semibold text-ink-900">
            补充证据，让要点站得住
          </h3>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            这些问题针对的是「本该有成果却没写出来」的要点。你填的内容会作为真实事实使用，
            写作时直接用在对应要点上。我们不会替你编造任何数字。
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="badge badge-neutral">按{data.role_label}评判</span>
          {data.gaps.length > 0 ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="btn btn-sm btn-secondary"
              aria-expanded={expanded}
            >
              {expanded ? "收起" : `回答 ${data.gaps.length} 个问题`}
            </button>
          ) : null}
        </div>
      </div>

      {data.quantification_optional ? (
        <p className="mt-3 text-xs leading-relaxed text-ink-500">
          {data.role_label}的成果常常没有数字。说清解决了什么问题、避免了什么风险、支撑了什么决策，
          同样是一条完整的要点。
        </p>
      ) : null}

      {savedCount > 0 ? (
        <div className="notice notice-success mt-3">
          <span className="text-xs">
            已保存 {savedCount} 条补充。重新生成优化稿后即会用上。
          </span>
        </div>
      ) : null}

      {error ? (
        <div className="notice notice-danger mt-3">
          <span className="text-xs">{error}</span>
        </div>
      ) : null}

      {data.gaps.length === 0 ? (
        <div className="notice notice-success mt-3">
          <span className="text-xs">
            {data.answered_count > 0
              ? `没有待补充项了，已累计补充 ${data.answered_count} 条。`
              : "没有发现明显缺少成果的要点，可以直接去优化预览。"}
          </span>
        </div>
      ) : !expanded ? (
        /* Collapsed: name what is waiting, so opening it is an informed choice. */
        <p className="mt-3 text-xs leading-relaxed text-ink-500">
          有 {data.gaps.length} 条要点缺少可写的成果
          {data.answered_count > 0 ? `，已补充 ${data.answered_count} 条` : ""}
          。补上之后重新生成，简历会实质变厚。
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {data.gaps.map((gap) => {
            const key = keyOf(gap);
            return (
              <li
                key={key}
                className="card-sunken p-3.5"
                // Focus rather than click: this fires for keyboard users reaching the
                // textarea by Tab as well as for a pointer, and both mean the same thing
                // — "this is the bullet I am working on".
                onFocus={() => onFocusPath?.(gap.field_path)}
                onMouseEnter={() => onFocusPath?.(gap.field_path)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge badge-warn">
                    {GAP_KIND_LABELS[gap.kind] ?? "待补充"}
                  </span>
                  <span className="min-w-0 truncate text-xs text-ink-500" title={gap.source_text}>
                    {gap.source_text}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-ink-800">{gap.question}</p>
                {/* The chips replace this line when they exist: a list of metric nouns
                    and a list of clickable skeletons are the same hint twice, and the
                    clickable one is strictly more useful. */}
                {gap.metrics?.length ? (
                  <MetricChips
                    metrics={gap.metrics}
                    onPick={(skeleton) => applySkeleton(key, skeleton)}
                  />
                ) : gap.examples.length > 0 ? (
                  <p className="mt-1.5 text-micro leading-relaxed text-ink-500">
                    可以从这些角度想：{gap.examples.join(" / ")}
                  </p>
                ) : null}
                <label className="mt-2.5 block">
                  <span className="sr-only">{gap.question}</span>
                  <textarea
                    ref={(el) => {
                      inputs.current[key] = el;
                    }}
                    rows={2}
                    value={drafts[key] ?? ""}
                    onChange={(e) =>
                      setDrafts((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                    placeholder="用一句话写下你记得的事实，不确定就留空"
                    className="field resize-y text-xs"
                  />
                </label>
              </li>
            );
          })}
        </ul>
      )}

      {data.gaps.length > 0 && expanded ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-ink-500">
            可以只回答你有把握的几条，留空的不会写进简历。
          </p>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || filled.length === 0}
            className="btn btn-md btn-primary"
          >
            {saving ? "保存中…" : `保存 ${filled.length} 条补充`}
          </button>
        </div>
      ) : null}
    </section>
  );
}
