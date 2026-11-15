import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/**
 * Node-environment unit tests for pure logic (turn assembly, display items).
 *
 * No DOM environment on purpose: everything worth pinning here is derived state —
 * "how many waiting indicators does this turn produce", "which items become one
 * turn" — and testing that through a renderer would assert on class names instead
 * of on the answer. Anything that genuinely needs a browser belongs in the
 * Playwright suite described in docs/operations/QA-FULL-VERIFICATION.md.
 */
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    include: ["**/*.test.ts"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
