# resume-reviewer

Export gate: review resume draft before PDF/DOCX or apply pipeline.

## Workflow

1. Call `jobcome_profile_get` if you need context.
2. Call `jobcome_resume_review` on the latest elevated draft.
3. If `passed` is false, explain `issues` / `notes` and ask user to fix profile or bullets — do **not** export.
4. Only after `passed: true` may the user proceed to export or `jobcome_apply_pipeline`.

## Rules

- Never skip review before export.
- Do not invent facts; only flag inconsistencies vs profile.
