"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getIntakePlan,
  INTAKE_MODE_COPY,
  splitIntakeAnswer,
  submitIntakeAnswers,
  type IntakeAnswered,
  type IntakeAppliedWrite,
  type IntakePlan,
  type IntakeQuestion,
  type IntakeSplitSegment,
} from "@/lib/api/intake";
import { userFacingApiError } from "@/lib/api/user-error";
import { useSkeletonInsert } from "@/lib/hooks/useSkeletonInsert";

import { MetricChips } from "../resume/MetricChips";

type Props = {
  profileId: string;
  /** Called after answers land so the caller can reload the profile it is displaying. */
  onAnswered?: (result: { stored: number; appliedPaths: string[] }) => void;
  /** Open on mount — used when the user arrives here from "我没有简历". */
  defaultOpen?: boolean;
};

/**
 * Build a profile by answering questions, for the case a file upload cannot serve:
 * no resume at all, or one so out of date that what it contains is someone else's
 * career.
 *
 * Why this is a deterministic interview and not a chat
 * ----------------------------------------------------
 * A free-form conversation with a model has no reason to stop, repeats itself in
 * different words, and drifts into questions a resume has no use for. The questions
 * here are computed from what the profile is missing, so the interview provably
 * terminates, never asks the same thing twice, and — because question ids are a
 * function of the profile rather than of a session — resumes exactly where it stopped
 * after the tab is closed.
 *
 * No model is in this path. Answers are stored as the user typed them; turning them
 * into resume prose happens later at generation time, where the user can see and reject
 * the result. The profile also stays in `draft`, so the normal confirmation step still
 * applies: nothing here bypasses the review the user does after a file upload.
 */
export function ProfileIntakePanel({ profileId, onAnswered, defaultOpen = false }: Props) {
  const [plan, setPlan] = useState<IntakePlan | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<IntakeAppliedWrite[]>([]);
  const [expanded, setExpanded] = useState(defaultOpen);
  // Which answered question is open for editing. One at a time: a list of simultaneously
  // editable fields is the form this interview exists to avoid.
  const [revising, setRevising] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  // A dictated answer broken into separate points, pending the user's confirmation.
  // Keyed by question id: only one answer is ever being split, but keying it means a
  // stale split cannot attach itself to the next question.
  const [split, setSplit] = useState<{ questionId: string; segments: IntakeSplitSegment[] } | null>(
    null,
  );
  const [splitting, setSplitting] = useState(false);
  // Clicking a sentence shape inserts it and puts the caret on the blank. Same hook
  // as the evidence panel: one user intent, one behaviour.
  const { inputs, insert } = useSkeletonInsert(setDrafts);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPlan(await getIntakePlan(profileId, { limit: 6 }));
    } catch (err) {
      setError(userFacingApiError(err, "无法加载建档问题"));
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    setDrafts({});
    setApplied([]);
    setRevising(null);
    setSplit(null);
    void load();
  }, [load]);

  const filled = plan
    ? plan.questions
        .map((q) => ({ q, text: (drafts[q.id] ?? "").trim() }))
        .filter((x) => x.text.length > 0)
    : [];

  const submit = useCallback(
    async (answers: { question_id: string; target_path: string; question: string; answer: string }[]) => {
      if (answers.length === 0) return;
      setSaving(true);
      setError(null);
      try {
        const res = await submitIntakeAnswers(profileId, answers);
        setPlan(res.plan);
        setApplied(res.applied);
        setDrafts({});
        setRevising(null);
        setSplit(null);
        onAnswered?.({ stored: res.stored, appliedPaths: res.applied_paths });
      } catch (err) {
        setError(userFacingApiError(err, "保存失败"));
      } finally {
        setSaving(false);
      }
    },
    [profileId, onAnswered],
  );

  async function handleSave() {
    if (!plan) return;
    await submit(
      filled.map(({ q, text }) => ({
        question_id: q.id,
        target_path: q.target_path,
        question: q.question,
        answer: text,
      })),
    );
  }

  /**
   * Offer to break one dictated answer into separate bullets.
   *
   * People answer 「最值得写的一件事」 with five things in one breath, and before this the
   * whole paragraph became a single 300-character bullet — the four strongest items
   * buried inside the first. The split happens on the server by punctuation alone, with
   * no model in the path, so it cannot reword or drop anything; what it can get wrong is
   * *where* a boundary falls, which is why this is a preview and not a write.
   */
  async function handleSplit(question: IntakeQuestion) {
    const answer = (drafts[question.id] ?? "").trim();
    if (!answer) return;
    setSplitting(true);
    setError(null);
    try {
      const res = await splitIntakeAnswer(profileId, {
        question_id: question.id,
        target_path: question.target_path,
        answer,
      });
      if (!res.split) {
        setError("这段话读起来是一件事，不用拆。直接保存就行。");
        setSplit(null);
        return;
      }
      setSplit({ questionId: question.id, segments: res.segments });
    } catch (err) {
      setError(userFacingApiError(err, "拆分失败"));
    } finally {
      setSplitting(false);
    }
  }

  /** Submit the confirmed segments, each answering the slot the server assigned it. */
  async function handleSplitConfirm(segments: IntakeSplitSegment[]) {
    const kept = segments.filter((seg) => seg.text.trim().length > 0);
    if (kept.length === 0) return;
    const asked = new Map(plan?.questions.map((q) => [q.id, q.question]) ?? []);
    await submit(
      kept.map((seg) => ({
        question_id: seg.question_id,
        target_path: seg.target_path,
        // The slot's own question when the plan asked for it; otherwise the label, so a
        // stored answer always says what it was an answer to.
        question: asked.get(seg.question_id) ?? seg.label,
        answer: seg.text.trim(),
      })),
    );
  }

  /**
   * Resubmit one already-answered question. Goes through the same endpoint as a fresh
   * answer: the server keys intake answers by question id, so this replaces the stored
   * answer and rewrites the same profile field rather than adding a second one.
   */
  async function handleRevise(item: IntakeAnswered, text: string) {
    await submit([
      {
        question_id: item.question_id,
        target_path: item.target_path,
        question: item.question,
        answer: text,
      },
    ]);
  }

  if (loading && !plan) {
    return (
      <div className="card card-pad">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton mt-3 h-20 w-full" />
      </div>
    );
  }

  if (!plan) {
    return error ? (
      <div className="notice notice-danger">
        <span className="text-xs">{error}</span>
      </div>
    ) : null;
  }

  const copy = INTAKE_MODE_COPY[plan.mode];
  const remaining = plan.questions.filter((q) => q.required).length;
  // A complete profile with nothing required left has no reason to take up this much
  // space on the review step; the entry point stays, collapsed.
  const quiet = plan.mode === "complete" && remaining === 0;

  return (
    <section className="card card-pad" aria-labelledby="intake-heading">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-start justify-between gap-3 text-left"
      >
        <div className="min-w-0">
          <h3
            id="intake-heading"
            className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900"
          >
            {quiet ? "用对话补充更多材料" : copy.title}
            {plan.answered_count > 0 ? (
              <span className="badge badge-neutral">已回答 {plan.answered_count} 条</span>
            ) : null}
            {!quiet && remaining > 0 ? (
              <span className="badge badge-brand">还有 {remaining} 个必答</span>
            ) : null}
          </h3>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            {quiet ? "档案已经可以生成简历，继续回答会让内容更厚。" : copy.detail}
          </p>
        </div>
        <svg
          viewBox="0 0 20 20"
          aria-hidden="true"
          fill="currentColor"
          className={`mt-0.5 h-4 w-4 shrink-0 text-ink-500 transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        >
          <path d="M5.5 7.5 10 12l4.5-4.5H5.5Z" />
        </svg>
      </button>

      {/* Progress by stage, and what still blocks generation. Visible when collapsed too:
          it is the answer to "我还差什么才能生成简历", which is the question a half-built
          profile raises. */}
      {!quiet ? (
        <div className="mt-3 border-t border-surface-border pt-3">
          <ol className="flex flex-wrap gap-1.5">
            {plan.stages.map((stage) => (
              <li
                key={stage.id}
                className={`badge ${stage.done ? "badge-success" : "badge-neutral"}`}
              >
                {stage.label}
                {stage.done ? null : (
                  <span className="opacity-70">还有 {stage.remaining}</span>
                )}
              </li>
            ))}
          </ol>
          {plan.can_generate ? (
            <p className="mt-2.5 text-xs leading-relaxed text-success-700">
              材料已经够生成一份简历了。确认档案后就能进入优化预览。
            </p>
          ) : (
            <p className="mt-2.5 text-xs leading-relaxed text-warn-900">
              还不能生成：{plan.blocking.join("；")}。
            </p>
          )}
        </div>
      ) : null}

      {/* What was written, in the user's words and with the text we stored. A path-only
          confirmation ("已写入 experiences[0].scope") cannot be checked against what the
          user meant to say, which is the only reason to show a write at all. */}
      {applied.length > 0 ? (
        <div className="notice notice-success mt-3" role="status">
          <div className="min-w-0">
            <p className="text-xs font-medium">
              已写入档案 {applied.length} 处，仍是草稿，可以继续修改。
            </p>
            <ul className="mt-2 space-y-1.5">
              {applied.map((write) => (
                <li key={write.path} className="text-xs leading-relaxed">
                  <span className="font-medium">{write.label}</span>
                  <span className="text-ink-700">：{write.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="notice notice-danger mt-3">
          <span className="text-xs">{error}</span>
        </div>
      ) : null}

      {expanded ? (
        <>
          {plan.questions.length === 0 ? (
            <p className="mt-3 text-xs leading-relaxed text-ink-500">
              没有要问的了。已回答 {plan.answered_count} 条，可以在下方回看或修改，
              也可以直接核对并确认档案。
            </p>
          ) : (
            <>
              <ul className="mt-4 space-y-3">
                {plan.questions.map((q) => (
                  <li key={q.id} className="card-sunken p-3.5">
                    <IntakeQuestionField
                      question={q}
                      value={drafts[q.id] ?? ""}
                      onChange={(text) => setDrafts((prev) => ({ ...prev, [q.id]: text }))}
                      onPickShape={(shape) => insert(q.id, shape)}
                      inputRef={(el) => {
                        inputs.current[q.id] = el;
                      }}
                      onSplit={() => void handleSplit(q)}
                      splitting={splitting}
                    />
                    {split?.questionId === q.id ? (
                      <SplitConfirm
                        segments={split.segments}
                        saving={saving}
                        onCancel={() => setSplit(null)}
                        onConfirm={(segments) => void handleSplitConfirm(segments)}
                      />
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-ink-500">
                  按你记得的写就行，留空的不会写进档案。
                </p>
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving || filled.length === 0}
                  className="btn btn-md btn-primary"
                >
                  {saving ? "保存中…" : `保存 ${filled.length} 条回答`}
                </button>
              </div>
            </>
          )}

          {/* Answers already given, so the interview is not write-once. Collapsed by
              default: the next question matters more than the last one, but "我刚才那条
              写错了" must have an answer other than hunting through the profile editor. */}
          {plan.answered.length > 0 ? (
            <div className="mt-4 border-t border-surface-border pt-3">
              <button
                type="button"
                onClick={() => setReviewOpen((v) => !v)}
                aria-expanded={reviewOpen}
                className="flex w-full items-center justify-between gap-2 text-left"
              >
                <span className="text-xs font-medium text-ink-800">
                  已回答的 {plan.answered.length} 条，可以回看或修改
                </span>
                <svg
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                  fill="currentColor"
                  className={`h-4 w-4 shrink-0 text-ink-500 transition-transform ${
                    reviewOpen ? "rotate-180" : ""
                  }`}
                >
                  <path d="M5.5 7.5 10 12l4.5-4.5H5.5Z" />
                </svg>
              </button>
              {reviewOpen ? (
                <ul className="mt-3 space-y-2.5">
                  {plan.answered.map((item) => (
                    <li key={item.question_id} className="card-sunken p-3.5">
                      <AnsweredRow
                        item={item}
                        editing={revising === item.question_id}
                        saving={saving}
                        onEdit={() => setRevising(item.question_id)}
                        onCancel={() => setRevising(null)}
                        onSave={(text) => void handleRevise(item, text)}
                      />
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function IntakeQuestionField({
  question,
  value,
  onChange,
  onPickShape,
  inputRef,
  onSplit,
  splitting,
}: {
  question: IntakeQuestion;
  value: string;
  onChange: (text: string) => void;
  onPickShape: (shape: string) => void;
  /** Set only for `long_text` questions, which are the ones that can carry shapes. */
  inputRef: (el: HTMLTextAreaElement | null) => void;
  onSplit: () => void;
  splitting: boolean;
}) {
  const inputId = `intake-${question.id}`;
  // Offered once the answer is long enough to plausibly hold more than one point.
  // Below that the button is noise, and pressing it would only return "不用拆".
  const canSplit = question.input_kind === "long_text" && value.trim().length >= 40;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {question.required ? (
          <span className="badge badge-warn">必答</span>
        ) : (
          <span className="badge badge-neutral">可跳过</span>
        )}
        {/* Where the answer will land, in the user's words. `target_path` is internal. */}
        <span className="text-micro text-ink-500">写入：{question.label || "档案"}</span>
      </div>
      <label htmlFor={inputId} className="mt-2 block text-sm leading-relaxed text-ink-800">
        {question.question}
      </label>
      <p className="mt-1 text-xs leading-relaxed text-ink-500">{question.rationale}</p>
      {/* Shapes replace the examples line when they exist: a list of metric nouns and a
          list of clickable skeletons are the same hint twice, and the clickable one is
          strictly more useful. */}
      {question.metrics.length > 0 ? (
        <MetricChips
          metrics={question.metrics}
          onPick={onPickShape}
          hint="可以点一个句式填进去，数字由你填——我们不会替你估。"
        />
      ) : question.examples.length > 0 ? (
        <p className="mt-1.5 text-xs leading-relaxed text-ink-500">
          例如：{question.examples.join(" / ")}
        </p>
      ) : null}
      {question.input_kind === "long_text" ? (
        <textarea
          id={inputId}
          ref={inputRef}
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="想到什么写什么，一次说好几件事也没关系——写完可以拆成几条"
          className="field mt-2.5 resize-y"
        />
      ) : (
        <input
          id={inputId}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={question.examples[0] ?? ""}
          className="field mt-2.5"
        />
      )}
      {canSplit ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onSplit}
            disabled={splitting}
            className="btn btn-sm btn-secondary"
          >
            {splitting ? "拆分中…" : "这段话里有好几件事，帮我拆开"}
          </button>
          <span className="text-micro text-ink-500">
            按你写的标点拆，不改一个字，拆完你再确认。
          </span>
        </div>
      ) : null}
    </div>
  );
}


/**
 * The proposed split, before anything is written.
 *
 * Editable, because the only thing a punctuation-based split can get wrong is where a
 * boundary falls — and the user is the only one who knows whether 「后来又做了灰度发布」
 * is its own achievement or the tail of the previous one. Deleting a segment's text drops
 * it, which is how two over-eager segments get merged: paste one into the other.
 */
function SplitConfirm({
  segments,
  saving,
  onCancel,
  onConfirm,
}: {
  segments: IntakeSplitSegment[];
  saving: boolean;
  onCancel: () => void;
  onConfirm: (segments: IntakeSplitSegment[]) => void;
}) {
  const [edited, setEdited] = useState(segments);

  // Re-sync when a fresh split arrives for the same question.
  useEffect(() => {
    setEdited(segments);
  }, [segments]);

  const kept = edited.filter((seg) => seg.text.trim().length > 0);

  return (
    <div className="mt-3 rounded-xl border border-brand-200 bg-brand-50 p-3.5">
      <p className="text-xs font-medium text-ink-900">
        拆成了 {segments.length} 条，每条会写到下面这个位置：
      </p>
      <ul className="mt-2.5 space-y-2.5">
        {edited.map((seg, index) => {
          const fieldId = `intake-split-${seg.question_id}`;
          return (
            <li key={seg.question_id}>
              <label htmlFor={fieldId} className="text-micro text-ink-500">
                {seg.label}
              </label>
              <textarea
                id={fieldId}
                rows={2}
                value={seg.text}
                onChange={(e) =>
                  setEdited((prev) =>
                    prev.map((item, i) => (i === index ? { ...item, text: e.target.value } : item)),
                  )
                }
                className="field mt-1 resize-y"
              />
            </li>
          );
        })}
      </ul>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-micro text-ink-500">
          清空某一条就是不要它；想合并两条，把文字挪到一起。
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={onCancel} className="btn btn-sm btn-ghost">
            还是当一条
          </button>
          <button
            type="button"
            onClick={() => onConfirm(kept)}
            disabled={saving || kept.length === 0}
            className="btn btn-sm btn-primary"
          >
            {saving ? "保存中…" : `保存这 ${kept.length} 条`}
          </button>
        </div>
      </div>
    </div>
  );
}


/**
 * One already-answered question: what we stored, and a way to change it.
 *
 * Revision goes back through the intake endpoint rather than the profile editor. The
 * editor can of course edit the same field, but a user who just typed an answer here is
 * not holding a map from 「你负责多大的范围」 to 「经历 1 的负责范围输入框」 — making them
 * find it is what made the panel feel one-way.
 */
function AnsweredRow({
  item,
  editing,
  saving,
  onEdit,
  onCancel,
  onSave,
}: {
  item: IntakeAnswered;
  editing: boolean;
  saving: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: (text: string) => void;
}) {
  const [text, setText] = useState(item.answer);
  const inputId = `intake-revise-${item.question_id}`;

  // Reset the field when the stored answer changes underneath us, e.g. after a save.
  useEffect(() => {
    setText(item.answer);
  }, [item.answer]);

  const trimmed = text.trim();
  const unchanged = trimmed === item.answer.trim();

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-micro text-ink-500">{item.label || item.target_path}</p>
          <p className="mt-1 text-xs leading-relaxed text-ink-700">{item.question}</p>
        </div>
        {editing ? null : (
          <button type="button" onClick={onEdit} className="btn btn-sm btn-secondary shrink-0">
            修改
          </button>
        )}
      </div>

      {editing ? (
        <>
          <label htmlFor={inputId} className="sr-only">
            修改回答：{item.question}
          </label>
          <textarea
            id={inputId}
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="field mt-2.5 resize-y"
          />
          <div className="mt-2.5 flex flex-wrap items-center justify-end gap-2">
            <button type="button" onClick={onCancel} className="btn btn-sm btn-ghost">
              取消
            </button>
            <button
              type="button"
              onClick={() => onSave(trimmed)}
              disabled={saving || trimmed.length === 0 || unchanged}
              className="btn btn-sm btn-primary"
            >
              {saving ? "保存中…" : "保存修改"}
            </button>
          </div>
        </>
      ) : (
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-900">
          {item.answer}
        </p>
      )}
    </div>
  );
}
