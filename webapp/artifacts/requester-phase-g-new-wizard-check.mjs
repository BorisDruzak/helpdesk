import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_G_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-g-new-wizard";

const requests = {
  create: null,
  feedback: [],
  knowledge: null,
  preview: null,
};
const consoleMessages = [];
const networkIssues = [];

function json(payload, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

function success(data) {
  return { status: "success", data };
}

function ticketDetail() {
  return success({
    ticket: {
      ticket_id: "T-PHASE-G-1",
      ticket_code: "T-PHASE-G-1",
      title: "Ноутбук не включается",
      description: "Ноутбук не включается после обновления",
      status: "new",
      status_label: "Новое",
      public_status: "accepted",
      public_status_label: "Принято",
      created_at: "2026-06-19T10:00:00Z",
      updated_at: "2026-06-19T10:00:00Z",
    },
    messages: [],
    timeline: [],
    attachments: [],
    consent_requests: [],
    available_actions: [],
  });
}

async function bodyJson(route) {
  const postData = route.request().postData();
  if (!postData) {
    return null;
  }
  return JSON.parse(postData);
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
    await route.fulfill(
      json(
        success({
          user_login: "requester@example.test",
          actor_role: "user",
          auth_type: "web_session",
          default_workspace: "requester",
          available_workspaces: ["requester"],
          permissions: ["workspace.requester.view"],
        }),
      ),
    );
    return;
  }

  if (key === "/api/web/notifications/unread_count") {
    await route.fulfill(json({ status: "ok", unread_count: 0 }));
    return;
  }

  if (key === "/api/web/requester/bootstrap") {
    await route.fulfill(
      json(
        success({
          workspace: "requester",
          profile: {
            person_id: "person-1",
            display_name: "Иван Петров",
            full_name: "Иван Петров",
            email: "requester@example.test",
            phone: "+7 343 000-00-01",
            department_id: "dept-it",
            location_id: "loc-ekb",
            status: "active",
          },
          profile_completion: {
            complete: true,
            status: "complete",
            setup_path: "/app/requester/profile/setup",
            required_fields: [],
            missing_fields: [],
            blocks: { ticket_create: false, ticket_preview: false },
          },
          profile_schema: { fields: [], custom_fields: [], required_fields: [] },
          requester_context: {
            profile: { full_name: "Иван Петров", department: "ИТ", location: "Екатеринбург" },
            form_prefill: { device_id: "device-1" },
            summary: [],
          },
          devices: [{ device_id: "device-1", hostname: "desk-1", asset_name: "Desk 1", os: "Windows" }],
          active_bindings: [],
          pending_registration_claims: [],
          open_ticket_count: 0,
          tickets_requiring_user_action_count: 0,
          pending_consent_count: 0,
          recent_tickets: [],
          feature_flags: { requester_ticket_create: true, requester_no_device_create: true },
        }),
      ),
    );
    return;
  }

  if (key === "/public_api/ticket_forms/current?pack_key=request_forms") {
    await route.fulfill(
      json({
        status: "ok",
        pack: {
          pack_key: "request_forms",
          version: "phase-g-browser",
          forms: [
            {
              key: "breakage",
              title: "Проблема с ноутбуком",
              request_kind: "incident",
              availability_policy: { available_without_agent_binding: true },
              fields: [
                { key: "summary", label: "Кратко", type: "text", required: true },
                { key: "device_id", label: "Устройство", type: "device_picker", required: true },
              ],
            },
          ],
        },
      }),
    );
    return;
  }

  if (key === "/api/service-catalog/current") {
    await route.fulfill(
      json({
        status: "ok",
        catalog_version: "phase-g-browser",
        services: [
          {
            service_code: "workplace",
            title: "Рабочее место",
            offerings: [
              {
                offering_code: "laptop_broken",
                full_code: "workplace.laptop_broken",
                title: "Сломался ноутбук",
                request_template_key: "breakage",
              },
            ],
          },
        ],
      }),
    );
    return;
  }

  if (key === "/api/knowledge/suggest") {
    requests.knowledge = await bodyJson(route);
    await route.fulfill(
      json({
        status: "ok",
        suggestions: [
          {
            item_id: "kb-1",
            version_id: "ver-1",
            slug: "laptop-power",
            type: "article",
            title: "Проверьте питание ноутбука",
            summary: "Отключите зарядку на 10 секунд и повторите запуск.",
          },
        ],
        rollout: { enabled: true, show_before_form: true },
      }),
    );
    return;
  }

  if (key === "/api/knowledge/feedback") {
    requests.feedback.push(await bodyJson(route));
    await route.fulfill(json({ status: "ok" }));
    return;
  }

  if (key === "/api/web/requester/tickets/preview") {
    requests.preview = await bodyJson(route);
    await route.fulfill(
      json(
        success({
          ok: true,
          service: { code: "workplace", title: "Рабочее место" },
          offering: { code: "laptop_broken", full_code: "workplace.laptop_broken", title: "Сломался ноутбук" },
          request_type_label: "Инцидент",
          public_status_after_create: "accepted",
          approval: { required: false },
          diagnostics: {
            required: true,
            consent_required: false,
            text: "Диагностика будет выполнена по основному устройству Desk 1.",
          },
          warnings: ["Маршрут будет выбран сервером по каталогу."],
          blockers: [],
          would_create_ticket: false,
        }),
      ),
    );
    return;
  }

  if (key === "/api/web/requester/tickets" && request.method() === "GET") {
    await route.fulfill(json(success({ tickets: [] })));
    return;
  }

  if (key === "/api/web/requester/tickets" && request.method() === "POST") {
    requests.create = await bodyJson(route);
    await route.fulfill(
      json(
        success({
          ticket_id: "T-PHASE-G-1",
          ticket: { ticket_id: "T-PHASE-G-1", title: "Ноутбук не включается", status: "new" },
        }),
      ),
    );
    return;
  }

  if (key === "/api/web/requester/tickets/T-PHASE-G-1") {
    await route.fulfill(json(ticketDetail()));
    return;
  }

  if (key === "/api/web/requester/consents?status=pending") {
    await route.fulfill(json(success({ consents: [] })));
    return;
  }

  await route.continue();
}

async function runDesktop() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    locale: "ru-RU",
  });
  const page = await context.newPage();
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
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/new`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Опишите проблему" }).waitFor();
  const serviceSelectorVisible = await page.getByLabel("Вариант услуги").count();
  await page.getByLabel("Что случилось или что нужно?").fill("Ноутбук не включается после обновления");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await page.getByText("Проверьте питание ноутбука").waitFor();
  await page.getByRole("button", { name: "Не помогло" }).click();
  await page.getByRole("button", { name: "Продолжить оформление" }).click();
  await page.getByLabel("Поле формы обращения summary").fill("Ноутбук не включается");
  await page.getByRole("button", { name: "К проверке" }).click();
  await page.getByRole("button", { name: "Проверить заявку" }).click();
  await page.getByText("Безопасный preview").waitFor();
  await page.getByText("Диагностика будет выполнена по основному устройству Desk 1.").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-1366x768.png`), fullPage: true });
  await page.getByRole("button", { name: "Создать обращение" }).click();
  await page.waitForURL("**/app/requester/tickets/T-PHASE-G-1", { timeout: 10000 });
  await page.waitForLoadState("networkidle");
  const finalUrl = page.url();
  await browser.close();
  return { finalUrl, serviceSelectorVisible };
}

async function runMobile() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "ru-RU",
    isMobile: true,
  });
  const page = await context.newPage();
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/new`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Опишите проблему" }).waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-390x844.png`), fullPage: true });
  const overflowCheck = await page.evaluate(() => {
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
    const elements = Array.from(document.querySelectorAll("*"))
      .filter((element) => !hasScrollableAncestor(element))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          left: rect.left,
          right: rect.right,
          width: rect.width,
          tag: element.tagName.toLowerCase(),
          text: (element.textContent ?? "").trim().slice(0, 80),
        };
      })
      .filter((rect) => rect.width > 0 && (rect.left < -1 || rect.right > width + 1))
      .slice(0, 5)
      .map((rect) => ({ left: rect.left, right: rect.right, width: rect.width, tag: rect.tag, text: rect.text }));
    return {
      pageOverflow:
        document.documentElement.scrollWidth > width + 1 ||
        document.body.scrollWidth > width + 1,
      elements,
    };
  });
  await browser.close();
  return overflowCheck;
}

await mkdir(artifactDir, { recursive: true });
const desktop = await runDesktop();
const mobile = await runMobile();
const summary = {
  ok:
    desktop.finalUrl.endsWith("/app/requester/tickets/T-PHASE-G-1") &&
    desktop.serviceSelectorVisible === 0 &&
    requests.create?.service_code === "workplace" &&
    requests.create?.offering_full_code === "workplace.laptop_broken" &&
    requests.create?.request_template_key === "breakage" &&
    requests.create?.form_payload?.summary === "Ноутбук не включается" &&
    requests.create?.form_payload?.device_id === "device-1" &&
    requests.create?.knowledge_attempts?.some?.((item) => item.item_id === "kb-1" && item.result === "not_helpful") &&
    !mobile.pageOverflow &&
    mobile.elements.length === 0 &&
    !consoleMessages.some((message) => message.type === "error" || message.type === "warning") &&
    networkIssues.length === 0,
  desktop,
  mobile,
  requests,
  consoleCount: consoleMessages.length,
  networkIssueCount: networkIssues.length,
  screenshots: [
    path.join(artifactDir, `${runId}-1366x768.png`),
    path.join(artifactDir, `${runId}-390x844.png`),
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
