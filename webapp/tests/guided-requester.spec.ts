import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }, { width: 390, height: 768 }]) {
  for (const mode of viewport.width === 390 ? ["long-submit"] : ["self-service", "ticket", "escape-ticket", ...(viewport.width === 1366 || viewport.width === 820 ? ["blocked-ticket", "double-ticket"] : []), ...(viewport.width === 1366 ? ["long-submit", "closed-result"] : [])]) {
  test(`guided requester ${mode} server steps and resume ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(response.url()); });
    page.on("requestfailed", request => failures.push(request.url()));
    let revision = 1;
    let current = "questions";
    let answer = "";
    let created = false;
    let previews = 0;
    let submissions = 0;
    let detailReads = 0;
    let starts = 0;
    const longAnswers = Array.from({ length: 7 }, (_, index) => ({ key: `saved_${index}`, label: `Сохранённый ответ ${index + 1}`, type: "text", value: "",
      display_value: `${`Проверка ${index + 1}: сотрудник указал кабинет, время сбоя и действия до обращения. `.repeat(index === 6 ? 5 : 2)}Конец ответа ${index + 1}.` }));
    let releaseSubmit!: () => void;
    const submitGate = new Promise<void>(resolve => { releaseSubmit = resolve; });
    const unexpectedRoutes: string[] = [];
    function step() {
      return { id: "guided-session", revision, state: created ? "ticket_created" : current === "finish" ? "completed_self_service" : "active", linked_ticket_id: created ? "test-ticket" : null,
        back_targets: mode === "long-submit" && current === "submit" ? [{ id: "questions", title: "Описание проблемы" }, { id: "instruction", title: "Выполненные проверки" }, { id: "review", title: "Ответы сотрудника" }] : [],
        block: current === "questions" ? { id: current, kind: "form_page", title: "Что происходит с принтером?", fields: [
          { key: "summary", type: "text", label: "Опишите проблему", required: true, value: answer },
          ...Array.from({ length: 8 }, (_, index) => ({ key: `detail_${index}`, type: "text", label: `Уточнение ${index + 1}`, required: false })),
        ] } : current === "instruction" ? { id: current, kind: "instruction", title: "Проверьте питание", acknowledgment_required: true, can_request_ticket: mode === "escape-ticket",
          content: { format: "plain", body: "Убедитесь, что кабель питания подключён." } }
          : current === "resolved" ? { id: current, kind: "resolution_check", title: "Удалось восстановить печать?" }
          : current === "review" ? { id: current, kind: "review", title: "Проверьте ответы", answers: [{ key: "summary", label: "Проблема", type: "text", value: answer, display_value: answer }] }
          : current === "submit" ? { id: current, kind: "submit_ticket", title: "Отправка в поддержку", ...(mode === "long-submit" ? { answers: longAnswers } : {}) }
          : { id: "finish", kind: "finish", title: "Печать восстановлена", message: "Проблема решена без обращения" } };
    }
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      const method = route.request().method();
      let data: unknown;
      if (path === "/api/web/session/me") data = { user_login: "guided@example.test", actor_role: "user", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path.endsWith("/requester/bootstrap")) data = { profile: { person_id: "p1", display_name: "Сотрудник" }, account_summary: { linked_profile: true }, profile_completion: { complete: true, required_fields: [], missing_fields: [], blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true }, policies: {} };
      else if (path === "/api/web/requester/consents" && method === "GET") data = { consents: [] };
      else if (path === "/api/web/requester/tickets/test-ticket" && method === "GET" && created) {
        detailReads++;
        data = { ticket: { ticket_id: "test-ticket", ticket_code: "T-300001", title: "Помощь с принтером", description: answer,
          status: mode === "closed-result" ? "closed" : "new", status_label: mode === "closed-result" ? "Закрыта" : "Новая", requester_status_label: mode === "closed-result" ? "Закрыта" : "Принято поддержкой", resolution_confirmation_pending: false,
          ...(mode === "closed-result" ? { requester_resolution_summary: "Печать проверена, обращение закрыто." } : {}),
          actions: { can_send_message: mode !== "closed-result", can_attach_files: false, can_confirm_solution: false, can_rate_solution: mode === "closed-result", can_reopen: mode === "closed-result" } },
          messages: [{ message_id: "created-message", text: "Обращение принято. Поддержка скоро ответит.", from_role: "support", ts: "2026-11-02T09:00:00+05:00", attachments: [] }],
          events: [{ event_id: 1, event_type: "ticket_created", requester_timeline_text: "Обращение создано", ts: "2026-11-02T09:00:00+05:00" }] };
      }
      else if ((path === "/api/web/requester/request-scenarios/sessions" && method === "POST") || (path === "/api/web/requester/request-scenarios/sessions/guided-session" && method === "GET") || (/^\/api\/web\/requester\/request-scenarios\/sessions\/guided-session\/(answer|advance|submit|ticket-preview)$/.test(path) && method === "POST")) {
        if (path.endsWith("/sessions") && method === "POST") { starts++; if (created || current === "finish") { created = false; current = "questions"; revision = 1; answer = ""; } }
        if (path.endsWith("/sessions") && route.request().method() === "POST" && mode === "ticket") expect(route.request().postDataJSON()).toEqual({ offering_full_code: "workplace.printer", entry_point_key: "paper" });
        if (path.endsWith("/answer")) { const body = route.request().postDataJSON(); expect(body).toMatchObject({ revision: 1, expected_block_id: "questions" }); answer = body.answers.summary; current = "instruction"; revision++; }
        if (path.endsWith("/advance")) { const body = route.request().postDataJSON(); expect(body.revision).toBe(revision); if (mode === "escape-ticket" && current === "instruction") { expect(body.current_result).toBe("request_ticket"); current = "review"; } else current = current === "instruction" ? "resolved" : current === "review" ? "submit" : mode !== "self-service" ? "review" : "finish"; revision++; }
        if (path.endsWith("/submit")) { expect(route.request().postDataJSON()).toEqual({ revision, confirm: true, device_scope: "none" }); submissions++; if (mode === "double-ticket") await submitGate; created = true; revision++; }
        data = step();
        if (path.endsWith("/ticket-preview")) { expect(route.request().postDataJSON()).toEqual({ revision, device_scope: "none" }); previews++; data = { ok: mode !== "blocked-ticket" || previews > 1, expected_resolution: "до 4 ч", approval: { text: "Согласование не требуется" }, blockers: mode === "blocked-ticket" && previews === 1 ? ["Уточните место установки принтера перед отправкой."] : [], warnings: ["Проверьте доступность принтера.", ...(mode === "long-submit" ? ["Проверьте адрес установки: специалисту потребуется доступ к принтеру и рабочему месту сотрудника.", "Сохранённые ответы передаются в поддержку вместе с обращением. Их можно проверить перед отправкой."] : [])], would_create_ticket: false }; }
      } else if (path === "/api/web/notifications/unread_count" && method === "GET") { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else { unexpectedRoutes.push(`${method} ${path}`); await route.fulfill({ status: 501, json: { status: "error", error: "Unexpected fixture route" } }); return; }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/api/registry/options", route => route.fulfill({ json: { status: "success", data: { departments: [], locations: [] } } }));
    await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "test", forms: [{ key: "printer", title: "Не печатает", fields: [{ key: "legacy", label: "Старое поле", type: "text" }], availability_policy: { available_without_agent_binding: true } }] } } }));
    await page.route("**/api/service-catalog/current*", route => {
      if (new URL(route.request().url()).searchParams.has("q")) return route.fulfill({ json: { status: "ok", search: {
        results: [{ title: "Бумага застряла", description: "Помощь с бумагой", category: "Оборудование", help_mode: "guided",
          offering_full_code: "workplace.printer", entry_point_key: "paper", match_reason: "Совпало дополнительное поисковое выражение" }],
        suggestions: [], corrected_query: null,
      } } });
      return route.fulfill({ json: { status: "ok", catalog_version: "test", services: [{ service_code: "workplace", title: "Рабочее место", offerings: [{ offering_code: "printer", full_code: "workplace.printer", title: "Не печатает", request_template_key: "printer", guided_scenario_enabled: true, ...(mode === "ticket" ? { catalog_items: [{ key: "paper", title: "Бумага застряла", description: "Помощь с бумагой", synonyms: ["замятие"], entry_point_key: "paper", scenario_key: "printer", version_id: "v1", target_block_id: "questions" }] } : {}) }] }] } });
    });
    await page.goto(mode === "escape-ticket" ? "/app/requester/new/?offering=workplace.printer" : "/app/requester/new");
    if (["self-service", "blocked-ticket", "double-ticket", "long-submit", "closed-result"].includes(mode)) await page.getByRole("combobox", { name: "Категория обращения" }).selectOption({ label: "Не печатает" });
    if (mode === "ticket") {
      await page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }).fill("замятие");
      const result = page.getByRole("button", { name: /Бумага застряла/ });
      await expect(result).toBeInViewport({ ratio: 1 });
      await expect(page.getByText("Оборудование · Пошаговая помощь")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-search.png`) });
      await result.click();
    }
    await expect(page.getByRole("heading", { name: "Что происходит с принтером?" })).toBeVisible();
    await expect(page.getByText("Старое поле")).toHaveCount(0);
    await page.getByRole("textbox", { name: /Опишите проблему/ }).fill("Задание остаётся в очереди");
    const next = page.getByRole("button", { name: "Продолжить", exact: true });
    await expect(next).toBeInViewport({ ratio: 1 });
    await next.click();
    await expect(page.getByRole("heading", { name: "Проверьте питание" })).toBeFocused();
    await expect(next).toBeDisabled();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Проверьте питание" })).toBeVisible();
    if (mode === "escape-ticket") {
      await expect(page.getByRole("checkbox", { name: "Инструкция выполнена" })).not.toBeChecked();
      await page.getByRole("button", { name: "Нужна помощь поддержки" }).click();
      await expect(page.getByRole("heading", { name: "Проверьте ответы" })).toBeFocused();
    } else {
      await page.getByRole("checkbox", { name: "Инструкция выполнена" }).check();
      await next.click();
      await expect(page.getByRole("heading", { name: "Удалось восстановить печать?" })).toBeVisible();
      await page.getByRole("button", { name: mode !== "self-service" ? "Нет, нужна помощь" : "Да, решено" }).click();
    }
    if (mode !== "self-service") {
      await expect(page.getByText(answer)).toBeVisible();
      await next.click();
      await expect(page.getByRole("button", { name: "Проверить обработку" })).toHaveCount(0);
      await expect(page.getByText("до 4 ч", { exact: true })).toBeVisible();
      await expect(page.getByText("Согласование не требуется", { exact: true })).toBeVisible();
      await expect(page.getByText("Проверьте доступность принтера.", { exact: true })).toBeVisible();
      expect(submissions).toBe(0);
      if (mode === "blocked-ticket") {
        await expect(page.getByRole("alert").filter({ hasText: "Уточните место установки принтера перед отправкой." })).toBeVisible();
        await expect(page.getByRole("button", { name: "Создать обращение", exact: true })).toHaveCount(0);
        expect(submissions).toBe(0);
        await page.getByRole("button", { name: "Повторить обработку", exact: true }).click();
      }
      const submit = page.getByRole("button", { name: "Создать обращение" });
      if (mode === "long-submit") {
        const actions = page.getByRole("group", { name: "Действия шага", exact: true });
        await expect(actions.getByRole("button", { name: /^Вернуться:/ })).toHaveCount(3);
        for (const saved of longAnswers) {
          const row = page.getByText(saved.label, { exact: true }).locator("..");
          await row.scrollIntoViewIfNeeded();
          // Check painted hit targets at both ends, not only DOM visibility beneath a sticky footer.
          await expect.poll(() => row.evaluate(element => {
            const rect = element.getBoundingClientRect();
            return [rect.top + 3, rect.bottom - 3].every(y => {
              const hit = document.elementFromPoint(rect.left + Math.min(30, rect.width / 2), y);
              return y > 0 && y < innerHeight && hit !== null && element.contains(hit);
            });
          })).toBe(true);
        }
        const tail = page.getByText(longAnswers.at(-1)!.display_value, { exact: true });
        await tail.evaluate(element => element.scrollIntoView({ block: "end" }));
        await expect.poll(() => tail.evaluate(element => {
          const text = element.firstChild;
          if (!text) return false;
          const range = document.createRange();
          range.setStart(text, Math.max(0, (text.textContent?.length ?? 0) - 18)); range.setEnd(text, text.textContent?.length ?? 0);
          const rect = range.getBoundingClientRect();
          const hit = document.elementFromPoint(rect.left + Math.min(4, rect.width / 2), rect.top + rect.height / 2);
          return hit !== null && element.contains(hit);
        })).toBe(true);
        expect(submissions).toBe(0);
        await page.screenshot({ path: info.outputPath(`${viewport.width}-submit-answer-tail.png`) });
        await submit.scrollIntoViewIfNeeded();
        await expect(submit).toBeInViewport({ ratio: 1 });
        expect(await actions.evaluate(element => {
          const answers = element.previousElementSibling;
          return answers !== null && answers.getBoundingClientRect().bottom <= element.getBoundingClientRect().top;
        })).toBe(true);
        await page.screenshot({ path: info.outputPath(`${viewport.width}-submit-processing-actions.png`) });
      }
      // Submission processing now follows all saved content in normal document flow.
      await submit.scrollIntoViewIfNeeded();
      await expect(submit).toBeInViewport({ ratio: 1 });
      if (mode === "double-ticket") {
        // Both click handlers run in one browser task before React can disable the button.
        await submit.evaluate(button => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
        await expect.poll(() => submissions).toBe(1);
        await expect(page.getByRole("status").filter({ hasText: "Создаём обращение..." })).toBeVisible();
        releaseSubmit();
      } else await submit.click();
      await expect(page).toHaveURL(/\/app\/requester\/tickets\/test-ticket$/);
      await expect(page.getByRole("region", { name: "Чат обращения", exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Помощь с принтером", exact: true })).toBeVisible();
      await expect(page.getByText("Обращение принято. Поддержка скоро ответит.", { exact: true })).toBeVisible();
      expect(submissions).toBe(1);
      expect(previews).toBe(mode === "blocked-ticket" ? 2 : 1);
      const readsBeforeReload = detailReads;
      await page.reload();
      await expect(page.getByRole("heading", { name: "Помощь с принтером", exact: true })).toBeVisible();
      await expect(page.getByText("Обращение принято. Поддержка скоро ответит.", { exact: true })).toBeVisible();
      expect(detailReads).toBeGreaterThan(readsBeforeReload);
      expect(submissions).toBe(1);
      if (mode === "closed-result") {
        await expect(page.getByRole("region", { name: "Результат решения", exact: true }).getByText("Печать проверена, обращение закрыто.", { exact: true })).toBeVisible();
        const rating = page.getByRole("button", { name: "Оценить решение", exact: true });
        const reopen = page.getByRole("button", { name: "Проблема не решена", exact: true });
        await expect(rating).toHaveAttribute("aria-expanded", "false"); await expect(reopen).toHaveAttribute("aria-expanded", "false");
        await expect(page.getByRole("spinbutton", { name: "Оценка обращения", exact: true })).toHaveCount(0);
        await expect(page.getByRole("textbox", { name: "Комментарий для возврата в работу", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Подтвердить решение", exact: true })).toHaveCount(0);
        await rating.click();
        await expect(page.getByRole("spinbutton", { name: "Оценка обращения", exact: true })).toBeVisible();
        await expect(reopen).toHaveAttribute("aria-expanded", "false");
        await expect(page.getByRole("button", { name: "Отправить оценку", exact: true })).toBeVisible();
        await rating.click(); await reopen.click();
        await expect(page.getByRole("textbox", { name: "Комментарий для возврата в работу", exact: true })).toBeVisible();
        await expect(page.getByRole("spinbutton", { name: "Оценка обращения", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Вернуть в работу", exact: true })).toBeVisible();
        await reopen.click();
        expect(submissions).toBe(1);
      }
      if (mode === "escape-ticket" && viewport.width === 1366) {
        await page.goto("/app/requester/new/?offering=workplace.printer");
        await expect(page.getByRole("heading", { name: "Что происходит с принтером?", exact: true })).toBeVisible();
        await expect(page.getByRole("textbox", { name: /Опишите проблему/ })).toHaveValue("");
        expect(starts).toBe(2); expect(submissions).toBe(1);
        await page.reload();
        await expect(page.getByRole("heading", { name: "Что происходит с принтером?", exact: true })).toBeVisible();
        expect(starts).toBe(2); expect(submissions).toBe(1);
      }
    } else { await expect(page.getByText("Проблема решена без обращения")).toBeVisible(); expect(previews).toBe(0); expect(submissions).toBe(0); }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-requester-${mode}.png`) });
    expect(unexpectedRoutes).toEqual([]); expect(errors).toEqual([]); expect(failures).toEqual([]);
  });
  }
}

test("guided conditional Other projects the latest focused input before Continue and clears hidden answers", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  const errors: string[] = [], failures: string[] = [], unexpected: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
  page.on("requestfailed", request => {
    // Replacing a pending projection intentionally aborts that read, never a lifecycle command.
    if (new URL(request.url()).pathname.endsWith("/step-preview") && request.failure()?.errorText === "net::ERR_ABORTED") return;
    failures.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  const projections: Record<string, unknown>[] = [];
  let commands = 0;
  let releaseFirst!: () => void;
  const firstGate = new Promise<void>(resolve => { releaseFirst = resolve; });
  function step(answers: Record<string, unknown> = {}) {
    return { id: "conditional-session", revision: 1, state: "active", back_targets: [], block: { id: "questions", kind: "form_page", title: "Уточните предмет обращения", has_dynamic_fields: true, fields: [
      { key: "subject", label: "Предмет обращения", type: "select", required: true, options: [{ value: "known", label: "Принтер" }, { value: "other", label: "Другое" }] },
      { key: "description", label: "Описание проблемы", type: "text", required: true },
      ...(answers.subject === "other" ? [{ key: "subject_other", label: "Другой предмет обращения", type: "text", required: true }] : []),
    ] } };
  }
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method();
    let data: unknown;
    if (path === "/api/web/session/me") data = { user_login: "conditional@example.test", actor_role: "user", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
    else if (path === "/api/web/requester/bootstrap") data = { profile: { person_id: "p1", display_name: "Сотрудник" }, account_summary: { linked_profile: true }, profile_completion: { complete: true, required_fields: [], missing_fields: [], blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true }, policies: {} };
    else if (path === "/api/web/notifications/unread_count") { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    else if (path === "/api/web/requester/request-scenarios/sessions" && method === "POST") data = step();
    else if (path === "/api/web/requester/request-scenarios/sessions/conditional-session/step-preview" && method === "POST") {
      const body = route.request().postDataJSON();
      expect(body).toMatchObject({ revision: 1, expected_block_id: "questions" });
      projections.push(body.answers);
      data = step(body.answers);
      if (projections.length === 1) await firstGate;
    } else { if (path.includes("/request-scenarios/")) commands++; unexpected.push(`${method} ${path}`); await route.fulfill({ status: 501, json: { status: "error", error: "Unexpected conditional fixture route" } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  await page.route("**/api/registry/options", route => route.fulfill({ json: { status: "success", data: { departments: [], locations: [] } } }));
  await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "test", forms: [{ key: "other", title: "Другое", fields: [], availability_policy: { available_without_agent_binding: true } }] } } }));
  await page.route("**/api/service-catalog/current*", route => route.fulfill({ json: { status: "ok", catalog_version: "test", services: [{ service_code: "general", title: "Общие вопросы", offerings: [{ offering_code: "other", full_code: "general.other", title: "Другое", request_template_key: "other", guided_scenario_enabled: true }] }] } }));
  await page.goto("/app/requester/new/?offering=general.other");
  const subject = page.getByRole("combobox", { name: /Предмет обращения/ });
  const description = page.getByRole("textbox", { name: /Описание проблемы/ });
  const other = page.getByRole("textbox", { name: /Другой предмет обращения/ });
  await subject.selectOption("other");
  await expect.poll(() => projections.length).toBe(1);
  // Type while the first Other projection is held, and leave the description focused.
  await description.fill("Неизвестная программа перестала запускаться");
  await expect.poll(() => projections.some(answers => answers.subject === "other" && answers.description === "Неизвестная программа перестала запускаться")).toBe(true);
  await expect(description).toBeFocused();
  await expect(other).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(commands).toBe(0);
  releaseFirst();
  await other.fill("Внутренняя программа");
  await subject.selectOption("known");
  await expect(other).toHaveCount(0);
  await subject.selectOption("other");
  await expect(other).toBeVisible();
  await expect(other).toHaveValue("");
  await expect(description).toHaveValue("Неизвестная программа перестала запускаться");
  expect(projections.at(-1)).not.toHaveProperty("subject_other");
  expect(commands).toBe(0); expect(unexpected).toEqual([]); expect(errors).toEqual([]); expect(failures).toEqual([]);
});
