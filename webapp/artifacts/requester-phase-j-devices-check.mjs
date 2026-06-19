import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_J_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-j-devices";

const calls = {
  confirms: [],
  lookups: [],
};
const consoleMessages = [];
const networkIssues = [];
let profileComplete = true;

function json(payload, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(payload) };
}

function success(data) {
  return { status: "success", data };
}

function bootstrapPayload() {
  return success({
    workspace: "requester",
    profile: profileComplete ? { person_id: "person-1", display_name: "Иван Петров" } : null,
    profile_completion: {
      complete: profileComplete,
      status: profileComplete ? "complete" : "required",
      setup_path: "/app/requester/profile/setup",
      required_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
      missing_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
      blocks: { ticket_create: !profileComplete, ticket_preview: !profileComplete, device_binding_confirmation: false },
    },
    profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
    requester_context: { profile: {}, form_prefill: {}, summary: [] },
    devices: profileComplete
      ? [
          {
            device_id: "device-1",
            hostname: "WORKSTATION-1",
            os: "Windows",
            agent_version: "3.1.72",
            relationship_type: "primary_user",
            binding_status: "active",
            online: true,
            last_seen_at: "2026-06-19T09:00:00Z",
            open_ticket_count: 2,
          },
        ]
      : [],
    active_bindings: [],
    pending_registration_claims: profileComplete
      ? [{ claim_id: "claim-safe", device_id: "hidden-device-id", status: "pending_admin_review", submitted_at: "2026-06-19T08:00:00Z" }]
      : [],
    open_ticket_count: 0,
    tickets_requiring_user_action_count: 0,
    pending_consent_count: 0,
    recent_tickets: [],
    feature_flags: { requester_ticket_create: profileComplete, requester_no_device_create: true },
  });
}

function pairingPayload(pairingId) {
  const direct = pairingId === "pair-direct";
  const approved = direct || pairingId === "pair-incomplete";
  return success({
    pairing_id: pairingId,
    purpose: "registration",
    status: approved ? "confirmed" : "pending",
    device: {
      device_id: direct ? "device-direct" : approved ? "device-incomplete" : "device-manual",
      hostname: direct ? "DIRECT-PC" : approved ? "INCOMPLETE-PC" : "R4-PC",
      os: "Windows",
      agent_version: direct ? "3.1.64" : approved ? "3.1.73" : "3.1.64",
    },
    registration: approved ? { status: "approved", device_id: direct ? "device-direct" : "device-incomplete" } : null,
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
  if (key === "/api/web/requester/devices/device-1") {
    await route.fulfill(json(success({
      device: {
        device_id: "device-1",
        hostname: "WORKSTATION-1",
        os: "Windows",
        agent_version: "3.1.72",
        relationship_type: "primary_user",
        binding_status: "active",
        online: true,
        open_ticket_count: 2,
      },
      recent_tickets: [{ ticket_id: "550e8400-e29b-41d4-a716-446655440000", ticket_code: "REQ-42", title: "VPN", status: "new" }],
    })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/lookup") {
    calls.lookups.push(await bodyJson(route));
    await route.fulfill(json(success({
      pairing_id: profileComplete ? "pair-manual" : "pair-incomplete",
      purpose: "registration",
      next_url: profileComplete ? "/app/device/register?pairing_id=pair-manual" : "/app/device/register?pairing_id=pair-incomplete",
    })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-manual") {
    await route.fulfill(json(pairingPayload("pair-manual")));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-incomplete") {
    await route.fulfill(json(pairingPayload("pair-incomplete")));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-direct") {
    await route.fulfill(json(pairingPayload("pair-direct")));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-manual/registration/confirm") {
    calls.confirms.push("manual");
    await route.fulfill(json(success({
      ...pairingPayload("pair-manual").data,
      status: "confirmed",
      registration: { status: "pending_admin_review", device_id: "device-manual" },
    })));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-incomplete/registration/confirm") {
    calls.confirms.push("incomplete");
    await route.fulfill(json(pairingPayload("pair-incomplete")));
    return;
  }
  if (key === "/api/web/registry/browser-pairings/pair-direct/registration/confirm") {
    calls.confirms.push("direct");
    await route.fulfill(json(pairingPayload("pair-direct")));
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

async function visibleForbiddenTerms(page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    return ["binding", "claim", "session", "pairing_id", "pair-direct", "pair-manual", "pair-incomplete", "hidden-device-id", "550e8400-e29b"].filter((term) =>
      text.includes(term),
    );
  });
}

async function runDesktop() {
  profileComplete = true;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: "ru-RU" });
  const page = await context.newPage();
  attachDiagnostics(page);
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/devices`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Устройства", exact: true }).waitFor();
  await page.getByRole("button", { name: "Подробнее о WORKSTATION-1" }).click();
  await page.getByText("Последние обращения", { exact: true }).waitFor();
  const radios = await page.getByRole("radio").count();
  await page.getByLabel("Код подключения").fill("ABCD-1234");
  await page.getByRole("button", { name: "Проверить код" }).click();
  await page.getByText("R4-PC").waitFor();
  await page.getByRole("button", { name: "Подключить устройство" }).click();
  await page.getByText("Запрос отправлен на проверку").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-desktop-1366x768.png`), fullPage: true });
  const forbidden = await visibleForbiddenTerms(page);
  await browser.close();
  return { forbidden, radios };
}

async function runIncompleteLink() {
  profileComplete = false;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: "ru-RU" });
  const page = await context.newPage();
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/devices/link`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Устройства", exact: true }).waitFor();
  await page.getByLabel("Код подключения").fill("WXYZ-9999");
  await page.getByRole("button", { name: "Проверить код" }).click();
  await page.getByText("INCOMPLETE-PC").waitFor();
  await page.getByRole("button", { name: "Подключить устройство" }).click();
  await page.getByText("Устройство подключено").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-incomplete-link-1366x768.png`), fullPage: true });
  const forbidden = await visibleForbiddenTerms(page);
  await browser.close();
  return { forbidden };
}

async function runMobileDirect() {
  profileComplete = true;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "ru-RU", isMobile: true });
  const page = await context.newPage();
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/devices?pairing_id=pair-direct`, { waitUntil: "networkidle" });
  await page.getByText("DIRECT-PC").waitFor();
  await page.getByText("Проверьте устройство перед подключением.").waitFor();
  await page.getByRole("button", { name: "Подключить устройство" }).click();
  await page.getByText("Устройство подключено").waitFor();
  await page.getByText("Устройство подключено").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-direct-390x844.png`), fullPage: false });
  const overflow = await overflowCheck(page);
  const forbidden = await visibleForbiddenTerms(page);
  await browser.close();
  return { forbidden, overflow };
}

await mkdir(artifactDir, { recursive: true });
const desktop = await runDesktop();
const incomplete = await runIncompleteLink();
const mobile = await runMobileDirect();
const summary = {
  ok:
    desktop.radios === 0 &&
    desktop.forbidden.length === 0 &&
    incomplete.forbidden.length === 0 &&
    mobile.forbidden.length === 0 &&
    !mobile.overflow.pageOverflow &&
    mobile.overflow.elements.length === 0 &&
    calls.lookups.some((payload) => payload?.pairing_code === "ABCD-1234") &&
    calls.lookups.some((payload) => payload?.pairing_code === "WXYZ-9999") &&
    calls.confirms.includes("manual") &&
    calls.confirms.includes("incomplete") &&
    calls.confirms.includes("direct") &&
    !consoleMessages.some((message) => message.type === "error" || message.type === "warning") &&
    networkIssues.length === 0,
  desktop,
  incomplete,
  mobile,
  calls,
  consoleCount: consoleMessages.length,
  networkIssueCount: networkIssues.length,
  screenshots: [
    path.join(artifactDir, `${runId}-desktop-1366x768.png`),
    path.join(artifactDir, `${runId}-incomplete-link-1366x768.png`),
    path.join(artifactDir, `${runId}-direct-390x844.png`),
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
