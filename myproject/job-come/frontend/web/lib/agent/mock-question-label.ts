/**
 * The label the interviewer's `jc_mock_ask` returns for a question it has put to the candidate,
 * such as "第 3 题" or "第 2 题 · 追问 1". Returns null for a refused ask, or for anything else.
 */
export function mockQuestionLabel(result: string): string | null {
  try {
    const data = JSON.parse(result) as { accepted?: unknown; label?: unknown };
    if (data.accepted === true && typeof data.label === "string") return data.label;
  } catch {
    // Not the JSON this tool returns; it is not a question marker.
  }
  return null;
}

export const MOCK_ASK_TOOL = "jc_mock_ask";
