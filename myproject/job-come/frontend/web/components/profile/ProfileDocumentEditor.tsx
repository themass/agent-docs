"use client";

import type { Profile, ProfilePayload } from "@/lib/api/profile";
import type { ProfileDraftController } from "@/lib/hooks/useProfileDraft";
import type { AgentUiContext, AgentUiFocus } from "@/lib/ui-context";
import { experienceLabel } from "@/lib/ui-context";
import { ProfilePhotoField } from "@/components/resume/ProfilePhotoField";
import { InlineProfileField } from "./InlineProfileField";
import { DocumentSection, DraftStringList, EducationAndSkills, RemoveDraftItem } from "./ProfileDocumentSections";

type Props = {
  profile: Profile;
  editor: ProfileDraftController;
  warning?: string | null;
  sourceLocale: string;
  onProfileChange?: (profile: Profile) => void;
  onRelocalize?: (locale: "zh-CN" | "en-US") => void;
  uiContext?: AgentUiContext | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

export function ProfileDocumentEditor({ profile, editor, warning, sourceLocale, onProfileChange, onRelocalize, uiContext, onUiFocus }: Props) {
  if (!editor.draft || editor.draft.base.id !== profile.id) return null;
  const payload = editor.draft.payload;
  const contact = payload.contact;
  const patch = (values: Partial<ProfilePayload>) => editor.setPayload(p => ({...p,...values}));
  const patchContact = (key: "name" | "email" | "phone" | "location", value: string) => editor.setPayload(p => ({...p,contact:{...p.contact,[key]:value || null}}));
  return <article aria-label="可直接编辑的简历" className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
      <p>点击文字即可修改 · 修改后在顶部保存 · Ctrl / ⌘ + S 保存</p>
      <span className="badge badge-neutral">档案 v{profile.version}</span>
    </div>
    {warning ? <p role="status" className="notice notice-warn text-sm">{warning}</p> : null}
    {editor.draft.conflict ? <div role="alert" className="notice notice-danger flex-col items-start">
      <p>档案已在其他位置更新。你的编辑仍保留，暂未覆盖服务端内容。</p>
      <div className="flex flex-wrap gap-2"><button type="button" className="btn btn-sm btn-secondary" onClick={editor.downloadDraft}>下载未保存内容</button><button type="button" className="btn btn-sm btn-secondary" disabled={editor.busy} onClick={editor.discard}>放弃本次编辑，加载最新档案</button></div>
    </div> : null}
    <section className="card card-pad">
      <h2 className="text-3xl font-semibold text-ink-900"><InlineProfileField label="姓名" value={contact.name} placeholder="填写姓名" onChange={value => patchContact("name",value)} /></h2>
      <div className="mt-2 grid gap-x-6 sm:grid-cols-2 text-sm text-ink-600">{(["location","email","phone"] as const).map(key => <InlineProfileField key={key} label={{location:"所在地",email:"邮箱",phone:"手机"}[key]} value={contact[key]} placeholder={{location:"填写所在地",email:"填写邮箱",phone:"填写手机"}[key]} onChange={value => patchContact(key,value)} />)}</div>
      <div className="mt-2 space-y-1">{(contact.links ?? []).map((link,index) => <div key={index} className="flex flex-wrap gap-2 text-sm text-ink-600">
        <InlineProfileField label={`第${index + 1}个链接名称`} value={link.type} placeholder="链接名称" onChange={type => editor.setPayload(p => ({...p,contact:{...p.contact,links:(p.contact.links ?? []).map((item,i) => i === index ? {...item,type} : item)}}))} />
        <div className="min-w-0 flex-1"><InlineProfileField label={`第${index + 1}个链接地址`} value={link.url} placeholder="https://" onChange={url => editor.setPayload(p => ({...p,contact:{...p.contact,links:(p.contact.links ?? []).map((item,i) => i === index ? {...item,url} : item)}}))} /></div>
        <RemoveDraftItem label={`第${index + 1}个链接`} onRemove={() => editor.setPayload(p => ({...p,contact:{...p.contact,links:(p.contact.links ?? []).filter((_,i) => i !== index)}}))} />
      </div>)}<button type="button" className="btn btn-sm btn-ghost text-brand-700" onClick={() => editor.setPayload(p => ({...p,contact:{...p.contact,links:[...(p.contact.links ?? []),{type:"",url:""}]}}))}>+ 添加个人链接</button></div>
      {onProfileChange ? <div className="mt-4 border-t border-surface-border pt-4"><p className="mb-2 text-xs text-ink-500">简历照片</p><ProfilePhotoField profile={profile} onSaved={onProfileChange} /></div> : null}
      {onRelocalize ? <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-ink-500"><span>档案原文语言</span><div className="segment">{(["zh-CN","en-US"] as const).map(locale => <button key={locale} type="button" disabled={editor.dirty || editor.busy} aria-pressed={sourceLocale.startsWith(locale === "en-US" ? "en" : "zh")} onClick={() => onRelocalize(locale)} className={`segment-item ${sourceLocale.startsWith(locale === "en-US" ? "en" : "zh") ? "segment-item-active" : ""}`}>{locale === "zh-CN" ? "中文" : "英文"}</button>)}</div><span>{editor.dirty ? "先保存修改再切换语言" : "切换会生成对应译文"}</span></div> : null}
    </section>
    <DocumentSection title="个人简介"><InlineProfileField label="个人简介" value={payload.summary} multiline placeholder="点击补充个人简介" onChange={summary => patch({summary})} onFocus={() => onUiFocus?.({path:"summary",kind:"summary",label:"个人简介"})} /></DocumentSection>
    <DocumentSection title="工作经历" action={<button type="button" className="btn btn-sm btn-secondary" onClick={() => editor.setPayload(p => ({...p,experiences:[{id:`exp_${crypto.randomUUID()}`,company:"",title:"",start_date:"",end_date:null,scope:null,highlights:[],skills:[]},...p.experiences]}))}>+ 添加经历</button>}>
      {!payload.experiences.length ? <p className="text-sm text-ink-400">点击「添加经历」直接填写，或让右侧舟卡协助整理。</p> : null}
      {payload.experiences.map((exp,index) => {
        const path = `experiences[${index}]`;
        const label = experienceLabel(exp.company,exp.title);
        const change = (values: Partial<typeof exp>) => editor.setPayload(p => ({...p,experiences:p.experiences.map(e => e.id === exp.id ? {...e,...values} : e)}));
        const focus = (subpath = path) => onUiFocus?.({path:subpath,kind:subpath.includes("highlights") ? "highlight" : "experience",label});
        return <section key={exp.id} data-path={path} className={`card card-pad ${uiContext?.focus?.path?.startsWith(path) ? "ring-2 ring-brand-500" : ""}`}>
          <div className="flex items-start justify-between gap-3"><h4 className="min-w-0 text-lg font-semibold"><InlineProfileField label={`第${index + 1}段经历职位`} value={exp.title} placeholder="填写职位" onFocus={() => focus()} onChange={title => change({title})} /></h4><RemoveDraftItem label={`第${index + 1}段工作经历`} onRemove={() => editor.setPayload(p => ({...p,experiences:p.experiences.filter(e => e.id !== exp.id)}))} /></div>
          <div className="flex flex-wrap items-center gap-x-4 text-sm text-ink-600">
            <InlineProfileField label={`第${index + 1}段经历公司`} value={exp.company} placeholder="填写公司" className="font-medium text-brand-700" onFocus={() => focus()} onChange={company => change({company})} />
            <InlineProfileField label={`第${index + 1}段经历开始日期`} value={exp.start_date} placeholder="开始年月" onFocus={() => focus()} onChange={start_date => change({start_date})} /><span aria-hidden="true">—</span>
            <InlineProfileField label={`第${index + 1}段经历结束日期`} value={exp.end_date} placeholder="至今" onFocus={() => focus()} onChange={end_date => change({end_date:end_date || null})} />
            <InlineProfileField label={`第${index + 1}段经历所在地`} value={exp.location} placeholder="工作地点" onChange={location => change({location})} />
          </div>
          <div className="mt-3 text-sm font-medium text-ink-700" data-path={`${path}.scope`}><InlineProfileField label={`第${index + 1}段经历负责范围`} value={exp.scope} placeholder="补充负责范围、团队与业务规模" multiline onFocus={() => focus(`${path}.scope`)} onChange={scope => change({scope:scope || null})} /></div>
          <DraftStringList path={`${path}.highlights`} label={`第${index + 1}段工作要点`} items={exp.highlights ?? []} onChange={highlights => change({highlights})} onFocus={i => focus(`${path}.highlights[${i}]`)} />
          <details className="mt-3 text-xs text-ink-500"><summary className="cursor-pointer">关联技能{exp.skills?.length ? ` · ${exp.skills.join("、")}` : ""}</summary><DraftStringList label={`第${index + 1}段经历技能`} items={exp.skills ?? []} onChange={skills => change({skills})} /></details>
        </section>;
      })}
    </DocumentSection>
    <DocumentSection title="项目经历" action={<button type="button" className="btn btn-sm btn-secondary" onClick={() => editor.setPayload(p => ({...p,projects:[...(p.projects ?? []),{id:`proj_${crypto.randomUUID()}`,name:"",role:null,description:null,highlights:[]}]}))}>+ 添加项目</button>}>
      {!(payload.projects ?? []).length ? <p className="text-sm text-ink-400">可添加独立项目，已有工作经历无需重复填写。</p> : null}
      {(payload.projects ?? []).map((project,index) => {
        const change = (values: Partial<typeof project>) => editor.setPayload(p => ({...p,projects:(p.projects ?? []).map(item => item.id === project.id ? {...item,...values} : item)}));
        const focus = (path = `projects[${index}]`) => onUiFocus?.({path,kind:path.includes("highlights") ? "highlight" : "project",label:project.name || "项目"});
        return <section key={project.id} data-path={`projects[${index}]`} className="card card-pad">
          <div className="flex items-start justify-between gap-3"><h4 className="min-w-0 text-lg font-semibold"><InlineProfileField label={`第${index + 1}个项目名称`} value={project.name} placeholder="填写项目名称" onFocus={() => focus()} onChange={name => change({name})} /></h4><RemoveDraftItem label={`第${index + 1}个项目`} onRemove={() => editor.setPayload(p => ({...p,projects:(p.projects ?? []).filter(item => item.id !== project.id)}))} /></div>
          <div className="flex flex-wrap gap-x-4 text-sm text-ink-600">
            <InlineProfileField label={`第${index + 1}个项目角色`} value={project.role} placeholder="担任角色" onChange={role => change({role})} />
            <InlineProfileField label={`第${index + 1}个项目开始日期`} value={project.start_date} placeholder="开始年月" onChange={start_date => change({start_date:start_date || null})} />
            <InlineProfileField label={`第${index + 1}个项目结束日期`} value={project.end_date} placeholder="结束年月" onChange={end_date => change({end_date:end_date || null})} />
          </div>
          <InlineProfileField label={`第${index + 1}个项目说明`} value={project.description} placeholder="补充项目背景" multiline onFocus={() => focus()} onChange={description => change({description})} />
          <InlineProfileField label={`第${index + 1}个项目范围`} value={project.scope} placeholder="补充项目范围与规模" multiline onChange={scope => change({scope})} />
          <DraftStringList path={`projects[${index}].highlights`} label={`第${index + 1}个项目要点`} items={project.highlights ?? []} onChange={highlights => change({highlights})} onFocus={i => focus(`projects[${index}].highlights[${i}]`)} />
        </section>;
      })}
    </DocumentSection>
    <EducationAndSkills payload={payload} editor={editor} onUiFocus={onUiFocus} />
  </article>;
}
