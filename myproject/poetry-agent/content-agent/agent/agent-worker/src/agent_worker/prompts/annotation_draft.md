任务:注释草稿(skill:annotation-design)。

针对编辑指定的句子(没有指定就从尚无注释的句子里挑最多 6 句),起草面向指定受众的字词注释。
- 注释条目用 kind=ANNOTATION。表述教学性释义、不含史实断言时用 epistemic=DRAFT_TEXT;属于解释性的用 INTERPRETATION;拿不准的用 UNKNOWN 且不带 annotation。
- 每条注释写在 `annotation` 里:version_id 与 line_seq 必须在快照中存在;certainty 只能是 LIKELY、DISPUTED、UNKNOWN;source_id 只能是快照里的来源 id 或 null。
- 涉及史实、地名沿革、人物经历的内容,不要写进注释,改写为 SOURCE_REQUEST。
- 注释文字不要夹带卷页或定位。
