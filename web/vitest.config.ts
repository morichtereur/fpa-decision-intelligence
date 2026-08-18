import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

/**
 * Component tests.
 *
 * Every rendering bug this project has had — exposure bars that never drew, a
 * driver tree whose input column was empty, a waterfall whose closing bar
 * collapsed to nothing, one client's disclaimers shown under another's name —
 * passed the production build, passed `tsc`, and passed the whole Python
 * suite. They were only ever caught by looking at the rendered output. These
 * tests look at it automatically.
 *
 * jsdom rather than a real browser: all four defects are visible in the
 * rendered markup and inline styles, so a browser would add minutes to CI to
 * catch nothing extra.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.tsx"],
    css: true,
  },
});
