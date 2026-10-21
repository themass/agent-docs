"use client";

import { useCallback, useEffect, useState } from "react";

import { Select } from "@/components/ui/Select";
import { userFacingApiError } from "@/lib/api/user-error";
import {
  getWritingOptions,
  updateWritingOptions,
  type WritingOptions,
} from "@/lib/api/writing-options";

type Props = {
  profileId: string;
  jobId?: string | null;
  /** Called after a setting changes so the caller can re-generate the draft. */
  onChanged?: (options: WritingOptions) => void;
  /**
   * True while the preview panel is (re)loading, including the regeneration this
   * panel's own save just triggered.
   *
   * Saving a setting here is a round trip to the profile, not to the draft — the
   * resume itself only catches up once the caller reloads the preview, which costs
   * a real model call. Without this, a changed angle looked like a no-op for however
   * long that call takes, which is exactly the complaint this panel exists to fix.
   */
  regenerating?: boolean;
};

/**
 * The two decisions that shape how a resume is written, made explicit.
 *
 * Before this panel both were made implicitly: the role family was inferred from a job
 * title, and the framing angle was whatever the model happened to pick. Users correctly
 * read that as "one opaque optimize button" — there was no way to say "write me as the
 * person who owned the decisions" rather than "the person who hit the numbers", even
 * though both are true of the same work.
 *
 * What a change here can and cannot do is a hard product boundary, and the copy says so:
 * angles reorder and re-word facts that are already in the profile. They never add one.
 * Making the resume *fuller* is a different mechanism — answering the evidence questions
 * below, which supplies real material.
 */
export function WritingOptionsPanel({
  profileId,
  jobId = null,
  onChanged,
  regenerating = false,
}: Props) {
  const [data, setData] = useState<WritingOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  // Latches true on a successful save and only clears once the caller reports the
  // regeneration it triggered has finished -- `saving` alone only covers the quick
  // profile-write request, not the slower reload that follows it.
  const [awaitingRegen, setAwaitingRegen] = useState(false);

  useEffect(() => {
    if (!regenerating) setAwaitingRegen(false);
  }, [regenerating]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getWritingOptions(profileId, { jobId }));
    } catch (err) {
      setError(userFacingApiError(err, "无法加载写作偏好"));
    } finally {
      setLoading(false);
    }
  }, [profileId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(body: { roleFamily?: string; framingEmphases?: string[] }) {
    setSaving(true);
    setError(null);
    try {
      const res = await updateWritingOptions(profileId, body, { jobId });
      setData(res);
      setAwaitingRegen(true);
      onChanged?.(res);
    } catch (err) {
      setError(userFacingApiError(err, "保存失败"));
    } finally {
      setSaving(false);
    }
  }

  function toggleAngle(id: string) {
    if (!data) return;
    const current = data.framing_emphases;
    if (current.includes(id)) {
      // Deselecting the last one restores the role default rather than leaving the
      // document with no angle at all.
      void save({ framingEmphases: current.filter((x) => x !== id) });
      return;
    }
    // At the cap, the newest pick replaces the oldest so the control never dead-ends.
    const next =
      current.length >= data.max_emphases
        ? [...current.slice(1), id]
        : [...current, id];
    void save({ framingEmphases: next });
  }

  if (loading && !data) {
    return (
      <div className="card card-pad">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton mt-3 h-10 w-full" />
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

  const activeLabels = data.presets
    .filter((p) => data.framing_emphases.includes(p.id))
    .map((p) => p.label);

  // `general` is what inference returns when it recognised nothing — not a verdict that
  // the role is generic. Left silent it reads as a decision, and the user gets the
  // neutral playbook for a role that has a specific one ("技术高P（底座方向）" matches no
  // alias and lands here). Inference deliberately does not guess, so the prompt to
  // choose has to be explicit.
  const needsFamily = data.role_family === "general" && !data.role_family_explicit;

  return (
    <section className="card card-pad" aria-labelledby="writing-options-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 id="writing-options-heading" className="text-sm font-semibold text-ink-900">
            简历往哪个方向写
          </h3>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            同一段经历可以有好几种真实写法——换一个岗位类型或主打角度，要点的顺序和说法会
            重新生成，但不会新增任何事实。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="btn btn-sm btn-primary shrink-0"
          aria-expanded={expanded}
        >
          {expanded ? "收起" : "换一个方向"}
        </button>
      </div>

      {needsFamily ? (
        <div className="notice notice-warn mt-3" role="status">
          <div className="min-w-0">
            <p className="text-xs font-medium">没认出你的岗位类型，正在按通用标准写</p>
            <p className="mt-1 text-xs leading-relaxed opacity-90">
              不同岗位的简历标准不一样：什么算成果、招聘方先看哪一节、每段要交代什么范围，
              都不同。选准岗位后，整份简历会按那一类的标准重写和检查。
            </p>
          </div>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="btn btn-sm btn-secondary shrink-0"
          >
            选择岗位类型
          </button>
        </div>
      ) : null}

      {/* Collapsed: one line stating what is in force and where it came from. */}
      {!expanded ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className={`badge ${needsFamily ? "badge-warn" : "badge-neutral"}`}>
            {data.role_label}
          </span>
          {activeLabels.map((label) => (
            <span key={label} className="badge badge-brand">
              {label}
            </span>
          ))}
          {awaitingRegen ? (
            <span className="inline-flex items-center gap-1 text-micro text-brand-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" aria-hidden />
              正在按新设置重新生成…
            </span>
          ) : !data.framing_explicit || !data.role_family_explicit ? (
            <span className="text-micro text-ink-500">按岗位推荐，可自行调整</span>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {awaitingRegen ? (
            <div className="notice notice-info" role="status">
              <span className="inline-flex items-center gap-1.5 text-xs">
                <span
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500"
                  aria-hidden
                />
                已保存，正在按新设置重新生成简历预览…
              </span>
            </div>
          ) : null}
          <div>
            <label className="label-meta" htmlFor="writing-role-family">
              这份简历按哪类岗位的标准写
            </label>
            <p className="mt-1 text-xs leading-relaxed text-ink-500">
              决定什么算「成果」、招聘方先看哪一节。选错会让整份简历写给错误的读者。
            </p>
            <Select
              id="writing-role-family"
              value={data.role_family}
              onChange={(e) => void save({ roleFamily: e.target.value })}
              disabled={saving}
              className="mt-2 w-full"
              selectClassName="text-sm"
            >
              {data.families.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </Select>
            {data.quantification_optional ? (
              <p className="mt-2 text-xs leading-relaxed text-ink-500">
                {data.role_label}的成果常常没有数字。写清解决了什么问题、避免了什么风险，
                同样是一条完整的要点。
              </p>
            ) : null}
          </div>

          <div>
            <span className="label-meta">主打角度</span>
            <p className="mt-1 text-xs leading-relaxed text-ink-500">
              最多选 {data.max_emphases} 个，第一个为主。选满后再选会替换最早选的那个。
              选好之后简历会按这个角度重新生成。
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {data.presets.map((preset) => {
                const active = data.framing_emphases.includes(preset.id);
                const primary = data.framing_emphases[0] === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => toggleAngle(preset.id)}
                    disabled={saving}
                    aria-pressed={active}
                    className={[
                      "rounded-lg border px-3 py-2.5 text-left transition",
                      "disabled:pointer-events-none disabled:opacity-60",
                      active
                        ? "border-brand-400 bg-brand-50 ring-1 ring-inset ring-brand-100"
                        : "border-surface-border bg-surface hover:border-surface-border-strong",
                    ].join(" ")}
                  >
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span
                        className={[
                          "text-xs font-semibold",
                          active ? "text-brand-800" : "text-ink-900",
                        ].join(" ")}
                      >
                        {preset.label}
                      </span>
                      {primary ? <span className="badge badge-brand">主</span> : null}
                      {preset.recommended && !active ? (
                        <span className="badge badge-neutral">推荐</span>
                      ) : null}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-ink-600">
                      {preset.hint}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">
              保存后会自动重新生成，换角度只改变呈现顺序和说法。想让简历更充实，要靠下面的
              「补充证据」提供真实材料。
            </p>
          </div>
        </div>
      )}

      {error ? (
        <div className="notice notice-danger mt-3">
          <span className="text-xs">{error}</span>
        </div>
      ) : null}
    </section>
  );
}
