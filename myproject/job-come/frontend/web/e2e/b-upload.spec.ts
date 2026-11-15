import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { minimalDocx, minimalPdf } from "./fixtures";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * B-01~B-03: the three file-upload entries.
 *
 * The samples are generated here rather than committed: a checked-in resume is
 * somebody's personal data, and the intake pipeline only needs a well-formed file
 * to exercise its upload, storage and parse-state path.
 */

test.describe("B. 文件上传建档", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  /**
   * Point the account at a fresh draft before an upload case.
   *
   * `POST /profiles/upload` and `/from-text` attach to the currently active profile
   * instead of always creating one. An earlier suite left a *confirmed* profile
   * active, so these cases saw `status=confirmed` where they assert `draft` — a
   * fixture-state failure reported as a product regression. Resetting first makes
   * the precondition explicit rather than incidental.
   */
  async function activateFreshDraft(page: Page): Promise<void> {
    const created = await page.request.post(
      new URL("/api/v1/profiles", page.url()).toString(),
      { data: { name: `e2e-upload-${Date.now()}` } },
    );
    if (created.status() >= 400) return;
    const prof = await created.json();
    await page.request.post(
      new URL(`/api/v1/profiles/${prof.id}/activate`, page.url()).toString(),
    );
  }

  test("B-01 上传 PDF 创建档案并进入解析流程", async ({ page }) => {
    await activateFreshDraft(page);
    const pdf = minimalPdf("Zhang San Backend Engineer Example Technology Co 2021-2024");
    const res = await page.request.post(new URL("/api/v1/profiles/upload", page.url()).toString(), {
      multipart: {
        file: { name: "e2e-resume.pdf", mimeType: "application/pdf", buffer: pdf },
      },
      timeout: 180_000,
    });

    expect(res.status(), "上传接口报错").toBeLessThan(400);
    const prof = await res.json();
    expect(prof.id, "没有返回档案 id").toBeTruthy();
    expect(prof.status, "新上传的档案必须是草稿").toBe("draft");
    // A source row is what makes parsing observable; without it the UI has nothing
    // to show progress on and the profile never leaves draft.
    const sources = prof.sources ?? [];
    expect(sources.length, "上传后没有解析来源记录").toBeGreaterThan(0);
    expect(sources[0].parse_status, "解析状态不存在").toBeTruthy();
  });

  test("B-02 上传 DOCX 同样建档案并进入解析", async ({ page }) => {
    await activateFreshDraft(page);
    // Word is the other format a real user has. The extractor is a different code
    // path from the PDF one, so a passing PDF says nothing about this.
    const docx = minimalDocx(
      "张三 后端工程师 2021-2024 示例科技 负责订单系统 P99 从 800ms 降到 120ms",
    );
    const res = await page.request.post(new URL("/api/v1/profiles/upload", page.url()).toString(), {
      multipart: {
        file: {
          name: "e2e-resume.docx",
          mimeType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          buffer: docx,
        },
      },
      timeout: 180_000,
    });

    expect(res.status(), "上传 DOCX 报错").toBeLessThan(400);
    const prof = await res.json();
    expect(prof.status).toBe("draft");
    const sources = prof.sources ?? [];
    expect(sources.length, "DOCX 上传后没有解析来源记录").toBeGreaterThan(0);
  });

  test("B-03 非简历文件被拒而不是静默接受", async ({ page }) => {
    const res = await page.request.post(new URL("/api/v1/profiles/upload", page.url()).toString(), {
      multipart: {
        file: {
          name: "not-a-resume.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("this is not a resume"),
        },
      },
    });
    // Either refused outright, or accepted as a source and left for the parser to
    // reject. What must not happen is a 500.
    expect(res.status(), "上传不支持的类型返回了 5xx").toBeLessThan(500);
  });

  test("B-04b 粘贴文本达到 80 字能解析", async ({ page }) => {
    await activateFreshDraft(page);
    const text =
      "张三，后端工程师，2021 年至 2024 年在示例科技负责订单系统，" +
      "主导把接口 P99 从 800ms 降到 120ms，日常使用 Go 和 PostgreSQL，" +
      "负责过日均千万级请求的服务治理与容量规划。";
    expect(text.length, "样本本身不足 80 字，测试会误报").toBeGreaterThan(80);

    const res = await page.request.post(
      new URL("/api/v1/profiles/from-text", page.url()).toString(),
      { data: { raw_text: text }, timeout: 180_000 },
    );
    expect(res.status(), "足量文本没有被接受").toBeLessThan(400);
    const prof = await res.json();
    expect(prof.id).toBeTruthy();
    expect(prof.status).toBe("draft");
  });
});
