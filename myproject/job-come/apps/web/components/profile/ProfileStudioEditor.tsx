"use client";

import { useEffect, useState } from "react";

import {
  updateProfile,
  type Profile,
  type ProfileEducation,
  type ProfileExperience,
  type ProfilePayload,
} from "@/lib/api/profile";
import { experienceLabel, type AgentUiFocus } from "@/lib/ui-context";

type Props = {
  profile: Profile;
  onSaved: (profile: Profile) => void;
  focusPath?: string | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

function newExpId(): string {
  return `exp_${Math.random().toString(36).slice(2, 10)}`;
}

function newEduId(): string {
  return `edu_${Math.random().toString(36).slice(2, 10)}`;
}

function emptyExperience(): ProfileExperience {
  return {
    id: newExpId(),
    company: "",
    title: "",
    start_date: "",
    end_date: null,
    highlights: [""],
    skills: [],
  };
}

function emptyEducation(): ProfileEducation {
  return { id: newEduId(), school: "", degree: null, major: null };
}

export function ProfileStudioEditor({ profile, onSaved, focusPath = null, onUiFocus }: Props) {
  const [payload, setPayload] = useState<ProfilePayload>(profile.payload);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setPayload(profile.payload);
  }, [profile.id, profile.version, profile.payload]);

  function patchExperience(index: number, patch: Partial<ProfileExperience>) {
    setPayload((prev) => {
      const experiences = [...prev.experiences];
      experiences[index] = { ...experiences[index], ...patch };
      return { ...prev, experiences };
    });
  }

  function patchHighlight(expIndex: number, hlIndex: number, value: string) {
    setPayload((prev) => {
      const experiences = [...prev.experiences];
      const highlights = [...(experiences[expIndex].highlights ?? [])];
      highlights[hlIndex] = value;
      experiences[expIndex] = { ...experiences[expIndex], highlights };
      return { ...prev, experiences };
    });
  }

  function addHighlight(expIndex: number) {
    setPayload((prev) => {
      const experiences = [...prev.experiences];
      const highlights = [...(experiences[expIndex].highlights ?? []), ""];
      experiences[expIndex] = { ...experiences[expIndex], highlights };
      return { ...prev, experiences };
    });
  }

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const cleaned: ProfilePayload = {
        ...payload,
        experiences: payload.experiences.map((exp) => ({
          ...exp,
          highlights: (exp.highlights ?? []).map((h) => h.trim()).filter(Boolean),
        })),
      };
      const next = await updateProfile(profile.id, cleaned, profile.version);
      onSaved(next);
      setMessage("已保存");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  const inputClass =
    "w-full rounded-lg border border-surface-border px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-surface-border bg-white p-5 shadow-card">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">基本信息</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block text-slate-600">姓名</span>
            <input
              className={inputClass}
              value={payload.contact.name ?? ""}
              onChange={(e) =>
                setPayload((p) => ({
                  ...p,
                  contact: { ...p.contact, name: e.target.value },
                }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">邮箱</span>
            <input
              type="email"
              className={inputClass}
              value={payload.contact.email ?? ""}
              onChange={(e) =>
                setPayload((p) => ({
                  ...p,
                  contact: { ...p.contact, email: e.target.value || null },
                }))
              }
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">手机</span>
            <input
              className={inputClass}
              value={payload.contact.phone ?? ""}
              onChange={(e) =>
                setPayload((p) => ({
                  ...p,
                  contact: { ...p.contact, phone: e.target.value || null },
                }))
              }
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1 block text-slate-600">所在地</span>
            <input
              className={inputClass}
              value={payload.contact.location ?? ""}
              onChange={(e) =>
                setPayload((p) => ({
                  ...p,
                  contact: { ...p.contact, location: e.target.value || null },
                }))
              }
            />
          </label>
        </div>
        <label className="mt-4 block text-sm">
          <span className="mb-1 block text-slate-600">个人总结</span>
          <textarea
            className={`${inputClass} min-h-24`}
            value={payload.summary ?? ""}
            onChange={(e) => setPayload((p) => ({ ...p, summary: e.target.value }))}
          />
        </label>
      </section>

      <section className="rounded-2xl border border-surface-border bg-white p-5 shadow-card">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">工作经历</h3>
          <button
            type="button"
            onClick={() =>
              setPayload((p) => ({
                ...p,
                experiences: [emptyExperience(), ...p.experiences],
              }))
            }
            className="text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            + 添加经历
          </button>
        </div>

        {!payload.experiences.length ? (
          <p className="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            暂无工作经历。点击「添加经历」或让 Agent 帮你整理。
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {payload.experiences.map((exp, expIndex) => (
              <div
                key={exp.id}
                data-path={`experiences[${expIndex}]`}
                onClick={() =>
                  onUiFocus?.({
                    path: `experiences[${expIndex}]`,
                    kind: "experience",
                    label: experienceLabel(exp.company, exp.title),
                  })
                }
                className={`rounded-xl border bg-slate-50/50 p-4 ${
                  focusPath === `experiences[${expIndex}]` ||
                  (focusPath?.startsWith(`experiences[${expIndex}].`) ?? false)
                    ? "border-brand-400 ring-2 ring-brand-500"
                    : "border-surface-border"
                }`}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    <span className="mb-1 block text-slate-600">公司</span>
                    <input
                      className={inputClass}
                      value={exp.company}
                      onChange={(e) => patchExperience(expIndex, { company: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block text-slate-600">职位</span>
                    <input
                      className={inputClass}
                      value={exp.title}
                      onChange={(e) => patchExperience(expIndex, { title: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block text-slate-600">开始</span>
                    <input
                      className={inputClass}
                      placeholder="2020-01"
                      value={exp.start_date}
                      onChange={(e) => patchExperience(expIndex, { start_date: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block text-slate-600">结束</span>
                    <input
                      className={inputClass}
                      placeholder="至今"
                      value={exp.end_date ?? ""}
                      onChange={(e) =>
                        patchExperience(expIndex, { end_date: e.target.value || null })
                      }
                    />
                  </label>
                </div>

                <div className="mt-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">工作要点</span>
                    <button
                      type="button"
                      onClick={() => addHighlight(expIndex)}
                      className="text-xs text-brand-600 hover:text-brand-700"
                    >
                      + 要点
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(exp.highlights?.length ? exp.highlights : [""]).map((hl, hlIndex) => (
                      <textarea
                        key={hlIndex}
                        data-path={`experiences[${expIndex}].highlights[${hlIndex}]`}
                        className={`${inputClass} min-h-[4rem]`}
                        placeholder="描述职责与成果，尽量量化"
                        value={hl}
                        onFocus={() =>
                          onUiFocus?.({
                            path: `experiences[${expIndex}].highlights[${hlIndex}]`,
                            kind: "highlight",
                            label: `${experienceLabel(exp.company, exp.title)} · 要点 ${hlIndex + 1}`,
                            excerpt: hl,
                          })
                        }
                        onChange={(e) => patchHighlight(expIndex, hlIndex, e.target.value)}
                      />
                    ))}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setPayload((p) => ({
                      ...p,
                      experiences: p.experiences.filter((_, i) => i !== expIndex),
                    }))
                  }
                  className="mt-3 text-xs text-red-600 hover:text-red-700"
                >
                  删除此经历
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-surface-border bg-white p-5 shadow-card">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">教育背景</h3>
          <button
            type="button"
            onClick={() =>
              setPayload((p) => ({
                ...p,
                education: [...p.education, emptyEducation()],
              }))
            }
            className="text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            + 添加
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {payload.education.map((edu, eduIndex) => (
            <div key={edu.id} className="grid gap-3 rounded-xl border border-surface-border p-3 sm:grid-cols-2">
              <input
                className={inputClass}
                placeholder="学校"
                value={edu.school}
                onChange={(e) => {
                  const education = [...payload.education];
                  education[eduIndex] = { ...edu, school: e.target.value };
                  setPayload((p) => ({ ...p, education }));
                }}
              />
              <input
                className={inputClass}
                placeholder="学历 / 专业"
                value={[edu.degree, edu.major].filter(Boolean).join(" · ")}
                onChange={(e) => {
                  const education = [...payload.education];
                  education[eduIndex] = { ...edu, degree: e.target.value, major: null };
                  setPayload((p) => ({ ...p, education }));
                }}
              />
            </div>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "保存中…" : "保存档案"}
        </button>
        {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      </div>
    </div>
  );
}
