import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_K_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-k-consents";

const consoleMessages = [];
const networkIssues = [];
const calls = {
  decisions: [],
};

let consents = [
  {
    consent_id: "consent-screen",
    subject_type: "remote_assist",
    subject_id: "remote-assist-screen",
    ticket_id: "550e8400-e29b-41d4-a716-446655440000",
    device_id: "device-raw-id",
    requester_person_id: "person-requester",
    requester_binding_id: "binding-requester",
    requester_account_session_id: "session-requester",
    requested_by_actor_id: "support-operator-1",
    requested_by_role: "support",
    risk_level: "remote_view",
    title: "Разрешить просмотр экрана",
    description: "Специалист просит временный просмотр экрана для обращения.",
    reason: "Нужно увидеть ошибку на экране.",
    requested_action_payload_redacted: { session_id: "remote-session-secret", mode: "view_only", duration_minutes: 5 },
    status: "pending",
    expires_at: "2026-06-20T10:00:00Z",
  },
  {
    consent_id: "consent-diagnostic",
    subject_type: "operation",
    subject_id: "diag-raw-id",
    ticket_id: "550e8400-e29b-41d4-a716-446655440000",
    device_id: "device-raw-id",
    requested_by_actor_id: "support-operator-1",
    requested_by_role: "support",
    risk_level: "diagnostic",
    title: "Диагностика устройства",
    description: "Специалист просит выполнить безопасную диагностику.",
    requested_action_payload_redacted: { tool_name: "observer_canary.consent_probe" },
    status: "pending",
    expires_at: "2026-06-20T10:00:00Z",
  },
  {
    consent_id: "consent-control",
    subject_type: "remote_assist",
    subject_id: "remote-assist-control",
    ticket_id: "550e8400-e29b-41d4-a716-446655440000",
    device_id: "device-raw-id",
    requested_by_actor_id: "support-operator-1",
    requested_by_role: "support",
    risk_level: "remote_control",
    title: "Удаленное управление",
    reason: "Помочь настроить рабочее место.",
    requested_action_payload_redacted: { session_id: "remote-control-secret", mode: "interactive_control", duration_minutes: 10 },
    status: "pending",
    expires_at: "2026-06-20T10:00:00Z",
  },
  {
    consent_id: "consent-admin",
    subject_type: "remote_assist",
    subject_id: "remote-assist-admin",
    ticket_id: "550e8400-e29b-41d4-a716-446655440000",
    device_id: "device-raw-id",
    requested_by_actor_id: "support-operator-1",
    requested_by_role: "admin",
    risk_level: "remote_admin",
    title: "Административный доступ",
    reason: "Установить обновление с повышенными правами.",
    requested_action_payload_redacted: { session_id: "remote-admin-secret", mode: "elevated_admin", duration_minutes: 3 },
    status: "pending",
    expires_at: "2026-06-20T10:00:00Z",
  },
];

function json(payload, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(payload) };
}

function success(data) {
  return { status: "success", data };
}

function pendingConsents() {
  return consents.filter((consent) => consent.status === "pending");
}

function bootstrapPayload() {
  return success({
    workspace: "requester",
    profile: { person_id: "person-requester", display_name: "Иван Петров" },
    profile_completion: {
      complete: true,
      status: "complete",
      setup_path: "/app/requester/profile/setup",
      required_fields: [],
      missing_fields: [],
      blocks: { ticket_create: false, ticket_preview: false, device_binding_confirmation: false },
    },
    profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
    requester_context: { profile: {}, form_prefill: {}, summary: [] },
    devices: [{ device_id: "device-raw-id", hostname: "WORKSTATION-1", os: "Windows", agent_version: "3.1.72", online: true }],
    active_bindings: [],
    pending_registration_claims: [],
    open_ticket_count: 1,
    tickets_requiring_user_action_count: pendingConsents().length ? 1 : 0,
    pending_consent_count: pendingConsents().length,
    recent_tickets: [
      {
        ticket_id: "550e8400-e29b-41d4-a716-446655440000",
        title: "VPN",
        description: "Не подключается VPN.",
        status: "waiting_user",
        requester_status_label: "Ждет пользователя",
        created_at: "2026-06-19T08:00:00Z",
      },
    ],
    feature_flags: { requester_ticket_create: true, requester_no_device_create: true },
  });
}

function ticketsPayload() {
  return success({
    tickets: [
      {
        ticket_id: "550e8400-e29b-41d4-a716-446655440000",
        ticket_code: "REQ-1001",
        title: "VPN",
        description: "Не подключается VPN.",
        status: "waiting_user",
        requester_status_label: "Ждет пользователя",
        updated_at: "2026-06-19T09:00:00Z",
        created_at: "2026-06-19T08:00:00Z",
      },
    ],
  });
}

function ticketDetailPayload() {
  return success({
    ticket: {
      ticket_id: "550e8400-e29b-41d4-a716-446655440000",
      ticket_code: "REQ-1001",
      title: "VPN",
      description: "Не подключается VPN.",
      status: "waiting_user",
      requester_status_label: "Ждет пользователя",
      updated_at: "2026-06-19T09:00:00Z",
      created_at: "2026-06-19T08:00:00Z",
    },
    messages: [],
    events: [{ event_id: "event-1", requester_timeline_text: "Специалист запросил согласие", created_at: "2026-06-19T09:05:00Z" }],
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
  if (key === "/api/web/requester/tickets") {
    await route.fulfill(json(ticketsPayload()));
    return;
  }
  if (key === "/api/web/requester/tickets/550e8400-e29b-41d4-a716-446655440000") {
    await route.fulfill(json(ticketDetailPayload()));
    return;
  }
  if (key === "/api/web/requester/consents?status=pending") {
    await route.fulfill(json(success({ consents: pendingConsents(), count: pendingConsents().length })));
    return;
  }
  const decisionMatch = key.match(/^\/api\/web\/requester\/consents\/([^/]+)\/(approve|deny)$/);
  if (decisionMatch) {
    const [, consentId, action] = decisionMatch;
    const decision = action === "approve" ? "approved" : "denied";
    calls.decisions.push({ consentId, action, body: await bodyJson(route) });
    consents = consents.map((consent) => (consent.consent_id === consentId ? { ...consent, status: decision } : consent));
    await route.fulfill(json(success({ consent: consents.find((consent) => consent.consent_id === consentId) })));
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
    const text = [
      document.body.innerText,
      ...Array.from(document.querySelectorAll("[aria-label]")).map((element) => element.getAttribute("aria-label") || ""),
    ].join("\n");
    return [
      "consent-screen",
      "consent-diagnostic",
      "consent-control",
      "consent-admin",
      "remote-assist-screen",
      "diag-raw-id",
      "remote-session-secret",
      "remote-control-secret",
      "remote-admin-secret",
      "support-operator-1",
      "device-raw-id",
      "person-requester",
      "binding-requester",
      "session-requester",
      "550e8400-e29b-41d4-a716-446655440000",
    ].filter((term) => text.includes(term));
  });
}

async function run() {
  await mkdir(artifactDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: "ru-RU" });
  const page = await context.newPage();
  attachDiagnostics(page);
  await page.route("**/*", routeApi);

  await page.goto(`${baseUrl}/app/requester`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Главная" }).waitFor();
  await page.getByRole("heading", { name: "Ожидают вашего решения" }).waitFor();
  await page.getByText("Просмотр экрана", { exact: true }).first().waitFor();
  await page.getByText("Диагностика", { exact: true }).first().waitFor();
  await page.getByText("Удаленное управление", { exact: true }).first().waitFor();
  await page.getByText("Административный доступ", { exact: true }).first().waitFor();
  await page.getByRole("button", { name: "Разрешить запрос согласия" }).first().click();
  await page.getByText("Согласие подтверждено").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-dashboard-1366x768.png`), fullPage: true });
  const dashboardForbidden = await forbiddenTerms(page);
  const dashboardOverflow = await overflowCheck(page);

  await page.goto(`${baseUrl}/app/requester/tickets/550e8400-e29b-41d4-a716-446655440000`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "VPN" }).waitFor();
  await page.getByRole("heading", { name: "Ожидают вашего решения" }).waitFor();
  await page.getByRole("button", { name: "Отклонить запрос согласия" }).first().click();
  await page.getByText("Согласие отклонено").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-detail-1366x768.png`), fullPage: true });
  const detailForbidden = await forbiddenTerms(page);
  const detailOverflow = await overflowCheck(page);

  await browser.close();

  const summary = {
    runId,
    decisions: calls.decisions,
    dashboardForbidden,
    detailForbidden,
    dashboardOverflow,
    detailOverflow,
    consoleCount: consoleMessages.length,
    networkIssueCount: networkIssues.length,
  };
  await writeFile(path.join(artifactDir, `${runId}-summary.json`), JSON.stringify(summary, null, 2), "utf8");
  await writeFile(path.join(artifactDir, `${runId}-console.json`), JSON.stringify(consoleMessages, null, 2), "utf8");
  await writeFile(path.join(artifactDir, `${runId}-network.json`), JSON.stringify(networkIssues, null, 2), "utf8");

  if (dashboardForbidden.length || detailForbidden.length) {
    throw new Error(`Forbidden visible/aria terms: ${JSON.stringify({ dashboardForbidden, detailForbidden })}`);
  }
  if (dashboardOverflow.pageOverflow || dashboardOverflow.elements.length || detailOverflow.pageOverflow || detailOverflow.elements.length) {
    throw new Error(`Layout overflow: ${JSON.stringify({ dashboardOverflow, detailOverflow })}`);
  }
  if (networkIssues.length) {
    throw new Error(`Network issues: ${JSON.stringify(networkIssues)}`);
  }
  if (!calls.decisions.some((decision) => decision.consentId === "consent-screen" && decision.action === "approve")) {
    throw new Error("Dashboard approval was not recorded");
  }
  if (!calls.decisions.some((decision) => decision.action === "deny")) {
    throw new Error("Detail denial was not recorded");
  }
  console.log(JSON.stringify(summary, null, 2));
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
