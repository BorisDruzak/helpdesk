#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";


const DEFAULT_BASE_URL = "http://192.168.100.17:8666";
const DEFAULT_LOGIN = process.env.PC_CLIENT_UI_LOGIN ?? "admin";
const DEFAULT_PASSWORD = process.env.PC_CLIENT_UI_PASSWORD ?? "admin123";
const DEFAULT_OUT_DIR = path.resolve("..", "artifacts", "browser_checks", "live-webapp-signoff");
const DEFAULT_EXPECT_ROUTE_MODE = "auto";

const LOGIN_HEADING = "Вход в рабочие места";
const ADMIN_HEADING = "Агенты";
const SUPPORT_HEADING = "Тикеты";
const RUSSIAN_TITLE = "pc_client — рабочие места";

const ADMIN_REQUIRED_TEXT = [
  "Инвентарь устройств",
  "Подключения",
  "Токены",
  "Rollout",
  "Плейбуки",
  "Observer"
];

const SUPPORT_REQUIRED_TEXT = [
  "Рабочая панель",
  "Список тикетов",
  "Видимых тикетов",
  "Все статусы"
];

const CUTOVER_REDIRECTS = [
  { path: "/login", expectedLocation: "/app/login" },
  { path: "/admin", expectedLocation: "/app/admin" },
  { path: "/support", expectedLocation: "/app/support" },
];

const LEGACY_DEFAULT_REDIRECTS = [
  { path: "/login", expectedPrefix: "/login?_shell=" },
  { path: "/admin", expectedPrefix: "/admin?_shell=" },
  { path: "/support", expectedPrefix: "/support?_shell=" },
];

const LEGACY_ESCAPE_REDIRECTS = [
  { path: "/login?legacy=1", expectedPrefix: "/login?legacy=1&_shell=" },
  { path: "/admin?legacy=1", expectedPrefix: "/admin?legacy=1&_shell=" },
  { path: "/support?legacy=1", expectedPrefix: "/support?legacy=1&_shell=" },
];


function parseArgs(argv) {
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    login: DEFAULT_LOGIN,
    password: DEFAULT_PASSWORD,
    outDir: DEFAULT_OUT_DIR,
    expectRouteMode: DEFAULT_EXPECT_ROUTE_MODE,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === "--base-url" && next) {
      options.baseUrl = next;
      index += 1;
      continue;
    }
    if (current === "--login" && next) {
      options.login = next;
      index += 1;
      continue;
    }
    if (current === "--password" && next) {
      options.password = next;
      index += 1;
      continue;
    }
    if (current === "--out-dir" && next) {
      options.outDir = path.resolve(next);
      index += 1;
      continue;
    }
    if (current === "--expect-route-mode" && next) {
      options.expectRouteMode = next;
      index += 1;
    }
  }

  return options;
}


function matchesExpectedLocation(entry, expectedLocation) {
  return entry.status === 302 && entry.location === expectedLocation;
}


function matchesExpectedPrefix(entry, expectedPrefix) {
  return entry.status === 302 && entry.location?.startsWith(expectedPrefix);
}


function resolveRouteMode(defaultRedirects) {
  const isWebappMode = defaultRedirects.every((entry, index) =>
    matchesExpectedLocation(entry, CUTOVER_REDIRECTS[index].expectedLocation)
  );
  if (isWebappMode) {
    return "webapp";
  }

  const isLegacyMode = defaultRedirects.every((entry, index) =>
    matchesExpectedPrefix(entry, LEGACY_DEFAULT_REDIRECTS[index].expectedPrefix)
  );
  if (isLegacyMode) {
    return "legacy";
  }

  return "mixed";
}


async function collectPageState(page, pageName, expectedHeading, requiredText) {
  await page.waitForTimeout(1500);
  await sweepPage(page);

  const bodyText = await page.evaluate(() => document.body.innerText ?? "");
  const lang = await page.locator("html").getAttribute("lang");
  const title = await page.title();
  const missingText = requiredText.filter((text) => !bodyText.includes(text));
  const headingVisible = bodyText.includes(expectedHeading);

  return {
    pageName,
    url: page.url(),
    lang,
    title,
    headingVisible,
    missingText,
    bodySnippet: bodyText.slice(0, 5000),
  };
}


async function sweepPage(page) {
  for (let index = 0; index < 14; index += 1) {
    await page.mouse.wheel(0, 1800);
    await page.waitForTimeout(250);
  }
  await page.mouse.wheel(0, -40_000);
  await page.waitForTimeout(300);
}


async function ensureLoggedIn(page, login, password) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1000);

  const loginInput = page.locator('input[name="login"]');
  if (await loginInput.count() === 0) {
    return;
  }

  await loginInput.fill(login);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.startsWith("/app/login"), {
    timeout: 30_000,
  });
  await page.waitForLoadState("networkidle");

  const nextBodyText = await page.evaluate(() => document.body.innerText ?? "");
  if (nextBodyText.includes(LOGIN_HEADING)) {
    throw new Error("Не удалось войти в новый webapp: форма логина осталась на месте.");
  }
}


async function captureScreenshot(page, targetPath) {
  await page.screenshot({
    path: targetPath,
    fullPage: true,
  });
}


async function inspectRedirect(baseUrl, pathName) {
  const response = await fetch(`${baseUrl}${pathName}`, {
    redirect: "manual",
  });
  return {
    path: pathName,
    status: response.status,
    location: response.headers.get("location"),
  };
}


async function collectCutoverChecks(baseUrl) {
  const defaultRedirects = [];
  for (const entry of CUTOVER_REDIRECTS) {
    defaultRedirects.push(await inspectRedirect(baseUrl, entry.path));
  }

  const legacyEscapes = [];
  for (const entry of LEGACY_ESCAPE_REDIRECTS) {
    legacyEscapes.push(await inspectRedirect(baseUrl, entry.path));
  }

  return {
    defaultRedirects,
    legacyEscapes,
  };
}


async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!["auto", "legacy", "webapp"].includes(options.expectRouteMode)) {
    throw new Error(`Unsupported --expect-route-mode: ${options.expectRouteMode}`);
  }
  await fs.mkdir(options.outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    baseURL: options.baseUrl,
    locale: "ru-RU",
    viewport: {
      width: 1600,
      height: 2200,
    },
  });

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

  await page.goto("/app/admin", { waitUntil: "domcontentloaded" });
  await ensureLoggedIn(page, options.login, options.password);
  const cutoverChecks = await collectCutoverChecks(options.baseUrl);
  const routeMode = resolveRouteMode(cutoverChecks.defaultRedirects);

  await page.goto("/app", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  const defaultRouteUrl = page.url();
  const sessionPayload = await page.evaluate(async () => {
    const response = await fetch("/api/web/session/me", {
      credentials: "same-origin",
    });
    return {
      status: response.status,
      payload: await response.json(),
    };
  });
  const sessionData = sessionPayload.payload?.data ?? null;

  await page.goto("/app/admin", { waitUntil: "networkidle" });
  const adminState = await collectPageState(page, "admin", ADMIN_HEADING, ADMIN_REQUIRED_TEXT);
  await captureScreenshot(page, path.join(options.outDir, "admin.png"));

  await page.goto("/app/support", { waitUntil: "networkidle" });
  const supportState = await collectPageState(page, "support", SUPPORT_HEADING, SUPPORT_REQUIRED_TEXT);
  await captureScreenshot(page, path.join(options.outDir, "support.png"));

  const summary = {
    baseUrl: options.baseUrl,
    expectedRouteMode: options.expectRouteMode,
    routeMode,
    defaultRouteUrl,
    cutoverChecks,
    sessionPayload,
    sessionData,
    admin: adminState,
    support: supportState,
    consoleErrors,
    pageErrors,
  };

  await fs.writeFile(
    path.join(options.outDir, "summary.json"),
    JSON.stringify(summary, null, 2),
    "utf-8",
  );

  console.log(JSON.stringify(summary, null, 2));

  const hasFailures =
    routeMode === "mixed" ||
    (options.expectRouteMode !== "auto" && routeMode !== options.expectRouteMode) ||
    cutoverChecks.legacyEscapes.some((entry, index) =>
      !matchesExpectedPrefix(entry, LEGACY_ESCAPE_REDIRECTS[index].expectedPrefix)
    ) ||
    sessionPayload.status !== 200 ||
    sessionData?.default_workspace !== "admin" ||
    !Array.isArray(sessionData?.available_workspaces) ||
    sessionData.available_workspaces.includes("admin") !== true ||
    !defaultRouteUrl.startsWith(`${options.baseUrl}/app/admin/inventory`) ||
    adminState.lang !== "ru" ||
    adminState.title !== RUSSIAN_TITLE ||
    adminState.headingVisible !== true ||
    adminState.missingText.length > 0 ||
    supportState.lang !== "ru" ||
    supportState.title !== RUSSIAN_TITLE ||
    supportState.headingVisible !== true ||
    supportState.missingText.length > 0 ||
    consoleErrors.length > 0 ||
    pageErrors.length > 0;

  await browser.close();

  if (hasFailures) {
    process.exitCode = 1;
  }
}


await main();
