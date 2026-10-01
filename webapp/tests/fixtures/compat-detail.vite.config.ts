import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

export default defineConfig({
  root: resolve(import.meta.dirname),
  base: "/__compat_assets/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: resolve(import.meta.dirname, "../../.e2e-compat"),
    emptyOutDir: true,
    rollupOptions: { input: resolve(import.meta.dirname, "compat-detail.html") },
  },
});
