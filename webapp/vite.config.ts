import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/*.spec.ts", "src/**/*.spec.tsx"],
    exclude: ["tests/**/*.spec.ts"],
    environment: "jsdom",
    globals: true,
    // Calendar expectations use this explicit zone on Windows and Linux CI.
    env: { TZ: "Asia/Yekaterinburg" },
    setupFiles: "./src/test/setup.ts",
    testTimeout: 20000
  }
});
