import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/*.spec.ts", "src/**/*.spec.tsx"],
    exclude: ["tests/**/*.spec.ts"],
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts"
  }
});
