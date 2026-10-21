"use client";

import {
  type Profile,
  type ProfileEducation,
  type ProfileExperience,
} from "@/lib/api/profile";
import type { ProfileDraftController } from "@/lib/hooks/useProfileDraft";
import { ProfilePhotoField } from "@/components/resume/ProfilePhotoField";
import { ZHOUKA_NAME } from "@/lib/brand";
import { experienceLabel, type AgentUiFocus } from "@/lib/ui-context";

type Props = {
  profile: Profile;
  editor: ProfileDraftController;
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

export function ProfileStudioEditor({ profile, editor, onSaved, focusPath = null, onUiFocus }: Props) {
  const { draft, setPayload } = editor;
  if (!draft || draft.base.id !== profile.id) return null;
  const payload = draft.payload;

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

  // Shared control style lives in globals.css so every form in the app matches.
  const inputClass = "field";

  return (
    <div className="space-y-5">
      <div role="status" className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-surface-border bg-surface p-3 shadow-sm">
        <span className="text-sm text-ink-700">{editor.busy ? "保存中…" : editor.dirty ? "有未保存的修改" : "档案已保存"}</span>
        <button type="button" onClick={() => void editor.save()} disabled={editor.busy || !editor.dirty || Boolean(draft.conflict)} className="btn btn-sm btn-primary">
          {editor.busy ? "保存中…" : "保存修改"}
        </button>
        {editor.message ? <p className="w-full text-sm text-ink-700">{editor.message}</p> : null}
        {draft.conflict ? <div role="alert" className="w-full text-sm text-danger-700">
          档案已在其他位置更新。你的输入已保留，尚未覆盖服务器内容。可先下载未保存内容留作备份，再加载最新档案重新合并。
          <button type="button" onClick={editor.downloadDraft} className="btn btn-sm btn-secondary mt-2">下载未保存内容</button>
          <button type="button" onClick={editor.discard} disabled={editor.busy} className="btn btn-sm btn-secondary mt-2">放弃本次编辑，加载最新档案</button>
        </div> : null}
      </div>
      <section className="card card-pad">
        <h3 className="label-meta">基本信息</h3>
        {/* The photo saves through its own endpoints the moment it changes, so it sits
            above the form fields rather than inside the block this form's Save button
            commits — see the note in `ProfilePhotoField`. `onSaved` is the editor's
            own handler, which refreshes `profile` and therefore `expected_version`. */}
        <div className="mt-4">
          <p className="mb-2 text-sm font-medium text-ink-800">简历照片</p>
          <ProfilePhotoField profile={profile} onSaved={onSaved} />
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1.5 block font-medium text-ink-800">姓名</span>
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
            <span className="mb-1.5 block font-medium text-ink-800">邮箱</span>
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
            <span className="mb-1.5 block font-medium text-ink-800">手机</span>
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
            <span className="mb-1.5 block font-medium text-ink-800">所在地</span>
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
          <span className="mb-1.5 block font-medium text-ink-800">个人总结</span>
          <textarea
            className={`${inputClass} min-h-28 leading-relaxed`}
            value={payload.summary ?? ""}
            onChange={(e) => setPayload((p) => ({ ...p, summary: e.target.value }))}
          />
        </label>
      </section>

      <section className="card card-pad">
        <div className="flex items-center justify-between gap-2">
          <h3 className="label-meta">工作经历</h3>
          <button
            type="button"
            onClick={() =>
              setPayload((p) => ({
                ...p,
                experiences: [emptyExperience(), ...p.experiences],
              }))
            }
            className="btn btn-sm btn-secondary"
          >
            + 添加经历
          </button>
        </div>

        {!payload.experiences.length ? (
          <div className="card-sunken mt-4 px-4 py-10 text-center">
            <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-500">
              暂无工作经历。点击「添加经历」或让{ZHOUKA_NAME}帮你整理。
            </p>
          </div>
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
                className={`rounded-xl bg-surface-sunken p-4 ring-1 ring-inset transition ${
                  focusPath === `experiences[${expIndex}]` ||
                  (focusPath?.startsWith(`experiences[${expIndex}].`) ?? false)
                    ? "ring-2 ring-brand-500"
                    : "ring-surface-border"
                }`}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-ink-800">公司</span>
                    <input
                      className={inputClass}
                      value={exp.company}
                      onChange={(e) => patchExperience(expIndex, { company: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-ink-800">职位</span>
                    <input
                      className={inputClass}
                      value={exp.title}
                      onChange={(e) => patchExperience(expIndex, { title: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-ink-800">开始</span>
                    <input
                      className={inputClass}
                      placeholder="2020-01"
                      value={exp.start_date}
                      onChange={(e) => patchExperience(expIndex, { start_date: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-ink-800">结束</span>
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

                {/* The scope line. Edited here as well as asked in the interview,
                    because an uploaded resume rarely states it and the generated block
                    opens with it: without this field the 先总后分 layer is only
                    reachable by users who came in through the interview. */}
                <label className="mt-3 block text-sm">
                  <span className="mb-1.5 block font-medium text-ink-800">
                    负责范围与量级
                  </span>
                  <textarea
                    data-path={`experiences[${expIndex}].scope`}
                    className={`${inputClass} min-h-[3.5rem] leading-relaxed`}
                    placeholder="例如：带 8 人后端团队，负责订单与结算两条主链路"
                    value={exp.scope ?? ""}
                    onChange={(e) =>
                      patchExperience(expIndex, { scope: e.target.value || null })
                    }
                  />
                  <span className="mt-1 block text-xs leading-relaxed text-ink-500">
                    这句会成为这段经历的开头，决定招聘方如何理解下面每一条要点。
                  </span>
                </label>

                <div className="mt-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="label-meta">工作要点</span>
                    <button
                      type="button"
                      onClick={() => addHighlight(expIndex)}
                      className="btn btn-sm btn-ghost text-brand-700 hover:text-brand-800"
                    >
                      + 要点
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(exp.highlights?.length ? exp.highlights : [""]).map((hl, hlIndex) => (
                      <textarea
                        key={hlIndex}
                        data-path={`experiences[${expIndex}].highlights[${hlIndex}]`}
                        className={`${inputClass} min-h-[4.5rem] leading-relaxed`}
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
                  className="btn btn-sm btn-ghost mt-3 text-danger-700 hover:bg-danger-50 hover:text-danger-700"
                >
                  删除此经历
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card card-pad">
        <div className="flex items-center justify-between gap-2">
          <h3 className="label-meta">教育背景</h3>
          <button
            type="button"
            onClick={() =>
              setPayload((p) => ({
                ...p,
                education: [...p.education, emptyEducation()],
              }))
            }
            className="btn btn-sm btn-secondary"
          >
            + 添加
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {payload.education.map((edu, eduIndex) => (
            <div key={edu.id} className="grid gap-3 rounded-xl bg-surface-sunken p-3 ring-1 ring-inset ring-surface-border sm:grid-cols-2">
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


    </div>
  );
}
