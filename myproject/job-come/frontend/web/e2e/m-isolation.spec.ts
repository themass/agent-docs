import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * M. 安全与隔离.
 *
 * Cross-user access needs two accounts, which this fixture does not have. What it
 * *can* assert without a second account: unauthenticated access is refused, and
 * the public endpoints carry no user data. The multi-account cases are listed as
 * not-covered in e2e/README.md rather than faked here.
 */

test.describe("M. 安全与隔离", () => {
  test("M-05 未登录访问业务接口返回 401", async ({ request }) => {
    for (const path of ["/api/v1/profiles", "/api/v1/agent/sessions", "/api/v1/auth/account"]) {
      const res = await request.get(path);
      expect(res.status(), `${path} 未登录时没有拒绝`).toBe(401);
    }
  });

  test("M-06 监控端点不含用户数据", async ({ request }) => {
    const res = await request.get("/api/v1/metrics/snapshot");
    // Either 200 with counts only, or 404 if the deployment hides it.
    expect([200, 404]).toContain(res.status());
    if (res.status() !== 200) return;
    const text = await res.text();
    // Counts and durations only: no email, no user id, no prompt text.
    expect(text).not.toMatch(/@[a-z0-9-]+\.(com|cn|net|org)/i);
    expect(text).not.toMatch(/\busr_[a-z0-9]{8,}\b/);
    expect(text).not.toMatch(/"prompt_text"|"response_text"|"reasoning_text"/);
  });

  test("M-08 错误响应不泄漏堆栈或内部路径", async ({ request }) => {
    const res = await request.get("/api/v1/profiles/does_not_exist_at_all");
    expect(res.status()).toBeGreaterThanOrEqual(400);
    const text = await res.text();
    expect(text).not.toMatch(/Traceback/);
    expect(text).not.toMatch(/\/home\/web\/|\/Users\/|site-packages/);
    expect(text).not.toMatch(/psycopg|sqlalchemy|postgres:\/\//i);
  });
});
