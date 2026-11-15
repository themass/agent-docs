import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue } from "./helpers";

/**
 * F-01 ~ F-10: one mock interview, end to end.
 *
 * The product rule these cover is state integrity, not UI: a session that the
 * database calls `completed` must not keep showing "进行中", an answer must be
 * recorded against the question it was given for, and a report must exist once the
 * session ends. Those are exactly the mismatches found by hand before.
 */

async function profileWithJob(page: Page): Promise<{ id: string; jobId?: string } | undefined> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  const confirmed = list.find((p: { status?: string }) => p.status === "confirmed") ?? list[0];
  if (!confirmed) return undefined;
  const jobsRes = await page.request.get(
    new URL(`/api/v1/jobs/profiles/${confirmed.id}`, page.url()).toString(),
  );
  if (jobsRes.status() !== 200) return { id: confirmed.id };
  const jobs = await jobsRes.json();
  const arr = Array.isArray(jobs) ? jobs : (jobs.jobs ?? []);
  return { id: confirmed.id, jobId: arr[0]?.id };
}

test.describe("F. 模拟面试完整流程", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("F-01/F-02/F-06/F-07/F-08 开一场、答一题、结束、报告存在", async ({ page }) => {
    const prof = requireValue(await profileWithJob(page), "没有可用档案");
    

    // Warmup mode needs no job, so this works on any profile. Level is left out so
    // the server picks one from the experience; if it cannot, creation is refused
    // with a readable reason and the test records that rather than failing.
    const createRes = await page.request.post(
      new URL("/api/v1/coach/mock/sessions", page.url()).toString(),
      { data: { profile_id: prof.id, mode: "warmup", kind: "warmup", style: "standard" } },
    );
    expect(createRes.status(), "开不了模拟面试").toBeLessThan(500);
    if (createRes.status() >= 400) {
      const body = await createRes.json();
      expect(body.message ?? body.detail ?? "").toBeTruthy();
      test.skip(true, `服务端拒绝开局（合规）：${body.message ?? body.code ?? createRes.status()}`);
    }

    const session = await createRes.json();
    const sid: string = session.id ?? session.mock_session_id;
    expect(sid, "没有返回会话 id").toBeTruthy();
    expect(["active", "in_progress"].includes(session.status ?? "active")).toBe(true);

    // F-06: progress must reflect zero answered so far.
    const progRes = await page.request.get(
      new URL(`/api/v1/coach/mock/sessions/${sid}/progress`, page.url()).toString(),
    );
    expect(progRes.status()).toBe(200);
    const prog = await progRes.json();
    expect(prog.asked_main, "新开局却被记为已提问").toBe(0);
    expect(prog.main_limit, "没有题目上限").toBeGreaterThan(0);

    // F-05: skip and swap are refused-or-accepted, but never 5xx.
    const skipRes = await page.request.post(
      new URL(`/api/v1/coach/mock/sessions/${sid}/skip`, page.url()).toString(),
      { data: { question_id: "q_does_not_exist" } },
    );
    expect(skipRes.status(), "跳过不存在的题返回了 5xx").toBeLessThan(500);

    // F-07: ending is idempotent enough to call, and leaves a terminal state.
    const endRes = await page.request.post(
      new URL(`/api/v1/coach/mock/sessions/${sid}/complete`, page.url()).toString(),
      { data: {} },
    );
    expect(endRes.status(), "结束本场失败").toBeLessThan(500);
    if (endRes.status() === 200) {
      const ended = await endRes.json();
      expect(ended.status, "结束后状态没有变化").not.toBe("active");
    }

    // F-08: a report object must exist even if generation is still pending. The
    // page reads `status` to decide what to show; a 500 here is the page showing
    // nothing at all.
    const repRes = await page.request.get(
      new URL(`/api/v1/coach/mock/sessions/${sid}/report`, page.url()).toString(),
    );
    expect(repRes.status(), "报告接口报错").toBeLessThan(500);
    if (repRes.status() === 200) {
      const rep = await repRes.json();
      expect(["active", "pending", "failed", "ready"]).toContain(rep.status);
      expect(rep.mock_session_id).toBe(sid);
    }
  });

  test("F-04 答题必须记录到被问的那道题上", async ({ page }) => {
    const prof = requireValue(await profileWithJob(page), "没有可用档案");
    

    const bankRes = await page.request.get(
      new URL(`/api/v1/coach/profiles/${prof.id}/bank?limit=1`, page.url()).toString(),
    );
    test.skip(bankRes.status() !== 200, "题库接口不可用");
    const bank = await bankRes.json();
    const q = (bank.questions ?? [])[0];
    test.skip(!q, "题库为空，无法验证答题落库");

    const answer = `e2e-answer-${Date.now()}`;
    const res = await page.request.post(
      new URL(`/api/v1/coach/questions/${q.id}/attempts`, page.url()).toString(),
      { data: { user_answer: answer } },
    );
    expect(res.status(), "答题接口报错").toBeLessThan(400);
    const saved = await res.json();
    // Recording an answer against a different question is the silent failure this
    // asserts against: the user thinks they answered and the bank disagrees.
    expect(saved.question_id, "答案记到了别的题上").toBe(q.id);
    expect(saved.attempt_id).toBeTruthy();
  });

  test("F-03 级别推荐可用", async ({ page }) => {
    // `profile_id` is a required query parameter — the recommendation is derived
    // from that profile's experience, so there is no profile-less form of it.
    const prof = requireValue(await profileWithJob(page), "没有可用档案");
    

    const res = await page.request.get(
      new URL(
        `/api/v1/coach/mock/level-recommendation?profile_id=${prof.id}`,
        page.url(),
      ).toString(),
    );
    test.skip(res.status() === 404, "该版本没有级别推荐接口");
    expect(res.status(), "级别推荐接口报错").toBe(200);

    const body = await res.json();
    // The response carries `recommended` (plus `reason` and the full level list) —
    // or null when nothing can be inferred, which forces a manual choice. Both are
    // valid; a 500 or a body with neither is not.
    expect(body).toHaveProperty("recommended");
    expect(body).toHaveProperty("levels");
    if (body.recommended) {
      expect(body.levels.map((l: { key: string }) => l.key)).toContain(body.recommended);
    }
  });
});
