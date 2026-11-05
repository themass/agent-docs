/** How the report page keeps asking for a report that is still being generated.
 *
 * It asks again after each answer, not on a fixed clock, so two requests are never in flight at
 * once. A failure that may pass (the server restarting, the network dropping) is retried more
 * slowly each time; a refusal that will not change (signed out, no such report) stops the asking.
 * After a long wait it stops and says so rather than ask for ever.
 */

export const POLL_BASE_MS = 5_000;
export const POLL_MAX_MS = 60_000;
/** A report takes a minute or two; ten minutes is the reviewer's whole budget and then some. */
export const POLL_GIVE_UP_MS = 10 * 60_000;

export type PollState = { failures: number; elapsedMs: number };
export type PollOutcome = { ok: true } | { ok: false; status: number | null };
export type PollStop = "rejected" | "gave_up";
export type PollStep = { state: PollState; delayMs: number | null; stopped: PollStop | null };

export const START: PollState = { failures: 0, elapsedMs: 0 };

/** A 4xx other than "slow down" or "try again" says the request itself is wrong. */
function isRefusal(status: number | null): boolean {
  return status !== null && status >= 400 && status < 500 && status !== 408 && status !== 429;
}

export function nextPoll(state: PollState, outcome: PollOutcome): PollStep {
  if (!outcome.ok && isRefusal(outcome.status)) {
    return { state, delayMs: null, stopped: "rejected" };
  }
  const failures = outcome.ok ? 0 : state.failures + 1;
  const delayMs = Math.min(POLL_MAX_MS, POLL_BASE_MS * 2 ** failures);
  const elapsedMs = state.elapsedMs + delayMs;
  if (elapsedMs >= POLL_GIVE_UP_MS) {
    return { state: { failures, elapsedMs }, delayMs: null, stopped: "gave_up" };
  }
  return { state: { failures, elapsedMs }, delayMs, stopped: null };
}
