/** The small pieces the interview bar and the report notice are made of. Kept apart from the
 * components so they can be tested without a browser. */

/** Stages the server reports for an interview in progress (see `jc_mock_plan`). */
export const STAGE_LABEL: Record<string, string> = {
  opening: "开场",
  experience: "经历深挖",
  core: "岗位核心",
  scenario: "情景与行为",
  candidate_qa: "候选人提问",
};

/** What the page says for the candidate after Skip and Swap, so the interviewer moves on without the
 * candidate typing it. The server reads both as steering, not as an answer
 * (`tests/test_mock_answer_recorder.py` pins the same two lines). */
export const SKIP_MESSAGE = "跳过这题，请出下一题。";
export const SWAP_MESSAGE = "换一题，请出下一题。";

type BarProgress = {
  stage: string;
  asked_main: number;
  main_limit: number;
  candidate_qa: boolean;
};

export function formatElapsed(ms: number): string {
  const seconds = Number.isFinite(ms) && ms > 0 ? Math.floor(ms / 1000) : 0;
  const two = (n: number) => String(n).padStart(2, "0");
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours > 0 ? `${hours}:${two(minutes)}:${two(rest)}` : `${two(minutes)}:${two(rest)}`;
}

/** The two parts of the bar's line: where in the interview, and which stage. */
export function barText(progress: BarProgress): { position: string; stage: string } {
  if (progress.candidate_qa) return { position: STAGE_LABEL.candidate_qa, stage: "" };
  const stage = STAGE_LABEL[progress.stage] ?? "";
  if (progress.asked_main === 0) return { position: STAGE_LABEL.opening, stage };
  return { position: `第 ${progress.asked_main} / ${progress.main_limit} 题`, stage };
}
