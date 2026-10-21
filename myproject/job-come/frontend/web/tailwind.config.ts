import type { Config } from "tailwindcss";

/**
 * JC design tokens.
 *
 * Single source of truth for type scale, colour roles, radius and elevation.
 * Rationale and usage rules live in `docs/architecture/TECH-DESIGN-SYSTEM.md`.
 *
 * Two deliberate departures from Tailwind defaults:
 *
 * 1. The type scale is re-based. Defaults assume a marketing page; JC is a dense
 *    work tool, so every step carries an explicit line-height tuned for CJK text
 *    (which needs more leading than Latin at the same size).
 * 2. `xs`/`sm`/`base` are *larger* than they look in the raw numbers because the
 *    codebase previously leaned on `text-[10px]`/`text-[11px]` arbitrary values.
 *    Those are mapped onto this scale so density is decided here, not per-file.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontSize: {
        // Badges, counters, field paths. Never body copy.
        micro: ["0.6875rem", { lineHeight: "1.45", letterSpacing: "0.01em" }],
        // Meta lines, helper text, table cells.
        xs: ["0.78125rem", { lineHeight: "1.5" }],
        // Secondary body, control labels. The workhorse for dense UI.
        sm: ["0.84375rem", { lineHeight: "1.6" }],
        // Primary body copy. Anything the user reads to understand something.
        base: ["0.9375rem", { lineHeight: "1.65" }],
        lg: ["1.0625rem", { lineHeight: "1.5", letterSpacing: "-0.005em" }],
        xl: ["1.25rem", { lineHeight: "1.4", letterSpacing: "-0.012em" }],
        "2xl": ["1.5rem", { lineHeight: "1.3", letterSpacing: "-0.018em" }],
        "3xl": ["1.875rem", { lineHeight: "1.22", letterSpacing: "-0.022em" }],
        "4xl": ["2.375rem", { lineHeight: "1.12", letterSpacing: "-0.028em" }],
      },
      colors: {
        // Accent. Indigo rather than the previous corporate blue: more chroma,
        // reads as current, still serious enough for a career product.
        brand: {
          50: "#f2f3ff",
          100: "#e5e7ff",
          200: "#cdd0fe",
          300: "#abaffc",
          400: "#8b87f8",
          500: "#6f63f1",
          600: "#5b46e5",
          700: "#4c37c9",
          800: "#3f30a2",
          900: "#352d80",
        },
        // Neutrals carry a slight cool-warm balance so large grey areas do not
        // look like a 2012 admin panel. Used via `ink-*` for text.
        // ink-400 and lighter are DECORATIVE ONLY (placeholders, disabled text,
        // icons, dividers). They do not reach 4.5:1 on any surface and must never
        // carry text the user has to read. ink-500 is the lightest readable text:
        // it clears 4.5:1 on white, surface-muted (ink-50) and ink-100.
        ink: {
          50: "#f7f8fa",
          100: "#eef0f4",
          200: "#dfe2e9",
          300: "#c4c9d4",
          400: "#929aab",
          500: "#616979",
          600: "#4e5564",
          700: "#3a4150",
          800: "#272d3a",
          900: "#161b26",
        },
        surface: {
          DEFAULT: "#ffffff",
          raised: "#ffffff",
          sunken: "#f7f8fa",
          muted: "#eef0f4",
          border: "#e4e7ee",
          "border-strong": "#d2d7e1",
        },
        success: {
          50: "#ecfdf4",
          100: "#d2f9e3",
          200: "#a7f0ca",
          600: "#0d9f6e",
          700: "#0a7f59",
          900: "#064e3b",
        },
        warn: {
          50: "#fffaeb",
          100: "#fef0c7",
          200: "#fde38a",
          600: "#d9960a",
          700: "#b27208",
          900: "#7a4d06",
        },
        danger: {
          50: "#fef3f2",
          100: "#fee4e2",
          200: "#fecdc9",
          600: "#dc3b2c",
          700: "#b92c20",
          900: "#7f1d17",
        },
      },
      borderRadius: {
        // A 4-step ladder. Controls use `md`, cards `xl`, panels `2xl`.
        md: "0.5rem",
        lg: "0.625rem",
        xl: "0.875rem",
        "2xl": "1.125rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        // Layered, low-opacity elevation. Replaces the previous habit of drawing
        // a 1px border around everything, which is what reads as "old".
        xs: "0 1px 2px rgba(22, 27, 38, 0.05)",
        sm: "0 1px 2px rgba(22, 27, 38, 0.06), 0 1px 3px rgba(22, 27, 38, 0.04)",
        card: "0 1px 2px rgba(22, 27, 38, 0.04), 0 4px 12px -2px rgba(22, 27, 38, 0.06)",
        raised:
          "0 1px 2px rgba(22, 27, 38, 0.05), 0 8px 20px -4px rgba(22, 27, 38, 0.08)",
        panel:
          "0 2px 4px rgba(22, 27, 38, 0.04), 0 16px 40px -8px rgba(22, 27, 38, 0.12)",
        pop: "0 8px 16px -4px rgba(22, 27, 38, 0.1), 0 24px 48px -12px rgba(22, 27, 38, 0.18)",
        // Accent glow for the primary action only.
        brand: "0 1px 2px rgba(76, 55, 201, 0.2), 0 6px 16px -4px rgba(91, 70, 229, 0.35)",
      },
      spacing: {
        // Named rhythm steps for page/section composition.
        gutter: "1.25rem",
        section: "1.5rem",
      },
      maxWidth: {
        shell: "1680px",
        prose: "68ch",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      transitionTimingFunction: {
        // Standard easing for UI motion; `out` for enter, `spring` for emphasis.
        out: "cubic-bezier(0.16, 1, 0.3, 1)",
        spring: "cubic-bezier(0.34, 1.4, 0.64, 1)",
      },
      transitionDuration: {
        fast: "120ms",
        DEFAULT: "180ms",
        slow: "280ms",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        // The collapsed rail's attention cue. A short nudge with a long pause:
        // the motion has to be noticeable once and then stay out of the way,
        // because it sits next to a document the user is reading.
        "nudge-x": {
          "0%, 72%, 100%": { transform: "translateX(0)" },
          "80%": { transform: "translateX(-3px)" },
          "88%": { transform: "translateX(-1px)" },
        },
        "agent-think": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(0.94)", opacity: "0.92" },
        },
        // Thinking-dots bounce. Intentionally a bigger vertical throw than
        // Tailwind's stock `animate-bounce` (which is sized as a % of the
        // element's own box — invisible at 3-4px) so the "still working" cue
        // reads clearly even at dot scale.
        "think-dot": {
          "0%, 80%, 100%": { transform: "translateY(0)" },
          "40%": { transform: "translateY(-5px)" },
        },
        // Floating feedback envelope's idle cue: a small hop, not a shake —
        // it sits over page content indefinitely, so the motion has to read
        // as "alive, optional to notice" rather than demand attention.
        "icon-bounce": {
          "0%, 78%, 100%": { transform: "translateY(0)" },
          "85%": { transform: "translateY(-4px)" },
          "92%": { transform: "translateY(0)" },
          "96%": { transform: "translateY(-2px)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-up": "fade-up 220ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "scale-in": "scale-in 160ms cubic-bezier(0.16, 1, 0.3, 1) both",
        "nudge-x": "nudge-x 3.2s cubic-bezier(0.16, 1, 0.3, 1) infinite",
        "agent-think": "agent-think 1.6s cubic-bezier(0.16, 1, 0.3, 1) infinite",
        "think-dot": "think-dot 1.1s ease-in-out infinite",
        "icon-bounce": "icon-bounce 4.5s cubic-bezier(0.34, 1.4, 0.64, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
