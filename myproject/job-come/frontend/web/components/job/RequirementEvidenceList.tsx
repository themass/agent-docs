import type { RequirementEvidence } from "@/lib/api/jobs";

const STATUS_LABEL = {
  supported: "有相关依据",
  partial: "部分相关",
  unverified: "待补充依据",
};
const IMPORTANCE_LABEL = {
  required: "必要要求",
  preferred: "优先条件",
  unspecified: "重要程度待确认",
};
const BASIS_LABEL = {
  jd_explicit: "依据岗位明文",
  jd_structure: "依据岗位描述结构",
  estimated: "模型估计，非硬性门槛",
};

export function RequirementEvidenceList({ items, profileVersion }: {
  items: RequirementEvidence[];
  profileVersion?: number | null;
}) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-ink-900">岗位要求与经历依据</h3>
      <p className="text-xs leading-relaxed text-ink-500">
        {profileVersion
          ? `引用已按档案第 ${profileVersion} 版核对；档案变更后请重新评估。`
          : "引用已按评估时的档案核对。"}
        匹配判断仍是建议。材料未证明，不代表你没有这项能力。
      </p>
      {items.map((item, index) => (
        <details key={`${item.requirement}-${index}`} className="card-sunken px-3 py-3">
          <summary className="cursor-pointer text-sm text-ink-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500">
            <span className="mr-2">{item.requirement}</span>
            <span className={item.status === "supported" ? "badge badge-neutral" : "badge badge-warn"}>
              {STATUS_LABEL[item.status]}
            </span>
          </summary>
          <div className="mt-3 space-y-2 text-sm leading-relaxed text-ink-700">
            <p className="text-xs text-ink-500">
              {IMPORTANCE_LABEL[item.importance]} · {BASIS_LABEL[item.importance_basis]}
            </p>
            {item.evidence.map((citation, i) => (
              <blockquote key={i} className="whitespace-pre-wrap break-words border-l-2 border-surface-border pl-3">
                {citation.quote}
              </blockquote>
            ))}
            {item.next_question ? <p>{item.next_question}</p> : null}
          </div>
        </details>
      ))}
    </div>
  );
}
