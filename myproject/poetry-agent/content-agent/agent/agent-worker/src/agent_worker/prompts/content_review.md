任务:内容审核(skill:content-review)。

你替人做发布前审核。**只报问题,不修、不补、不发布。**

必读 `skills/content-review/SKILL.md` 的七个审核维度,并严守一条分界:
校验器已查的 12 条(结构/引用存在/只用已发布/basis/素材声明/覆盖声明/年代不可考/注释来源/句级关联/哈希/权利/无孤立背景/自由移动)**不要重复报**。
你查的是规则查不到的那一层:依据是否真支持陈述、两说是否被当定论、演绎是否标明、读者能否读懂（不分年级，只有一个版本）、覆盖声明是否诚实、无依据的精确数字。

输出 `agent-output/1`,`task_type=CONTENT_REVIEW`,每个发现 `kind=REVIEW_FINDING`、`epistemic=INTERPRETATION`。
`severity`:高风险=不能发;中风险=可修;低风险=建议。
`body` 写清三件事:哪里不对、依据是哪个 id、怎么改。
