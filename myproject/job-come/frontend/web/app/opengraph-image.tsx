import { ImageResponse } from "next/og";

import { PRODUCT_NAME_EN } from "@/lib/brand";
import { SITE_URL } from "@/lib/seo/site";

/**
 * Default link-preview card, inherited by every page that does not define its own
 * (Next resolves the nearest collocated `opengraph-image`, so a page-specific card
 * added later overrides this one without touching it).
 *
 * The rendered text is deliberately Latin-only. `next/og` ships a Noto Sans subset
 * with no CJK glyphs, so Chinese here draws tofu boxes in every shared link. Getting
 * Chinese into the image would mean bundling a multi-megabyte CJK font or fetching one
 * at build time on the deploy box — not worth it for a card whose job is brand
 * recognition plus one phrase. The Chinese copy still reaches readers through
 * `og:title` / `og:description`, which are text, not pixels.
 */
export const alt = "舟卡 JobCome — AI 简历优化";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 96px",
          background: "linear-gradient(135deg, #312e81 0%, #4f46e5 100%)",
          color: "white",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              display: "flex",
              width: 72,
              height: 72,
              borderRadius: 16,
              background: "rgba(255,255,255,0.14)",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              fontWeight: 700,
            }}
          >
            JC
          </div>
          <div style={{ display: "flex", fontSize: 40, fontWeight: 700 }}>
            {PRODUCT_NAME_EN}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 68,
            fontWeight: 700,
            marginTop: 40,
            letterSpacing: -1,
          }}
        >
          AI Resume Optimization
        </div>
        <div style={{ display: "flex", fontSize: 30, marginTop: 24, opacity: 0.85 }}>
          diagnose · rewrite per job description · mock interview
        </div>
        <div style={{ display: "flex", fontSize: 24, marginTop: 48, opacity: 0.6 }}>
          {SITE_URL.replace(/^https?:\/\//, "")}
        </div>
      </div>
    ),
    { ...size }
  );
}
