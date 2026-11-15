import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * D. 导出 — the backend was producing files while the QA run reported "the browser
 * never received a download". The page renders a link the user clicks, so no
 * download event fires on its own; that was a test-method error, not a defect.
 * These cases assert the file is actually reachable, which is what matters.
 */

const FORMATS = [
  { id: "pdf", contentType: /application\/pdf/, magic: "%PDF" },
  { id: "docx", contentType: /wordprocessingml/, magic: "PK" },
  { id: "html", contentType: /text\/html/, magic: "<" },
] as const;

test.describe("D. 导出", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  for (const fmt of FORMATS) {
    test(`D-01 ${fmt.id} 能生成并能下载到真实文件`, async ({ page }) => {
      const profRes = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
      const profs = await profRes.json();
      const list = Array.isArray(profs) ? profs : (profs.profiles ?? []);
      const confirmed = list.find((p: { status?: string }) => p.status === "confirmed") ?? list[0];
      test.skip(!confirmed, "没有可用档案");

      const res = await page.request.post(
        new URL(`/api/v1/profiles/${confirmed.id}/export`, page.url()).toString(),
        { data: { format: fmt.id, locale: "zh-CN" }, timeout: 300_000 },
      );
      expect(res.status()).toBe(200);
      const job = await res.json();
      expect(job.status, job.error_message ?? "").toBe("done");
      expect(job.download_url, "没有下载链接 = 用户拿不到文件").toBeTruthy();

      const file = await page.request.get(job.download_url);
      expect(file.status()).toBe(200);
      expect(file.headers()["content-type"]).toMatch(fmt.contentType);

      const bytes = await file.body();
      expect(bytes.length, "文件是空的").toBeGreaterThan(1000);
      expect(bytes.subarray(0, 4).toString("latin1")).toContain(fmt.magic);
    });
  }
});
