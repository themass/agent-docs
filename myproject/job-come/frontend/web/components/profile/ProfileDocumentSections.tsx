"use client";

import type { ReactNode } from "react";
import type { ProfilePayload } from "@/lib/api/profile";
import type { ProfileDraftController } from "@/lib/hooks/useProfileDraft";
import type { AgentUiFocus } from "@/lib/ui-context";
import { InlineProfileField } from "./InlineProfileField";

export function DocumentSection({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return <section className="space-y-3"><div className="flex items-center justify-between gap-3 border-b border-surface-border pb-2"><h3 className="text-lg font-semibold text-ink-900">{title}</h3>{action}</div>{children}</section>;
}

export function RemoveDraftItem({ label, onRemove }: { label: string; onRemove: () => void }) {
  return <button type="button" className="btn btn-sm btn-ghost text-ink-500 hover:text-danger-700" aria-label={`删除${label}`} onClick={() => {
    if (window.confirm(`从当前草稿删除${label}？保存修改后才会写入档案。`)) onRemove();
  }}>删除</button>;
}

export function DraftStringList({ items, label, onChange, onFocus, path }: {
  items: string[]; label: string; path?: string; onChange: (items: string[]) => void; onFocus?: (index: number) => void;
}) {
  return <div className="space-y-2">
    <ul className="space-y-1">{items.map((value, index) => <li key={index} data-path={path ? `${path}[${index}]` : undefined} className="flex items-start gap-2">
      <span className="mt-4 h-1 w-1 shrink-0 rounded-full bg-brand-400" aria-hidden="true" />
      <div className="min-w-0 flex-1"><InlineProfileField label={`${label}第${index + 1}条`} value={value} multiline onFocus={() => onFocus?.(index)} placeholder="点击填写职责或成果" onChange={(text) => onChange(items.map((item, i) => i === index ? text : item))} /></div>
      <RemoveDraftItem label={`${label}第${index + 1}条`} onRemove={() => onChange(items.filter((_, i) => i !== index))} />
    </li>)}</ul>
    <button type="button" className="btn btn-sm btn-ghost text-brand-700" onClick={() => onChange([...items, ""])}>+ 添加{label.endsWith("技能") ? "技能" : "要点"}</button>
  </div>;
}

export function EducationAndSkills({ payload, editor, onUiFocus }: {
  payload: ProfilePayload; editor: ProfileDraftController; onUiFocus?: (focus: AgentUiFocus) => void;
}) {
  return <>
    <DocumentSection title="教育背景" action={<button type="button" className="btn btn-sm btn-secondary" onClick={() => editor.setPayload(p => ({ ...p, education: [...p.education, { id: `edu_${crypto.randomUUID()}`, school: "", degree: null, major: null }] }))}>+ 添加教育</button>}>
      {!payload.education.length ? <p className="text-sm text-ink-400">尚未添加教育经历</p> : null}
      {payload.education.map((edu, index) => {
        const patch = (values: Partial<typeof edu>) => editor.setPayload(p => ({ ...p, education: p.education.map(e => e.id === edu.id ? { ...e, ...values } : e) }));
        return <div key={edu.id} data-path={`education[${index}]`} className="rounded-xl border border-surface-border p-4" onFocusCapture={() => onUiFocus?.({path:`education[${index}]`,kind:"education",label:edu.school || "教育经历"})}>
          <div className="flex items-start justify-between gap-3"><InlineProfileField label={`第${index + 1}段教育学校`} value={edu.school} placeholder="填写学校" className="font-semibold" onChange={school => patch({ school })} /><RemoveDraftItem label={`第${index + 1}段教育`} onRemove={() => editor.setPayload(p => ({...p, education:p.education.filter(e => e.id !== edu.id)}))} /></div>
          <div className="flex flex-wrap gap-x-4 text-sm text-ink-600">
            <InlineProfileField label={`第${index + 1}段教育学历`} value={edu.degree} placeholder="填写学历" onChange={degree => patch({degree})} />
            <InlineProfileField label={`第${index + 1}段教育专业`} value={edu.major} placeholder="填写专业" onChange={major => patch({major})} />
            <InlineProfileField label={`第${index + 1}段教育开始日期`} value={edu.start_date} placeholder="开始年月" onChange={start_date => patch({start_date:start_date || null})} />
            <InlineProfileField label={`第${index + 1}段教育结束日期`} value={edu.end_date} placeholder="结束年月" onChange={end_date => patch({end_date:end_date || null})} />
          </div>
        </div>;
      })}
    </DocumentSection>
    <DocumentSection title="专业技能" action={<button type="button" className="btn btn-sm btn-secondary" onClick={() => editor.setPayload(p => ({...p, skills:[...(p.skills ?? []), {name:""}]}))}>+ 添加技能</button>}>
      <div data-path="skills" className="flex flex-wrap gap-2">{(payload.skills ?? []).map((skill, index) => <div key={index} className="flex items-center rounded-lg border border-surface-border bg-surface-sunken px-2 text-sm">
        <InlineProfileField label={`第${index + 1}项技能`} value={skill.name} placeholder="填写技能" onFocus={() => onUiFocus?.({path:"skills",kind:"skills",label:"专业技能"})} onChange={name => editor.setPayload(p => ({...p, skills:(p.skills ?? []).map((s,i) => i === index ? {...s,name} : s)}))} />
        <RemoveDraftItem label={`第${index + 1}项技能`} onRemove={() => editor.setPayload(p => ({...p,skills:(p.skills ?? []).filter((_,i) => i !== index)}))} />
      </div>)}</div>
      {!payload.skills?.length ? <p className="text-sm text-ink-400">点击添加技能；各段工作经历内的关联技能会继续保留。</p> : null}
    </DocumentSection>
  </>;
}
