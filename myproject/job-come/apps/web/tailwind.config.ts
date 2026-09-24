import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#d9e6ff",
          200: "#bcd4ff",
          500: "#3b6fd9",
          600: "#2f5bb8",
          700: "#264a96",
          900: "#1a2f5c",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f4f6fb",
          border: "#e2e8f0",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06)",
        panel: "0 4px 32px rgba(30, 58, 95, 0.08)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
