import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.PHASE_H_BASE_URL || "http://127.0.0.1:5190";
const repoRoot = path.resolve(process.cwd(), "..");
const artifactDir = path.join(repoRoot, "artifacts", "browser_live_validation", "requester-ui-refactor-20260619");
const runId = "requester-phase-h-tickets";

const calls = {
  close: 0,
  consentApprove: 0,
  feedback: null,
  message: null,
  reopen: 0,
  upload: 0,
};
const consoleMessages = [];
const networkIssues = [];
let consentStatus = "pending";
let detailStatus = "resolved";
let messageSent = false;
let feedbackSubmitted = false;

function json(payload, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(payload) };
}

function success(data) {
  return { status: "success", data };
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
  if (key === "/api/web/requester/tickets") {
    await route.fulfill(json(success({
      tickets: [
        {
          ticket_id: "T-1001",
          ticket_code: "REQ-1001",
          title: "Ноутбук не включается",
          status: detailStatus,
          requester_status_label: detailStatus === "resolved" ? "Решена" : detailStatus === "closed" ? "Закрыта" : "В работе",
          updated_at: "2026-06-19T04:30:00Z",
          created_at: "2026-06-19T04:00:00Z",
        },
        {
          ticket_id: "550e8400-e29b-41d4-a716-446655440000",
          ticket_code: "REQ-1002",
          title: "Нужен ответ",
          status: "waiting_user",
          requester_status_label: "Ждет вашего ответа",
          updated_at: "2026-06-19T05:00:00Z",
        },
        {
          ticket_id: "T-1003",
          ticket_code: "REQ-1003",
          title: "Закрытая заявка",
          status: "closed",
          requester_status_label: "Закрыта",
          updated_at: "2026-06-18T09:00:00Z",
        },
      ],
    })));
    return;
  }
  if (key === "/api/web/requester/consents?status=pending") {
    await route.fulfill(json(success({
      consents: consentStatus === "pending" ? [{
        consent_id: "consent-1",
        ticket_id: "T-1001",
        subject_type: "diagnostic",
        subject_id: "diag-1",
        title: "Диагностика устройства",
        description: "Оператор просит выполнить безопасную диагностику.",
        status: "pending",
        risk_level: "low",
        expires_at: "2026-06-20T10:00:00Z",
      }] : [],
    })));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001") {
    await route.fulfill(json(success({
      ticket: {
        ticket_id: "T-1001",
        ticket_code: "REQ-1001",
        title: "Ноутбук не включается",
        description: "Не включается после обновления",
        status: detailStatus,
        requester_status_label: detailStatus === "resolved" ? "Решена" : detailStatus === "closed" ? "Закрыта" : "В работе",
        updated_at: "2026-06-19T04:30:00Z",
      },
      messages: messageSent ? [{
        message_id: "m-1",
        from_role: "user",
        text: "Прикладываю лог",
        created_at: "2026-06-19T05:10:00Z",
        attachments: [{ artifact_id: "artifact-1", name: "log.txt", url: "/api/artifacts/artifact-1/download" }],
      }] : [{
        message_id: "m-support",
        from_role: "support",
        text: "Проверьте питание.",
        created_at: "2026-06-19T04:40:00Z",
      }],
      events: [{ event_id: "e-1", requester_timeline_text: "Оператор запросил диагностику", created_at: "2026-06-19T04:45:00Z" }],
    })));
    return;
  }
  if (key === "/api/upload") {
    calls.upload += 1;
    await route.fulfill(json({ status: "success", artifact_id: "artifact-1", filename: "log.txt", url: "/api/artifacts/artifact-1/download", kind: "file" }));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001/message") {
    calls.message = JSON.parse(request.postData() || "{}");
    messageSent = true;
    await route.fulfill(json(success({ message_id: "m-1" })));
    return;
  }
  if (key === "/api/web/requester/consents/consent-1/approve") {
    calls.consentApprove += 1;
    consentStatus = "approved";
    await route.fulfill(json(success({ consent: { consent_id: "consent-1", status: "approved" } })));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001/close") {
    calls.close += 1;
    detailStatus = "closed";
    await route.fulfill(json(success({ ticket: { ticket_id: "T-1001", status: "closed" } })));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001/feedback") {
    calls.feedback = JSON.parse(request.postData() || "{}");
    feedbackSubmitted = true;
    await route.fulfill(json(success({ ok: true, feedback_id: "fb-1", reopen_available: true })));
    return;
  }
  if (key === "/api/web/requester/tickets/T-1001/reopen") {
    if (!feedbackSubmitted) {
      await route.fulfill(json({ status: "error", message: "feedback missing" }, 409));
      return;
    }
    calls.reopen += 1;
    detailStatus = "in_progress";
    await route.fulfill(json(success({ ok: true, ticket_id: "T-1001", ticket_status: "in_progress", reopen_id: "re-1" })));
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

async function runDesktop() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: "ru-RU" });
  const page = await context.newPage();
  attachDiagnostics(page);
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/tickets`, { waitUntil: "networkidle" });
  await page.getByText("REQ-1001").waitFor();
  const rawUuidVisible = await page.getByText("550e8400-e29b-41d4-a716-446655440000").count();
  await page.getByRole("button", { name: "Требуют действий" }).click();
  await page.getByText("Подтвердите решение").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-list-1366x768.png`), fullPage: true });
  await page.getByText("REQ-1001").click();
  await page.getByRole("heading", { name: "Ноутбук не включается" }).waitFor();
  await page.getByLabel("Прикрепить файл к ответу").setInputFiles({
    name: "log.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("log"),
  });
  await page.getByText("log.txt").waitFor();
  await page.getByLabel("Ответ заявителя").fill("Прикладываю лог");
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await page.getByRole("link", { name: "log.txt" }).waitFor();
  await page.getByRole("button", { name: "Разрешить диагностику" }).click();
  await page.getByText("Согласие подтверждено").waitFor();
  await page.getByRole("button", { name: "Подтвердить решение" }).click();
  await page.getByText("Решение подтверждено").waitFor();
  await page.getByLabel("Оценка обращения").fill("2");
  await page.getByLabel("Проблема решена").click();
  await page.getByRole("button", { name: "Отправить оценку" }).click();
  await page.getByText("Оценка сохранена").waitFor();
  await page.getByRole("button", { name: "Вернуть в работу" }).click();
  await page.getByText("Обращение возвращено в работу").waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-detail-1366x768.png`), fullPage: true });
  const finalUrl = page.url();
  await browser.close();
  return { finalUrl, rawUuidVisible };
}

async function runMobile() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "ru-RU", isMobile: true });
  const page = await context.newPage();
  await page.route("**/*", routeApi);
  await page.goto(`${baseUrl}/app/requester/tickets/T-1001`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Ноутбук не включается" }).waitFor();
  await page.screenshot({ path: path.join(artifactDir, `${runId}-detail-390x844.png`), fullPage: true });
  const overflow = await overflowCheck(page);
  await browser.close();
  return overflow;
}

await mkdir(artifactDir, { recursive: true });
const desktop = await runDesktop();
const mobile = await runMobile();
const summary = {
  ok:
    desktop.rawUuidVisible === 0 &&
    calls.upload === 1 &&
    calls.message?.text === "Прикладываю лог" &&
    calls.message?.attachment_refs?.[0] === "artifact-1" &&
    calls.consentApprove === 1 &&
    calls.close === 1 &&
    calls.feedback?.rating === 2 &&
    calls.feedback?.problem_resolved === false &&
    calls.reopen === 1 &&
    !mobile.pageOverflow &&
    mobile.elements.length === 0 &&
    !consoleMessages.some((message) => message.type === "error" || message.type === "warning") &&
    networkIssues.length === 0,
  desktop,
  mobile,
  calls,
  consoleCount: consoleMessages.length,
  networkIssueCount: networkIssues.length,
  screenshots: [
    path.join(artifactDir, `${runId}-list-1366x768.png`),
    path.join(artifactDir, `${runId}-detail-1366x768.png`),
    path.join(artifactDir, `${runId}-detail-390x844.png`),
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
