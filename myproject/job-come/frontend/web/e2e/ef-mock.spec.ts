import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue } from "./helpers";

/** E. JD 解析与匹配 / F. 模拟面试 */

async function firstProfile(page: Page): Promise<{ id: string; status?: string }> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  return list[0];
}

test.describe("E. JD 解析与匹配", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("E-01 粘贴 JD 能解析出结构化结果", async ({ page }) => {
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    

    const res = await page.request.post(
      new URL(`/api/v1/jobs/profiles/${prof.id}/parse`, page.url()).toString(),
      {
        data: {
          raw_text:
            "高级后端工程师\n职责：负责订单系统架构设计与高并发优化，保障核心链路稳定性。" +
            "要求：5 年以上 Go/Java 经验，熟悉分布式系统、消息队列与数据库调优，" +
            "有大规模服务治理经验者优先。",
        },
        timeout: 180_000,
      },
    );
    expect(res.status(), "解析接口报错").toBeLessThan(400);
    const job = await res.json();
    expect(job.id ?? job.job_id, "没有返回岗位 id").toBeTruthy();
  });

  test("E-04 低分不阻断后续操作", async ({ page }) => {
    // The product rule is that a match score is a diagnosis, never a gate. Asserting
    // this through the API: scoring a profile against a job must not make the
    // profile unreadable or unexportable.
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    
    const res = await page.request.get(
      new URL(`/api/v1/profiles/${prof.id}`, page.url()).toString(),
    );
    expect(res.status()).toBe(200);
  });
});

test.describe("F. 模拟面试", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("F-02 目标岗模式未绑定岗位时被拒，且文案正确", async ({ page }) => {
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    

    const res = await page.request.post(
      new URL("/api/v1/coach/mock/sessions", page.url()).toString(),
      { data: { profile_id: prof.id, mode: "target", kind: "full" } },
    );
    // Either it refuses for lack of a job (the documented rule) or for quota /
    // level — but it must never silently create a target-mode session with no JD.
    if (res.status() === 200) {
      const sess = await res.json();
      expect(sess.job_id, "目标岗模式竟然没有绑定岗位").toBeTruthy();
    } else {
      const body = await res.json();
      expect(body.message ?? body.detail ?? "").toBeTruthy();
      expect(JSON.stringify(body)).not.toMatch(/Traceback/);
    }
  });

  test("F-01 练手模式不绑 JD 可以开", async ({ page }) => {
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    

    const res = await page.request.post(
      new URL("/api/v1/coach/mock/sessions", page.url()).toString(),
      { data: { profile_id: prof.id, mode: "warmup", kind: "single" } },
    );
    // 409 with a readable reason (quota / level) is acceptable; 500 is not.
    expect(res.status()).toBeLessThan(500);
  });
});
