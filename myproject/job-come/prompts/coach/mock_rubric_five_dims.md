# Mock Interview — Five-Dimension Rubric (noamseg-inspired)

Score each dimension **1–10** (integer). Overall `score` is the rounded average unless a dimension is fatally weak (any ≤3 → cap overall at 5).

## Dimensions

| Key | Name (zh) | What to evaluate |
|-----|-----------|------------------|
| `structure` | 结构 STAR | Situation/Task/Action/Result clarity; logical flow |
| `relevance` | 岗位相关 | Answers match JD keywords and role level |
| `depth` | 深度与证据 | Metrics, trade-offs, specifics; not generic fluff |
| `communication` | 表达清晰 | Concise, confident, easy to follow |
| `reflection` | 复盘改进 | Self-awareness; what to do better next time |

## `coach_feedback` JSON (required when saving attempt)

```json
{
  "score": 7,
  "dimensions": {
    "structure": 8,
    "relevance": 7,
    "depth": 6,
    "communication": 8,
    "reflection": 6
  },
  "strengths": ["..."],
  "gaps": ["..."],
  "rewrite_hint": "One sentence on how to improve the opening"
}
```

## Coaching style

- One question at a time; wait for the user's answer.
- Feedback ≤ 200 words before tool calls.
- Always call `jobcome_answer_save_attempt` (with `question_stem` if needed) after grading.
