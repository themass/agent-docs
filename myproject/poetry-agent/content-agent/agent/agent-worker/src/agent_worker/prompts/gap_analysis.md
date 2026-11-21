任务:缺口分析(skill:poem-gap-analysis)。

只读分析快照,产出按严重度排序的缺口清单。检查:缺文本版本或缺句、四层背景缺失、背景未关联诗句(反堆砌)、claim 没有可核查出处、FACT 类 claim 缺来源、来源仍为 PENDING、占位定位、注释覆盖了哪几句、覆盖声明与未考日期、审计非零项。
- 每条缺口用 kind=GAP,epistemic=DRAFT_TEXT 或 UNKNOWN,severity 必填,evidence_refs 填快照里真实的 id。
- 对每条没有可核查出处的 claim,另写一条 kind=SOURCE_REQUEST,epistemic=FACT_REQUEST,带 source_request;只写要核对什么、建议什么类型的来源,**不要写卷页或定位**。
- 不写注释,不写背景正文。
