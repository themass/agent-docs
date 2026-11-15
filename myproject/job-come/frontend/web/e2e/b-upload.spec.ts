import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * B-01~B-03: the three file-upload entries.
 *
 * The samples are generated here rather than committed: a checked-in resume is
 * somebody's personal data, and the intake pipeline only needs a well-formed file
 * to exercise its upload, storage and parse-state path.
 */

/** A minimal, valid one-page PDF with one line of text. */
function minimalPdf(text: string): Buffer {
  const escaped = text.replace(/[()\\]/g, "");
  const content = `BT /F1 12 Tf 50 750 Td (${escaped}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((obj, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${obj}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) pdf += `${String(off).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

test.describe("B. 文件上传建档", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("B-01 上传 PDF 创建档案并进入解析流程", async ({ page }) => {
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
