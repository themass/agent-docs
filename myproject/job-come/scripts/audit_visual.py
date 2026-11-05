#!/usr/bin/env python3
"""Mechanical visual audit of the built frontend: contrast, type scale, dead classes.

Catches the class of design-system regression that neither `tsc --noEmit` nor
`npm run build` can see, because the breakage only exists in computed style:

  - text below the WCAG 1.4.3 contrast floor (4.5:1 body, 3:1 large/bold);
  - Tailwind classes that do not exist and therefore silently do nothing;
  - unintended horizontal overflow;
  - type-scale sprawl (a reviewable inventory, not a hard failure).

Disabled controls are exempt per WCAG 1.4.3, so they are reported separately and
never fail the run.

Usage (frontend must already be serving a production build):
    python scripts/audit_visual.py --base http://127.0.0.1:3000
    python scripts/audit_visual.py --base http://127.0.0.1:3000 --paths /jobs /bank
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from lib.bootstrap import ensure_project_env

ensure_project_env()

from playwright.async_api import async_playwright  # noqa: E402

DEFAULT_PATHS = [
    "/auth/login",
    "/auth/register",
    "/jobs",
    "/campaign",
    "/applications",
    "/bank",
    "/interviews",
    "/resume-agent",
    "/settings/account",
]

# Tailwind 3 ships only these fractional spacing steps. Anything else is a no-op.
VALID_HALF_STEPS = {"0.5", "1.5", "2.5", "3.5"}

COLLECT_JS = r"""
() => {
  const out = {fonts: {}, colors: {}, halfSteps: [], tiny: [], lowContrast: [], overflow: []};
  const bump = (o, k) => { o[k] = (o[k] || 0) + 1; };
  const parse = (c) => {
    const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
  };
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  // Walk up for the first opaque-enough background: that is what the eye sees behind text.
  const effectiveBg = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c[3] > 0.85) return c;
      n = n.parentElement;
    }
    return [255, 255, 255, 1];
  };
  const isDisabled = (el) => {
    let n = el;
    while (n && n !== document.body) {
      if (n.disabled === true || n.getAttribute?.('aria-disabled') === 'true') return true;
      n = n.parentElement;
    }
    return false;
  };

  for (const el of document.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;

    const cls = typeof el.className === 'string' ? el.className : '';
    for (const m of cls.matchAll(/\b([a-z]+(?:-[a-z]+)*)-(\d+\.5)\b/g)) {
      out.halfSteps.push({cls: m[0], step: m[2]});
    }

    bump(out.fonts, s.fontSize);
    bump(out.colors, s.color);

    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0
        && s.overflowX !== 'auto' && s.overflowX !== 'scroll' && s.overflowX !== 'hidden') {
      out.overflow.push({tag: el.tagName, cls: cls.slice(0, 70), sw: el.scrollWidth, cw: el.clientWidth});
    }

    const text = (el.textContent || '').trim();
    if (el.children.length !== 0 || text.length < 2) continue;

    const px = parseFloat(s.fontSize);
    if (px < 11) out.tiny.push({px, text: text.slice(0, 40)});

    const fg = parse(s.color);
    if (!fg || fg[3] <= 0.5) continue;
    const L1 = lum(fg), L2 = lum(effectiveBg(el));
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const bold = parseInt(s.fontWeight, 10) >= 700;
    const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3.0 : 4.5;
    if (ratio < need) {
      out.lowContrast.push({
        ratio: +ratio.toFixed(2), need, px, color: s.color,
        disabled: isDisabled(el), text: text.slice(0, 45),
      });
    }
  }

  out.docOverflow = document.documentElement.scrollWidth > window.innerWidth + 1
    ? {scrollWidth: document.documentElement.scrollWidth, viewport: window.innerWidth}
    : null;
  return out;
}
"""


async def audit(base: str, paths: list[str], width: int) -> int:
    fonts: collections.Counter[str] = collections.Counter()
    colors: collections.Counter[str] = collections.Counter()
    failures = 0
    exempt_total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": 950})
            for path in paths:
                try:
                    await page.goto(base.rstrip("/") + path, wait_until="networkidle", timeout=25_000)
                except Exception as exc:  # noqa: BLE001 - report and keep auditing
                    print(f"\n=== {path}\n  NAVIGATION FAILED: {type(exc).__name__}")
                    failures += 1
                    continue
                await page.wait_for_timeout(800)
                r = await page.evaluate(COLLECT_JS)

                fonts.update(r["fonts"])
                colors.update(r["colors"])
                print(f"\n=== {path}")
                problems = 0

                dead = sorted({h["cls"] for h in r["halfSteps"] if h["step"] not in VALID_HALF_STEPS})
                if dead:
                    print(f"  DEAD CLASSES (no such Tailwind step, silently ignored): {dead}")
                    problems += 1

                if r["docOverflow"]:
                    print(f"  HORIZONTAL SCROLL: {r['docOverflow']}")
                    problems += 1
                for o in r["overflow"][:3]:
                    if "sr-only" in o["cls"]:
                        continue  # visually-hidden text legitimately overflows its 1px box
                    print(f"  OVERFLOW: {o}")
                    problems += 1

                if r["tiny"]:
                    print(f"  TEXT BELOW 11px ({len(r['tiny'])}): {r['tiny'][:3]}")
                    problems += 1

                enforced = [x for x in r["lowContrast"] if not x["disabled"]]
                exempt = [x for x in r["lowContrast"] if x["disabled"]]
                exempt_total += len(exempt)
                if enforced:
                    distinct: dict[tuple[str, float], dict] = {}
                    for x in enforced:
                        distinct.setdefault((x["color"], x["ratio"]), x)
                    print(f"  LOW CONTRAST: {len(enforced)} nodes, {len(distinct)} distinct")
                    for x in sorted(distinct.values(), key=lambda v: v["ratio"])[:8]:
                        print(f"     {x['ratio']}:1 (need {x['need']}) {x['px']}px "
                              f"{x['color']} :: {x['text']!r}")
                    problems += 1
                if exempt:
                    print(f"  (exempt: {len(exempt)} low-contrast node(s) inside disabled controls)")

                if problems == 0:
                    print("  clean")
                failures += problems
        finally:
            await browser.close()

    print("\n\n########## TYPE SCALE (review for sprawl) ##########")
    for size, n in sorted(fonts.items(), key=lambda kv: -float(kv[0].rstrip("px"))):
        print(f"  {size:>9}  x{n}")
    print("\n########## TEXT COLORS (top 15) ##########")
    for color, n in colors.most_common(15):
        print(f"  {color:>26}  x{n}")

    print()
    if failures:
        print(f"FAIL: {failures} visual problem group(s) across {len(paths)} page(s)")
    else:
        print(f"PASS: {len(paths)} page(s) clean "
              f"({exempt_total} WCAG-exempt disabled node(s) ignored)")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000",
                        help="origin of an already-running production build")
    parser.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    parser.add_argument("--width", type=int, default=1440)
    args = parser.parse_args()
    sys.exit(asyncio.run(audit(args.base, args.paths, args.width)))
