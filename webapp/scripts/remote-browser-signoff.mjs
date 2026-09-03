#!/usr/bin/env node

import fs from "node:fs/promises";
import http from "node:http";
import https from "node:https";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { chromium } from "playwright";


const DEFAULT_BASE_URL =
  process.env.PC_CLIENT_BROWSER_BASE_URL ??
  process.env.REMOTE_SMOKE_BASE_URL ??
  "https://example.test:9443";
const DEFAULT_LOGIN = process.env.PC_CLIENT_UI_LOGIN ?? "admin";
const DEFAULT_PASSWORD = process.env.PC_CLIENT_UI_PASSWORD ?? "admin123";
const DEFAULT_OUT_DIR = path.resolve("..", "artifacts", "browser_checks", "live-webapp-signoff");
const DEFAULT_EXPECT_ROUTE_MODE = "webapp";

const LOGIN_HEADING = "Вход в рабочие места";
const ADMIN_HEADING = "Центр администрирования";
const SUPPORT_HEADING = "Центр действий";
const RUSSIAN_TITLE = "pc_client — рабочие места";

const ADMIN_REQUIRED_TEXT = [
  "Устройства и агенты",
  "Каталог и заявки",
  "База знаний",
  "Автоматизация",
  "Управление сервисом",
  "Система",
];

const SUPPORT_REQUIRED_TEXT = [
  "Тикеты",
  "База знаний",
  "Отчёты",
  "Настройки",
];

export const RETIRED_SHELL_REDIRECTS = [
  { path: "/login", expectedLocation: "/app/login" },
  { path: "/admin", expectedLocation: "/app/admin" },
  { path: "/support", expectedLocation: "/app/support" },
  { path: "/help", expectedLocation: "/app/help" },
  { path: "/ticket.html", expectedLocation: "/app/ticket" },
  { path: "/ticket/T-100", expectedLocation: "/app/ticket/T-100" },
  { path: "/login?legacy=1", expectedLocation: "/app/login" },
  { path: "/admin?legacy=1", expectedLocation: "/app/admin" },
  { path: "/support?legacy=1", expectedLocation: "/app/support" },
  { path: "/help?legacy=1", expectedLocation: "/app/help" },
  { path: "/ticket.html?legacy=1", expectedLocation: "/app/ticket" },
  { path: "/ticket/T-100?legacy=1", expectedLocation: "/app/ticket/T-100" },
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
  return entry.status === 308 && entry.location === expectedLocation;
}


export function redirectsMatchRetiredShellContract(redirects) {
  return redirects.length === RETIRED_SHELL_REDIRECTS.length && redirects.every((entry, index) =>
    matchesExpectedLocation(entry, RETIRED_SHELL_REDIRECTS[index].expectedLocation)
  );
}


async function collectPageState(page, pageName, expectedHeading, requiredText) {
  await page.waitForTimeout(1500);
  await sweepPage(page);

  const bodyText = await page.evaluate(() => document.body.innerText ?? "");
  const lang = await page.locator("html").getAttribute("lang");
  const title = await page.title();
  const missingText = requiredText.filter((text) => !bodyText.includes(text));
  const headingVisible = await page
    .getByRole("heading", { name: expectedHeading, exact: true })
    .first()
    .isVisible({ timeout: 1000 })
    .catch(() => false);

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
  const targetUrl = new URL(pathName, baseUrl);
  const transport = targetUrl.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const request = transport.request(targetUrl, {
      method: "GET",
      rejectUnauthorized: false,
    }, (response) => {
      response.resume();
      response.on("end", () => {
        resolve({
          path: pathName,
          status: response.statusCode,
          location: response.headers.location ?? null,
        });
      });
    });
    request.on("error", reject);
    request.end();
  });
}


async function collectCutoverChecks(baseUrl) {
  const retiredShellRedirects = [];
  for (const entry of RETIRED_SHELL_REDIRECTS) {
    retiredShellRedirects.push(await inspectRedirect(baseUrl, entry.path));
  }

  return {
    retiredShellRedirects,
  };
}


async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.expectRouteMode !== "webapp") {
    throw new Error(`Unsupported --expect-route-mode: ${options.expectRouteMode}`);
  }
  await fs.mkdir(options.outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    baseURL: options.baseUrl,
    ignoreHTTPSErrors: true,
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
  const routeMode = redirectsMatchRetiredShellContract(cutoverChecks.retiredShellRedirects) ? "webapp" : "mixed";

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
    routeMode !== options.expectRouteMode ||
    sessionPayload.status !== 200 ||
    sessionData?.default_workspace !== "admin" ||
    !Array.isArray(sessionData?.available_workspaces) ||
    sessionData.available_workspaces.includes("admin") !== true ||
    new URL(defaultRouteUrl).pathname !== "/app/admin" ||
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


if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
