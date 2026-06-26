#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";


const DEFAULT_BASE_URL =
  process.env.PC_CLIENT_BROWSER_BASE_URL ??
  process.env.REMOTE_SMOKE_BASE_URL ??
  "https://192.168.100.17:9443";
const DEFAULT_OUT_DIR = path.resolve("..", "artifacts", "browser_live_validation", "live-behavior-suite");
const RUSSIAN_TITLE = "pc_client — рабочие места";

const ROLE_CONFIGS = {
  requester: {
    login: process.env.PC_CLIENT_REQUESTER_LOGIN ?? process.env.PC_CLIENT_UI_REQUESTER_LOGIN ?? "requester",
    password: process.env.PC_CLIENT_REQUESTER_PASSWORD ?? process.env.PC_CLIENT_UI_REQUESTER_PASSWORD ?? "requester123",
  },
  support: {
    login: process.env.PC_CLIENT_SUPPORT_LOGIN ?? process.env.PC_CLIENT_UI_SUPPORT_LOGIN ?? "support",
    password: process.env.PC_CLIENT_SUPPORT_PASSWORD ?? process.env.PC_CLIENT_UI_SUPPORT_PASSWORD ?? "support123",
  },
  admin: {
    login: process.env.PC_CLIENT_ADMIN_LOGIN ?? process.env.PC_CLIENT_UI_ADMIN_LOGIN ?? "admin",
    password: process.env.PC_CLIENT_ADMIN_PASSWORD ?? process.env.PC_CLIENT_UI_ADMIN_PASSWORD ?? "admin123",
  },
};

const SURFACE_DEFAULT_PROBES = {
  requester: [
    { role: "requester", path: "/app/requester", expectedTextAny: ["Главная", "Кабинет пользователя"] },
  ],
  support: [
    { role: "support", path: "/app/support", expectedTextAny: ["Центр действий", "Тикеты"] },
  ],
  admin: [
    { role: "admin", path: "/app/admin", expectedTextAny: ["Рабочее место администрирования", "Администрирование"] },
  ],
  reports: [
    { role: "admin", path: "/app/reports", expectedTextAny: ["Отчёты", "Операционный отчёт"] },
  ],
};

const SCENARIO_PROBES = {
  requester_support_admin_session_switch: [
    { role: "requester", path: "/app/requester", expectedTextAny: ["Главная", "Кабинет пользователя"] },
    { role: "support", path: "/app/support", expectedTextAny: ["Центр действий"] },
  ],
  requester_support_chat_roundtrip: [
    { role: "requester", path: "/app/requester/tickets", expectedTextAny: ["Мои обращения", "Ожидают вашего решения"] },
    { role: "support", path: "/app/tickets", expectedTextAny: ["Тикеты", "Очередь тикетов"] },
  ],
  admin_publish_requester_create: [
    { role: "requester", path: "/app/requester/new", expectedTextAny: ["Категория и форма", "Сначала заполните профиль", "Нет доступной формы"] },
  ],
  real_account_device_linking: [
    { role: "admin", path: "/app/admin/registry", expectedTextAny: ["Центр регистрации и привязок", "Операционный реестр"] },
  ],
  support_queue_status_after_routing: [
    { role: "support", path: "/app/support", expectedTextAny: ["Центр действий"] },
    { role: "support", path: "/app/tickets", expectedTextAny: ["Тикеты", "Очередь тикетов"] },
  ],
  requester_support_admin_search_visibility: [
    { role: "requester", path: "/app/help", expectedTextAny: ["База знаний", "Помощь", "Поиск"] },
    { role: "support", path: "/app/tickets", expectedTextAny: ["Тикеты", "Очередь тикетов"] },
  ],
  requester_feedback_support_qa: [
    { role: "requester", path: "/app/requester/tickets", expectedTextAny: ["Мои обращения", "Ожидают вашего решения"] },
    { role: "support", path: "/app/tickets", expectedTextAny: ["Тикеты", "Очередь тикетов"] },
  ],
  admin_problem_support_link: [
    { role: "admin", path: "/app/admin/problems", expectedTextAny: ["Problem workspace", "Problem management"] },
  ],
  admin_change_approval_workflow: [
    { role: "admin", path: "/app/admin/changes", expectedTextAny: ["Рабочее место изменений", "Управление изменениями"] },
  ],
  bounded_provider_canary: [
    { role: "support", path: "/app/support", expectedTextAny: ["Центр действий"] },
  ],
  module_playbook_canary: [
    { role: "admin", path: "/app/admin/modules", expectedTextAny: ["Модули"] },
    { role: "admin", path: "/app/admin/playbooks", expectedTextAny: ["Плейбуки диагностики", "Плейбуки"] },
  ],
  non_production_remote_assist_session: [
    { role: "support", path: "/app/tickets", expectedTextAny: ["Тикеты", "Очередь тикетов"] },
  ],
  admin_support_trace_drilldown: [
    { role: "admin", path: "/app/admin/observer", expectedTextAny: ["Observer", "Operational Integrity Observer"] },
  ],
  browser_totals_against_seeded_pack: [
    { role: "admin", path: "/app/reports", expectedTextAny: ["Отчёты", "Операционный отчёт"] },
  ],
};


function parseArgs(argv) {
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    outDir: DEFAULT_OUT_DIR,
    domain: "unknown",
    scenarioKey: "",
    surface: "requester",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === "--base-url" && next) {
      options.baseUrl = next;
      index += 1;
      continue;
    }
    if (current === "--out-dir" && next) {
      options.outDir = path.resolve(next);
      index += 1;
      continue;
    }
    if (current === "--domain" && next) {
      options.domain = next;
      index += 1;
      continue;
    }
    if (current === "--scenario-key" && next) {
      options.scenarioKey = next;
      index += 1;
      continue;
    }
    if (current === "--surface" && next) {
      options.surface = next;
      index += 1;
    }
  }
  return options;
}


function sanitizeFilePart(value) {
  return String(value || "probe")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100) || "probe";
}


function probesFor(options) {
  return SCENARIO_PROBES[options.scenarioKey] ?? SURFACE_DEFAULT_PROBES[options.surface] ?? [];
}


async function ensureLoggedIn(page, probe) {
  await page.waitForLoadState("domcontentloaded");
  const loginInput = page.locator('input[name="login"], input[autocomplete="username"]').first();
  if ((await loginInput.count()) === 0) {
    await loginInput.waitFor({ state: "visible", timeout: 10_000 }).catch(() => undefined);
  }
  if ((await loginInput.count()) === 0) {
    return false;
  }

  const config = ROLE_CONFIGS[probe.role];
  if (!config) {
    throw new Error(`No browser credentials configured for role: ${probe.role}`);
  }
  await loginInput.fill(config.login);
  const passwordInput = page.locator('input[name="password"], input[type="password"]').first();
  await passwordInput.waitFor({ state: "visible", timeout: 10_000 });
  await passwordInput.fill(config.password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL((url) => !url.pathname.startsWith("/app/login"), {
    timeout: 30_000,
  });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  if (new URL(page.url()).pathname !== probe.path) {
    await page.goto(probe.path, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle").catch(() => undefined);
  }
  return true;
}


async function runProbe(browser, options, probe, index) {
  const context = await browser.newContext({
    baseURL: options.baseUrl,
    ignoreHTTPSErrors: true,
    locale: "ru-RU",
    viewport: {
      width: 1440,
      height: 1100,
    },
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(String(error));
  });

  await page.goto(probe.path, { waitUntil: "domcontentloaded" });
  const loginSubmitted = await ensureLoggedIn(page, probe);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(1000);

  const bodyText = await page.evaluate(() => document.body.innerText ?? "");
  const lang = await page.locator("html").getAttribute("lang");
  const title = await page.title();
  const expectedTextAny = probe.expectedTextAny ?? [];
  const matchedExpectedText = expectedTextAny.filter((text) => bodyText.includes(text));
  const screenshotName = [
    String(index + 1).padStart(2, "0"),
    sanitizeFilePart(options.scenarioKey),
    sanitizeFilePart(probe.role),
    sanitizeFilePart(probe.path),
  ].join("-") + ".png";
  const screenshotPath = path.join(options.outDir, screenshotName);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await context.close();

  const errors = [];
  if (lang !== "ru") {
    errors.push(`html lang must be ru, got ${lang}`);
  }
  if (title !== RUSSIAN_TITLE) {
    errors.push(`title must be ${RUSSIAN_TITLE}, got ${title}`);
  }
  if (expectedTextAny.length > 0 && matchedExpectedText.length === 0) {
    errors.push(`none of expected text markers were visible: ${expectedTextAny.join(", ")}`);
  }
  if (bodyText.includes("Вход в рабочие места") || bodyText.includes("Добро пожаловать")) {
    errors.push("login page is still visible after authentication attempt");
  }
  if (consoleErrors.length > 0) {
    errors.push(`console errors: ${consoleErrors.length}`);
  }
  if (pageErrors.length > 0) {
    errors.push(`page errors: ${pageErrors.length}`);
  }

  return {
    role: probe.role,
    path: probe.path,
    url: page.url(),
    title,
    lang,
    loginSubmitted,
    expectedTextAny,
    matchedExpectedText,
    screenshot: path.relative(options.outDir, screenshotPath),
    consoleErrors,
    pageErrors,
    bodySnippet: bodyText.slice(0, 3000),
    status: errors.length === 0 ? "pass" : "fail",
    errors,
  };
}


async function main() {
  const options = parseArgs(process.argv.slice(2));
  const probes = probesFor(options);
  if (probes.length === 0) {
    throw new Error(`No probes configured for scenario=${options.scenarioKey} surface=${options.surface}`);
  }
  await fs.mkdir(options.outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (let index = 0; index < probes.length; index += 1) {
      results.push(await runProbe(browser, options, probes[index], index));
    }
  } finally {
    await browser.close();
  }

  const summary = {
    schema: "pc_client.live_browser_scenario.v1",
    baseUrl: options.baseUrl,
    domain: options.domain,
    scenarioKey: options.scenarioKey,
    surface: options.surface,
    status: results.every((result) => result.status === "pass") ? "pass" : "fail",
    probes: results,
  };
  await fs.writeFile(path.join(options.outDir, "browser-report.json"), JSON.stringify(summary, null, 2), "utf-8");
  console.log(JSON.stringify(summary, null, 2));
  if (summary.status !== "pass") {
    process.exitCode = 1;
  }
}


await main();
