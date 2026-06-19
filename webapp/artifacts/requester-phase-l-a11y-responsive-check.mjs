import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_L_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-l-a11y-responsive";

const consoleMessages = [];
const networkIssues = [];
const calls = {
  deviceConfirm: 0,
  messages: [],
  profileUpdate: null,
  ticketCreate: null,
};

let profileComplete = false;
let profile = {
  person_id: "person-1",
  display_name: "",
  full_name: "",
  phone: "",
  internal_extension: "",
  department_id: "",
  location_id: "",
  custom_fields: {},
};

const profileSchema = {
  schema_key: "requester_profile",
  fields: [
    { key: "full_name", label: "ФИО", type: "text", required: true, visible: true, system: true, editable: true, section: "identity", order: 10 },
    { key: "department_id", label: "Подразделение", type: "select", required: true, visible: true, system: true, editable: true, section: "identity", order: 20 },
    { key: "location_id", label: "Локация", type: "select", required: true, visible: true, system: true, editable: true, section: "identity", order: 30 },
    { key: "phone", label: "Телефон", type: "phone", required: true, visible: true, system: true, editable: true, section: "contact", order: 40 },
    { key: "internal_extension", label: "Внутренний номер", type: "phone", visible: true, editable: true, section: "contact", order: 50 },
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true, section: "custom", order: 60 },
  ],
  custom_fields: [{ key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true }],
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

function profileDetail() {
  return success({
    profile,
    profile_completion: {
      complete: profileComplete,
      status: profileComplete ? "complete" : "required",
      setup_path: "/app/requester/profile/setup",
      required_fields: profileSchema.required_fields,
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
    profile_policy: { editable: true, editable_fields: [], change_request_required: false },
    profile_schema: profileSchema,
  });
}

function bootstrapPayload() {
  return success({
    workspace: "requester",
    profile: profileComplete ? { ...profile, display_name: "Иван Петров", full_name: "Иван Петров" } : profile,
    profile_completion: profileDetail().data.profile_completion,
    profile_schema: profileSchema,
    requester_context: {
      profile: { full_name: "Иван Петров", department: "ИТ", location: "Екатеринбург" },
      form_prefill: { device_id: "device-1" },
      summary: [],
    },
    devices: [
      {
        device_id: "device-1",
        hostname: "WORKSTATION-1",
        asset_name: "Ноутбук бухгалтера",
        os: "Windows",
        agent_version: "3.1.72",
        relationship_type: "primary_user",
        binding_status: "active",
        online: true,
        last_seen_at: "2026-06-19T09:00:00Z",
        open_ticket_count: 1,
      },
    ],
    active_bindings: [],
    pending_registration_claims: [{ claim_id: "claim-hidden", device_id: "device-hidden", status: "pending_admin_review" }],
    open_ticket_count: 1,
    tickets_requiring_user_action_count: 1,
    pending_consent_count: 0,
    recent_tickets: [],
    feature_flags: { requester_ticket_create: true, requester_no_device_create: true },
  });
}

function formPackPayload() {
  return {
    status: "ok",
    pack: {
      pack_key: "request_forms",
      version: "phase-l",
      forms: [
        {
          key: "workplace_help",
          title: "Помощь с рабочим местом",
          request_kind: "incident",
          availability_policy: { available_without_completed_profile: true, available_without_agent_binding: true },
          fields: [
            { key: "summary", label: "Кратко", type: "text", required: true },
            { key: "device_id", label: "Устройство", type: "device_picker", required: true },
          ],
        },
      ],
    },
  };
}

function catalogPayload() {
  return {
    status: "ok",
    catalog_version: "phase-l",
    services: [
      {
        service_code: "workplace",
        title: "Рабочее место",
        offerings: [{ offering_code: "help", full_code: "workplace.help", title: "Помощь с рабочим местом", request_template_key: "workplace_help" }],
      },
    ],
  };
}

function ticketsPayload() {
  return success({
    tickets: [
      {
        ticket_id: "T-1001",
        ticket_code: "REQ-1001",
        title: "VPN",
        description: "Не подключается VPN.",
        status: "waiting_user",
        requester_status_label: "Ждет ответа",
        updated_at: "2026-06-19T09:00:00Z",
        created_at: "2026-06-19T08:00:00Z",
      },
    ],
  });
}

function ticketDetailPayload() {
  return success({
    ticket: ticketsPayload().data.tickets[0],
    messages: [{ message_id: "message-1", from_role: "support", text: "Проверьте VPN еще раз.", created_at: "2026-06-19T09:05:00Z", attachments: [] }],
    events: [{ event_id: "event-1", requester_timeline_text: "Специалист ответил", created_at: "2026-06-19T09:05:00Z" }],
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
  if (key === "/api/web/requester/bootstrap") {
    await route.fulfill(json(bootstrapPayload()));
    return;
  }
  if (key === "/api/web/requester/profile" && request.method() === "GET") {
    await route.fulfill(json(profileDetail()));
    return;
  }
  if (key === "/api/web/requester/profile" && request.method() === "PUT") {
    calls.profileUpdate = await bodyJson(route);
    profileComplete = true;
    profile = { ...profile, ...calls.profileUpdate, display_name: calls.profileUpdate.full_name };
    await route.fulfill(json(profileDetail()));
    return;
  }
  if (key === "/api/registry/options") {
    await route.fulfill(json(success({ departments: [{ value: "dept-it", label: "ИТ" }], locations: [{ value: "loc-ekb", label: "Екатеринбург" }] })));
    return;
  }
  if (key === "/public_api/ticket_forms/current?pack_key=request_forms") {
    await route.fulfill(json(formPackPayload()));
    return;
  }
  if (key === "/api/service-catalog/current") {
    await route.fulfill(json(catalogPayload()));
    return;
  }
  if (key === "/api/knowledge/suggest") {
    await route.fulfill(json({ status: "ok", suggestions: [{ item_id: "kb-1", version_id: "v1", title: "Проверьте подключение", summary: "Отключите VPN и подключите снова." }], rollout: { enabled: true } }));
    return;
  }
  if (key === "/api/knowledge/feedback") {
    await route.fulfill(json({ status: "ok" }));
    return;
  }
  if (key === "/api/web/requester/tickets/preview") {
    await route.fulfill(json(success({ ok: true, request_type_label: "Инцидент", blockers: [], warnings: [], diagnostics: { text: "Диагностика будет выполнена по основному устройству." } })));
    return;
  }
  if (key === "/api/web/requester/tickets" && request.method() === "GET") {
    await route.fulfill(json(ticketsPayload()));
    return;
  }
  if (key === "/api/web/requester/tickets" && request.method() === "POST") {
    calls.ticketCreate = await bodyJson(route);
    await route.fulfill(json(success({ ticket_id: "T-1002", ticket: { ticket_id: "T-1002", ticket_code: "REQ-1002", title: "VPN", status: "new" } })));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001") {
    await route.fulfill(json(ticketDetailPayload()));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001/message") {
    calls.messages.push(await bodyJson(route));
    await route.fulfill(json(success({ message: { message_id: "message-2" } })));
    return;
  }
  if (key === "/api/web/requester/consents?status=pending") {
    await route.fulfill(json(success({ consents: [], count: 0 })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/lookup") {
    await route.fulfill(json(success({ pairing_id: "pair-l", purpose: "registration", next_url: "/app/device/register?pairing_id=pair-l" })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-l") {
    await route.fulfill(json(success({ pairing_id: "pair-l", purpose: "registration", status: "pending", device: { device_id: "device-l", hostname: "LINK-PC", os: "Windows", agent_version: "3.1.72" } })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-l/registration/confirm") {
    calls.deviceConfirm += 1;
    await route.fulfill(json(success({ pairing_id: "pair-l", purpose: "registration", status: "confirmed", device: { device_id: "device-l", hostname: "LINK-PC", os: "Windows", agent_version: "3.1.72" }, registration: { status: "pending_admin_review", device_id: "device-l" } })));
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
    if (error !== "net::ERR_ABORTED") {
      networkIssues.push({ type: "requestfailed", url: request.url(), error });
    }
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
        if (overflowX === "auto" || overflowX === "scroll") return true;
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

async function forbiddenTextCheck(page) {
  return page.evaluate(() => {
    const visibleText = document.body.innerText;
    const accessibleText = Array.from(document.querySelectorAll("[aria-label]"))
      .map((element) => element.getAttribute("aria-label") || "")
      .join("\n");
    const haystack = `${visibleText}\n${accessibleText}`;
    return [
      "Requester",
      "ticket",
      "pairing_id",
      "binding",
      "claim",
      "session",
      "registry person",
      "verified",
      "profile not linked",
      "department_id",
      "device_id",
      "affected_person_id",
      "pair-l",
      "device-l",
      "claim-hidden",
      "device-hidden",
    ].filter((term) => haystack.includes(term));
  });
}

async function captureReadableScreenshot(page, filename) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(100);
  await page.screenshot({ path: path.join(artifactDir, filename), fullPage: true });
}

async function newPage(browser, viewport) {
  const context = await browser.newContext({ viewport, locale: "ru-RU" });
  const page = await context.newPage();
  attachDiagnostics(page);
  await page.route("**/*", routeApi);
  return { context, page };
}

async function runKeyboardFlows(browser) {
  const results = {};
  profileComplete = false;
  profile = { person_id: "person-1", display_name: "", full_name: "", phone: "", internal_extension: "", department_id: "", location_id: "", custom_fields: {} };

  let session = await newPage(browser, { width: 1366, height: 768 });
  let { context, page } = session;
  await page.goto(`${baseUrl}/app/requester/profile/setup`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Заполните профиль" }).waitFor();
  await page.getByRole("button", { name: "Сохранить профиль" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "ФИО");
  results.profileFirstErrorFocus = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
  await page.getByLabel("ФИО").fill("Иван Петров");
  await page.getByLabel("Подразделение").selectOption("dept-it");
  await page.getByLabel("Локация").selectOption("loc-ekb");
  await page.getByLabel("Внутренний номер").fill("8899");
  await page.getByLabel("Центр затрат").fill("CC-42");
  await page.getByRole("button", { name: "Сохранить профиль" }).focus();
  await page.keyboard.press("Enter");
  await page.getByText("Профиль сохранен").waitFor();
  await captureReadableScreenshot(page, `${runId}-profile-1366x768.png`);
  results.profileForbidden = await forbiddenTextCheck(page);
  await context.close();

  session = await newPage(browser, { width: 1366, height: 768 });
  ({ context, page } = session);
  await page.goto(`${baseUrl}/app/requester/devices/link`, { waitUntil: "networkidle" });
  await page.getByLabel("Код подключения").focus();
  await page.keyboard.type("ABCD-1234");
  await page.keyboard.press("Enter");
  await page.getByText("LINK-PC").waitFor();
  await page.getByRole("button", { name: "Подключить устройство" }).focus();
  await page.keyboard.press("Enter");
  await page.getByText("Запрос отправлен на проверку").waitFor();
  await captureReadableScreenshot(page, `${runId}-devices-link-1366x768.png`);
  results.deviceForbidden = await forbiddenTextCheck(page);
  await context.close();

  session = await newPage(browser, { width: 390, height: 844 });
  ({ context, page } = session);
  await page.goto(`${baseUrl}/app/requester/new`, { waitUntil: "networkidle" });
  await page.getByLabel("Что случилось или что нужно?").focus();
  await page.keyboard.type("VPN не подключается");
  await page.getByRole("button", { name: "Продолжить" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Продолжить оформление" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "К проверке" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Кратко");
  results.dynamicFirstErrorFocus = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
  await page.getByLabel("Кратко").fill("VPN не подключается");
  await page.getByRole("button", { name: "К проверке" }).click();
  await page.getByRole("button", { name: "Проверить заявку" }).click();
  await page.getByText("Безопасный preview").waitFor();
  await captureReadableScreenshot(page, `${runId}-new-mobile-390x844.png`);
  results.newForbidden = await forbiddenTextCheck(page);
  await context.close();

  session = await newPage(browser, { width: 1366, height: 768 });
  ({ context, page } = session);
  await page.goto(`${baseUrl}/app/requester/tickets/T-1001`, { waitUntil: "networkidle" });
  await page.getByLabel("Ответ заявителя").focus();
  await page.keyboard.type("Проверил, ошибка осталась.");
  await page.getByRole("button", { name: "Отправить" }).focus();
  await page.keyboard.press("Enter");
  await page.getByText("Ответ отправлен").waitFor();
  await captureReadableScreenshot(page, `${runId}-chat-1366x768.png`);
  results.chatForbidden = await forbiddenTextCheck(page);
  await context.close();

  return results;
}

async function runViewportMatrix(browser) {
  const viewports = [
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ];
  const routes = ["/app/requester", "/app/requester/new", "/app/requester/tickets/T-1001", "/app/requester/profile/setup", "/app/requester/devices/link"];
  const results = [];
  for (const viewport of viewports) {
    for (const route of routes) {
      const { context, page } = await newPage(browser, viewport);
      await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
      await page.locator("main").first().waitFor();
      const overflow = await overflowCheck(page);
      const forbidden = await forbiddenTextCheck(page);
      results.push({ route, viewport, overflow, forbidden });
      await context.close();
    }
  }
  return results;
}

async function main() {
  await mkdir(artifactDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const keyboard = await runKeyboardFlows(browser);
  const viewportMatrix = await runViewportMatrix(browser);
  await browser.close();

  const badOverflow = viewportMatrix.filter((item) => item.overflow.pageOverflow || item.overflow.elements.length);
  const badForbidden = [
    ...Object.entries(keyboard).filter(([, value]) => Array.isArray(value) && value.length).map(([key, value]) => ({ key, forbidden: value })),
    ...viewportMatrix.filter((item) => item.forbidden.length).map((item) => ({ route: item.route, viewport: item.viewport, forbidden: item.forbidden })),
  ];
  const report = {
    runId,
    baseUrl,
    calls,
    keyboard,
    viewportMatrix,
    consoleCount: consoleMessages.length,
    networkIssueCount: networkIssues.length,
    consoleMessages,
    networkIssues,
    badOverflow,
    badForbidden,
  };
  await writeFile(path.join(artifactDir, `${runId}-report.json`), JSON.stringify(report, null, 2), "utf8");

  if (keyboard.profileFirstErrorFocus !== "ФИО" || keyboard.dynamicFirstErrorFocus !== "Кратко") {
    throw new Error(`Keyboard first-error focus failed: ${JSON.stringify(keyboard)}`);
  }
  if (!calls.profileUpdate || calls.deviceConfirm !== 1 || !calls.messages.length) {
    throw new Error(`Expected keyboard mutations were not recorded: ${JSON.stringify(calls)}`);
  }
  if (badOverflow.length || badForbidden.length || networkIssues.length) {
    throw new Error(`Phase L browser check failed: ${JSON.stringify({ badOverflow, badForbidden, networkIssues }, null, 2)}`);
  }
  console.log(JSON.stringify({ ok: true, report: path.join(artifactDir, `${runId}-report.json`), keyboard, checked: viewportMatrix.length }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
