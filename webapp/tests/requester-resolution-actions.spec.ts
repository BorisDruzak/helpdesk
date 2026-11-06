import { expect, test } from "playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
  test(`requester can decide a solution after scrolling history ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    let phase = "resolved";
    const commands: Array<{ path: string; body: unknown }> = [];
    const errors: string[] = [], unexpected: string[] = [];
    const code = "T-009990";
    const closedTimer = JSON.parse(execFileSync(process.env.PYTHON ?? "python", ["-X", "utf8", "-c",
      "import sys,json;from pathlib import Path;sys.path[:0]=[sys.argv[1],str(Path(sys.argv[1]).parent)];from datetime import datetime,timezone,timedelta;from types import SimpleNamespace;from tickets.workflow_service import _build_transition_updates;from requester.ticket_handling import sla_timer;due=datetime(2026,11,5,13,47,tzinfo=timezone.utc);resolved=due-timedelta(minutes=65);closed=due+timedelta(hours=15);t=SimpleNamespace(status='resolved',created_at=due-timedelta(hours=5),resolution_at=resolved,resolved_at=resolved,resolution_due_at=due,closed_at=None,canceled_at=None,sla_paused_at=None,sla_paused_seconds=0,resolution_breached_at=None);t.__dict__.update(_build_transition_updates(t,'resolved','closed',closed,None),status='closed');print(json.dumps(sla_timer(t,t.__dict__,resolution=True,now=closed)))",
      fileURLToPath(new URL("../../server", import.meta.url))], { encoding: "utf8" }));
    expect(closedTimer.completed_at).toBe("2026-11-05T12:42:00+00:00");
    expect(closedTimer.completed_within_target).toBe(true);
    const ticket = () => ({ ticket_id: "synthetic-resolution", ticket_code: code, title: "Синтетическая проверка решения", status: phase,
      requester_status_label: phase === "resolved" ? "Проверьте решение" : phase === "closed" ? "Закрыто" : "В работе",
      requester_resolution_summary: "Специалист предложил решение. Проверьте результат.",
      actions: { can_confirm_solution: phase === "resolved", can_reopen: phase === "resolved", can_rate_solution: phase === "resolved", can_send_message: phase === "in_progress", can_attach_files: false } });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    await page.route("**/api/**", async (route) => {
      const req = route.request(), path = new URL(req.url()).pathname;
      let data: unknown;
      if (path === "/api/web/session/me") data = { user_login: "synthetic-employee", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path === "/api/web/session/capabilities") data = {};
      else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
      else if (path === "/api/web/requester/consents") data = { consents: [] };
      else if (path === "/api/web/requester/tickets") data = { tickets: [ticket()] };
      else if (path === `/api/web/requester/tickets/${code}/close` || path === `/api/web/requester/tickets/${code}/reopen`) {
        commands.push({ path, body: req.postDataJSON() }); phase = path.endsWith("/close") ? "closed" : "in_progress";
        data = { ticket: ticket() };
      } else if (path === `/api/web/requester/tickets/${code}`) data = {
        ticket: ticket(), events: [],
        handling: { status_label: ticket().requester_status_label, assignee: { assigned: true, display_name: "Специалист" }, next_action_owner: phase === "closed" ? null : "requester", device: { state: "none" }, sla: { resolution: phase === "closed" ? closedTimer : { status: "paused", remaining_seconds: 3600 } } },
        messages: Array.from({ length: 45 }, (_, i) => ({ message_id: `m${i}`, from_role: i === 44 || i % 2 ? "support" : "user", text: i === 44 ? "Проблема решена. Для подтверждения используйте одну из кнопок ниже." : `Предыдущее сообщение ${i + 1}. Подробности проверки рабочего места.`, created_at: `2026-11-05T10:${String(i).padStart(2, "0")}:00Z` })),
      };
      else { unexpected.push(path); return route.fulfill({ status: 404, json: { status: "error" } }); }
      return route.fulfill({ json: { status: "success", data } });
    });
    await page.goto(`/app/requester/tickets/${code}`);
    const bar = page.getByRole("region", { name: "Действия по решению обращения" });
    const confirm = bar.getByRole("button", { name: "Подтвердить решение" });
    const reject = bar.getByRole("button", { name: "Проблема не решена", exact: true });
    await expect(confirm).toBeInViewport(); await expect(reject).toBeInViewport();
    await page.locator("#requester-chat-content").evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await expect(page.getByText("Проблема решена. Для подтверждения используйте одну из кнопок ниже.", { exact: true })).toBeInViewport();
    await expect(confirm).toBeInViewport(); await expect(reject).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("pending-controls.png") });
    await page.getByRole("button", { name: "Описание и история" }).click();
    await expect(confirm).toBeInViewport(); await expect(reject).toBeInViewport();
    await page.getByRole("button", { name: "Вернуться к чату" }).click();
    await bar.getByRole("button", { name: "Оценить решение" }).click();
    await expect(bar.getByRole("spinbutton", { name: "Оценка обращения" })).toBeVisible();
    await bar.getByRole("button", { name: "Оценить решение" }).click();
    await expect(confirm).toBeInViewport();
    await confirm.click();
    await expect(page.getByText("Решение подтверждено", { exact: true })).toBeVisible();
    await expect(bar).toHaveCount(0);
    await expect(page.getByText("Срок был нарушен", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("closed-sla.png") });
    expect(commands).toEqual([{ path: `/api/web/requester/tickets/${code}/close`, body: { reason: "requester_confirmed_resolution" } }]);

    phase = "resolved"; await page.reload();
    await expect(reject).toBeInViewport(); await reject.click();
    await bar.getByRole("textbox", { name: "Комментарий для возврата в работу" }).fill("Ошибка повторилась");
    await bar.getByRole("button", { name: "Вернуть в работу", exact: true }).click();
    await expect(page.getByText("Обращение возвращено в работу", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Ответ заявителя" })).toBeVisible();
    expect(commands[1]).toMatchObject({ path: `/api/web/requester/tickets/${code}/reopen`, body: { reason_comment: "Ошибка повторилась" } });
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
