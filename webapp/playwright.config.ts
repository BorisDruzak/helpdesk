import { defineConfig } from "playwright/test";


const PORT = Number.parseInt(process.env.PC_CLIENT_WEBAPP_E2E_PORT ?? "4173", 10);
const BASE_URL = `http://127.0.0.1:${PORT}`;
const CI = process.env.CI === "1" || process.env.CI === "true";


export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: CI ? 1 : 0,
  reporter: [["list"]],
  expect: {
    timeout: 10_000
  },
  use: {
    baseURL: BASE_URL,
    headless: true,
    locale: "ru-RU",
    screenshot: "only-on-failure",
    trace: CI ? "on-first-retry" : "retain-on-failure",
    video: "retain-on-failure"
  },
  webServer: {
    command: `python tests/fixtures/support_fixture_server.py --port ${PORT}`,
    url: `${BASE_URL}/app/login`,
    reuseExistingServer: false,
    timeout: 120_000
  }
});
