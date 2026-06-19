import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_I_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-i-profile";

const calls = {
  profileUpdate: null,
};
const consoleMessages = [];
const networkIssues = [];
let profileComplete = false;

const schema = {
  fields: [
    { key: "full_name", label: "ФИО", type: "text", required: true, visible: true, system: true, editable: true, section: "identity", order: 10 },
    {
      key: "department_id",
      label: "Подразделение",
      type: "select",
      required: true,
      visible: true,
      system: true,
      editable: true,
      section: "identity",
      order: 20,
      options: [{ value: "dept-it", label: "ИТ" }],
    },
    {
      key: "location_id",
      label: "Локация",
      type: "select",
      required: true,
      visible: true,
      system: true,
      editable: true,
      section: "identity",
      order: 30,
      options: [{ value: "loc-ekb", label: "Екатеринбург" }],
    },
    { key: "phone", label: "Телефон", type: "phone", required: true, visible: true, system: true, editable: true, section: "contact", order: 40 },
    { key: "internal_extension", label: "Внутренний номер", type: "phone", visible: true, editable: true, section: "contact", order: 50 },
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true, section: "custom", order: 60 },
    { key: "secret_note", label: "Скрытое поле", type: "text", required: false, visible: false, custom: true, editable: true, section: "custom", order: 70 },
  ],
  custom_fields: [
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true },
    { key: "secret_note", label: "Скрытое поле", type: "text", required: false, visible: false, custom: true, editable: true },
  ],
  required_fields: [
    { key: "full_name", label: "ФИО" },
    { key: "department_id", label: "Подразделение" },
    { key: "location_id", label: "Локация" },
    { key: "phone", label: "Телефон или внутренний номер" },
    { key: "cost_center", label: "Центр затрат" },
  ],
};

function json(payload, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(payload) };
}

function success(data) {
  return { status: "success", data };
}

function profilePayload() {
  const profile = profileComplete
    ? {
        person_id: "person-1",
        display_name: "Иван Петров",
        full_name: "Иван Петров",
        email: "requester@example.test",
        phone: "",
        internal_extension: "8899",
        department_id: "dept-it",
        department_name: "ИТ",
        location_id: "loc-ekb",
        location_name: "Екатеринбург",
        status: "active",
        custom_fields: { cost_center: "CC-42", secret_note: "hidden-server-value" },
      }
    : {
        person_id: "person-1",
        display_name: "Иван Петров",
        full_name: "",
        email: "requester@example.test",
        phone: "",
        internal_extension: "",
        department_id: "",
        location_id: "",
        status: "active",
        custom_fields: {},
      };
  return success({
    profile,
    profile_completion: {
      complete: profileComplete,
      status: profileComplete ? "complete" : "incomplete",
      setup_path: "/app/requester/profile/setup",
      required_fields: schema.required_fields,
      missing_fields: profileComplete
        ? []
        : [
            { key: "full_name", label: "ФИО" },
            { key: "department_id", label: "Подразделение" },
            { key: "location_id", label: "Локация" },
            { key: "phone", label: "Телефон или внутренний номер" },
            { key: "cost_center", label: "Центр затрат" },
          ],
      blocks: { ticket_create: !profileComplete, ticket_preview: !profileComplete },
    },
    profile_policy: { required: true },
    profile_schema: schema,
  });
}

async function bodyJson(route) {
  const postData = route.request().postData();
  return postData ? JSON.parse(postData) : null;
}

async function routeApi(route) {
  const request = route.request();
  const url = new URL(request.url());
  const key = `${url.pathname}${url.search}`;
  if (url.origin !== baseUrl) {
    await route.continue();
    return;
  }
  if (key === "/api/web/session/me") {
    await route.fulfill(json(success({
      user_login: "requester@example.test",
      actor_role: "user",
      auth_type: "web_session",
      default_workspace: "requester",
      available_workspaces: ["requester"],
      permissions: ["workspace.requester.view"],
    })));
    return;
  }
  if (key === "/api/web/notifications/unread_count") {
    await route.fulfill(json({ status: "ok", unread_count: 0 }));
    return;
  }
  if (key === "/api/web/requester/profile" && request.method() === "GET") {
    await route.fulfill(json(profilePayload()));
    return;
  }
  if (key === "/api/web/requester/profile" && request.method() === "PUT") {
    calls.profileUpdate = await bodyJson(route);
    profileComplete = true;
    await route.fulfill(json(profilePayload()));
    return;
  }
  if (key === "/api/web/requester/bootstrap") {
    await route.fulfill(json(success({
      workspace: "requester",
      profile: profilePayload().data.profile,
      profile_completion: profilePayload().data.profile_completion,
      profile_schema: schema,
      requester_context: { profile: {}, form_prefill: {}, summary: [] },
      devices: [],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 0,
      tickets_requiring_user_action_count: 0,
      pending_consent_count: 0,
      recent_tickets: [],
      feature_flags: { requester_ticket_create: profileComplete, requester_no_device_create: true },
    })));
    return;
  }
  if (key === "/api/web/requester/tickets") {
    await route.fulfill(json(success({ tickets: [] })));
    return;
  }
  if (key === "/api/registry/options") {
    await route.fulfill(json(success({
      departments: [{ value: "dept-it", label: "ИТ" }],
      locations: [{ value: "loc-ekb", label: "Екатеринбург" }],
      services: [],
      assets: [],
      people: [],
    })));
    return;
  }
  await route.continue();
}

function attachDiagnostics(page) {
  page.on("console", (message) => {
    if (message.type() !== "debug") {
      consoleMessages.push({ type: message.type(), text: message.text(), location: message.location() });
    }
  });
  page.on("requestfailed", (request) => {
    const error = request.failure()?.errorText ?? null;
    if (error === "net::ERR_ABORTED") {
      return;
    }
    networkIssues.push({ type: "requestfailed", url: request.url(), error });
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      networkIssues.push({ type: "response", url: response.url(), status: response.status() });
    }
  });
}

async function overflowCheck(page) {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const hasScrollableAncestor = (element) => {
      for (let current = element.parentElement; current; current = current.parentElement) {
        const overflowX = window.getComputedStyle(current).overflowX;
        if (overflowX === "auto" || overflowX === "scroll") {
          return true;
        }
      }
      return false;
    };
    return {
      pageOverflow: document.documentElement.scrollWidth > width + 1 || document.body.scrollWidth > width + 1,
      elements: Array.from(document.querySelectorAll("*"))
        .filter((element) => !hasScrollableAncestor(element))
        .map((element) => element.getBoundingClientRect())
        .filter((rect) => rect.width > 0 && (rect.left < -1 || rect.right > width + 1))
        .slice(0, 5)
        .map((rect) => ({ left: rect.left, right: rect.right, width: rect.width })),
    };
  });
}

async function forbiddenTerms(page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    return ["Registry", "verified", "provider", "person_id", "metadata_json", "binding", "claim", "session"].filter((term) => text.includes(term));
  });
}

async function runDesktop() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: "ru-RU" });
  const page = await context.newPage();
  attachDiagnostics(page);
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/profile/setup?next=/app/requester/new`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Заполните профиль" }).waitFor();
  await page.getByLabel("Поле профиля full_name").fill("Иван Петров");
  await page.getByLabel("Поле профиля department_id").selectOption("dept-it");
  await page.getByLabel("Поле профиля location_id").selectOption("loc-ekb");
  await page.getByLabel("Поле профиля phone").fill("");
  await page.getByLabel("Поле профиля internal_extension").fill("8899");
  await page.getByLabel("Поле профиля cost_center").fill("CC-42");
  const hiddenFieldVisible = await page.getByLabel("Поле профиля secret_note").count();
  await page.getByRole("button", { name: "Сохранить профиль" }).click();
  await page.getByText("Профиль сохранен").waitFor();
  await page.getByRole("link", { name: "Продолжить" }).waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-setup-1366x768.png`), fullPage: true });
  const forbidden = await forbiddenTerms(page);
  const finalUrl = page.url();
  await browser.close();
  return { finalUrl, forbidden, hiddenFieldVisible };
}

async function runMobile() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "ru-RU", isMobile: true });
  const page = await context.newPage();
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/profile`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Профиль" }).waitFor();
  await page.getByText("Центр затрат").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-read-390x844.png`), fullPage: true });
  const overflow = await overflowCheck(page);
  const forbidden = await forbiddenTerms(page);
  await browser.close();
  return { overflow, forbidden };
}

await mkdir(artifactDir, { recursive: true });
const desktop = await runDesktop();
const mobile = await runMobile();
const summary = {
  ok:
    calls.profileUpdate?.full_name === "Иван Петров" &&
    calls.profileUpdate?.phone === "" &&
    calls.profileUpdate?.internal_extension === "8899" &&
    calls.profileUpdate?.custom_fields?.cost_center === "CC-42" &&
    !("secret_note" in (calls.profileUpdate?.custom_fields ?? {})) &&
    desktop.hiddenFieldVisible === 0 &&
    desktop.forbidden.length === 0 &&
    mobile.forbidden.length === 0 &&
    !mobile.overflow.pageOverflow &&
    mobile.overflow.elements.length === 0 &&
    !consoleMessages.some((message) => message.type === "error" || message.type === "warning") &&
    networkIssues.length === 0,
  desktop,
  mobile,
  calls,
  consoleCount: consoleMessages.length,
  networkIssueCount: networkIssues.length,
  screenshots: [
    path.join(artifactDir, `${runId}-setup-1366x768.png`),
    path.join(artifactDir, `${runId}-read-390x844.png`),
  ],
};

await writeFile(path.join(artifactDir, `${runId}-summary.json`), JSON.stringify(summary, null, 2), "utf8");
await writeFile(path.join(artifactDir, `${runId}-console.json`), JSON.stringify(consoleMessages, null, 2), "utf8");
await writeFile(path.join(artifactDir, `${runId}-network.json`), JSON.stringify(networkIssues, null, 2), "utf8");

if (!summary.ok) {
  console.error(JSON.stringify(summary, null, 2));
  process.exit(1);
}

console.log(JSON.stringify(summary, null, 2));
