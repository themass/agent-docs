import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue, seedProfileWithGap } from "./helpers";

/**
 * C-03 / C-04: evidence gaps and writing preferences.
 *
 * Both carry product rules that are easy to get subtly wrong and impossible to
 * see from a status code:
 *
 * - A metric skeleton may only offer a dimension, a unit and a blank. Pre-filling a
 *   plausible number is the failure mode: it gets accepted, reaches a real
 *   employer, and collapses in the interview. The PRD is explicit about it.
 * - At most 2 framing angles. More than that and the draft has no emphasis at all.
 */

async function confirmedProfile(page: Page): Promise<{ id: string } | undefined> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  return list.find((p: { status?: string }) => p.status === "confirmed") ?? list[0];
}

test.describe("C. 证据补全与写作偏好", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("C-03 指标句式只有维度和空位，永不预填数值", async ({ page }) => {
    const prof = requireValue(await confirmedProfile(page), "没有可用档案");

    const res = await page.request.get(
      new URL(`/api/v1/profiles/${prof.id}/evidence-gaps`, page.url()).toString(),
    );
    expect(res.status(), "证据缺口接口报错").toBe(200);
    const data = await res.json();
    const gaps = data.gaps ?? data.items ?? [];
    expect(Array.isArray(gaps)).toBe(true);

    const withMetrics = gaps.filter(
      (g: { metrics?: unknown[] }) => Array.isArray(g.metrics) && g.metrics.length > 0,
    );
    for (const gap of withMetrics) {
      for (const m of gap.metrics as Array<Record<string, unknown>>) {
        const skeleton = String(m.skeleton ?? m.template ?? m.text ?? "");
        if (!skeleton) continue;
        // A skeleton must contain a blank to fill. A number already in it means the
        // user is invited to accept a figure they never measured.
        expect(skeleton, `指标句式没有任何空位：${skeleton}`).toMatch(/_{2,}|\{\{|＿/);
        // And no digit sequence that looks like a filled-in result.
        const digits = skeleton.match(/\d+/g) ?? [];
        for (const d of digits) {
          // Units and dimension hints legitimately contain no digits; anything >2
          // digits in a blank skeleton is a value that came from somewhere.
          expect(
            d.length,
            `指标句式里出现了疑似预填的数值 ${d}：${skeleton}`,
          ).toBeLessThanOrEqual(2);
        }
      }
    }
  });

  test("C-04 写作偏好可读可写，角度上限是 2", async ({ page }) => {
    const prof = requireValue(await confirmedProfile(page), "没有可用档案");
    const url = new URL(`/api/v1/profiles/${prof.id}/writing-options`, page.url()).toString();

    const res = await page.request.get(url);
    expect(res.status()).toBe(200);
    const opts = await res.json();
    expect(opts.role_family).toBeTruthy();
    expect(opts.max_emphases, "角度上限必须是 2").toBe(2);
    expect(Array.isArray(opts.framing_emphases)).toBe(true);
    expect(opts.framing_emphases.length, "在用的角度不应超过上限").toBeLessThanOrEqual(
      opts.max_emphases,
    );

    // The field is `id`, not `key`. Reading the wrong name produced `[undefined]`,
    // which serialized away and came back as a 422 — a test bug that looked exactly
    // like a validation defect. Checked against schemas/writing_options.py.
    const presets: string[] = (opts.presets ?? []).map((p: { id: string }) => p.id);
    expect(presets.length, "没有可选的包装角度").toBeGreaterThan(0);

    // Sending more than the cap is *capped*, not refused: `writing_options_service`
    // stores `kept[:MAX_EMPHASES]` deliberately. My first version asserted a 4xx and
    // was wrong about the product — but the property that actually matters still
    // holds and is worth pinning: whatever is stored must never exceed the cap, or
    // the UI would show a choice that is not in force.
    if (presets.length >= 3) {
      const tooMany = await page.request.put(url, {
        data: { framing_emphases: presets.slice(0, 3) },
      });
      expect(tooMany.status(), "提交超限角度返回了 5xx").toBeLessThan(500);
      if (tooMany.status() === 200) {
        const kept = (await tooMany.json()).framing_emphases ?? [];
        expect(
          kept.length,
          `提交 3 个角度后保存了 ${kept.length} 个，超过上限 ${opts.max_emphases}`,
        ).toBeLessThanOrEqual(opts.max_emphases);
      }
    }

    // One angle round-trips.
    if (presets.length >= 1) {
      const put = await page.request.put(url, { data: { framing_emphases: [presets[0]] } });
      expect(put.status()).toBe(200);
      const after = await (await page.request.get(url)).json();
      expect(after.framing_emphases, "写入的角度没有生效").toContain(presets[0]);
      expect(after.framing_explicit, "写入后应标记为用户显式选择").toBe(true);
    }
  });

  test("C-03b 证据答案能回填并出现在下一次缺口查询里", async ({ page }) => {
    const prof = requireValue(await seedProfileWithGap(page), "无法造出带缺口的档案");

    const gapUrl = new URL(`/api/v1/profiles/${prof.id}/evidence-gaps`, page.url()).toString();
    const gapsRes = await page.request.get(gapUrl);
    test.skip(gapsRes.status() !== 200, "缺口接口不可用");
    const gaps = (await gapsRes.json()).gaps ?? [];
    expect(gaps.length, "刚写入「多项」却没有产生缺口，缺口规则变了").toBeGreaterThan(0);

    const target = gaps[0];
    const answer = `e2e-evidence-${Date.now()}`;
    const post = await page.request.post(
      new URL(`/api/v1/profiles/${prof.id}/evidence-answers`, page.url()).toString(),
      {
        data: {
          answers: [
            {
              field_path: target.field_path,
              question: target.question,
              answer,
              kind: target.kind,
            },
          ],
        },
      },
    );
    expect(post.status(), "提交证据答案失败").toBeLessThan(400);

    // The gap must now carry the answer back. Without this the user is asked the
    // same question forever, which is the loop the mirror-as-evidence design exists
    // to prevent.
    const again = (await (await page.request.get(gapUrl)).json()).gaps ?? [];
    const same = again.find(
      (g: { field_path: string; question: string }) =>
        g.field_path === target.field_path && g.question === target.question,
    );
    if (same) {
      expect(same.answer, "答案写进去了但缺口没有回显它").toBe(answer);
    }
  });
});
