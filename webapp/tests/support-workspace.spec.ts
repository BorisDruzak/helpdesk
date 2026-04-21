import { expect, test, type Page } from "playwright/test";


function waitForRealtimeSubscribeAck(page: Page, scope: "ticket" | "device", id: string): Promise<void> {
  return new Promise((resolve) => {
    page.on("websocket", (socket) => {
      if (!socket.url().endsWith("/ws_ui")) {
        return;
      }
      socket.on("framereceived", (event) => {
        try {
          const payload = JSON.parse(event.payload);
          const payloadId = scope === "ticket" ? payload.ticket_id : payload.device_id;
          if (payload.type === "subscribe_ack" && payloadId === id) {
            resolve();
          }
        } catch {
          // Ignore non-JSON frames from the test bridge.
        }
      });
    });
  });
}


test("оператор проходит support workflow на русском языке", async ({ page }) => {
  const ticketRealtimeReady = waitForRealtimeSubscribeAck(page, "ticket", "ticket-1");

  await page.goto("/app/support");

  await expect(page).toHaveURL(/\/app\/login/);
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page).toHaveTitle("pc_client — рабочие места");
  await expect(page.getByRole("heading", { name: "Вход в рабочие места" })).toBeVisible();

  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/support$/);
  await expect(page.getByRole("heading", { name: "Рабочее место поддержки" })).toBeVisible();
  await expect(page.getByText("trace-support-root")).toBeVisible();

  await page.getByRole("button", { name: /T-200002/i }).click();
  await expect(page.getByRole("heading", { name: "Нужно уточнить статус печати" })).toBeVisible();

  await page.getByRole("button", { name: /T-200001/i }).click();
  await expect(page.getByRole("heading", { name: "Ошибка синхронизации профиля" })).toBeVisible();
  await ticketRealtimeReady;

  const externalMessage = "Внешнее обновление прилетело по realtime-мосту.";
  await page.evaluate(async (messageText) => {
    await fetch("/api/web/support/tickets/ticket-1/messages", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: messageText,
        visibility: "public",
      }),
    });
  }, externalMessage);
  await expect(page.getByText(externalMessage)).toBeVisible();

  await page
    .getByLabel("Ответ оператору")
    .fill("Проверка начата, остаёмся на связи и собираем сетевой снимок.");
  await page.getByRole("button", { name: "Отправить ответ" }).click();
  await expect(
    page.getByText("Проверка начата, остаёмся на связи и собираем сетевой снимок.")
  ).toBeVisible();

  await page.getByRole("button", { name: "Взять в работу" }).click();
  await expect(page.locator(".support-ticket-detail__stats")).toContainText("В работе");

  await page.getByRole("button", { name: /network\.diagnostics/i }).click();
  await page.getByLabel("Хост").fill("fileserver.local");
  await page.getByRole("button", { name: "Запустить инструмент" }).click();

  await expect(
    page.getByText(/Операция op-support-tool-\d+ поставлена в очередь выполнения\./)
  ).toBeVisible();
  await expect(page.getByText("Сетевой маршрут проверен успешно.").first()).toBeVisible();
  await expect(page.getByText("Инструмент завершён")).toBeVisible();
  await expect(page.locator(".support-operations__list")).toContainText("network.diagnostics");
});
