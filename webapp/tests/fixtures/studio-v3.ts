import { expect, type Page } from "playwright/test";
import type { ScenarioDraftDefinition } from "../../src/features/request-template-studio/scenario-contract";

export async function installStudioV3Fixture(page: Page) {
  const errors: string[] = [], unexpected: string[] = [], writes: string[] = [];
  let revision = 1;
  let definition: ScenarioDraftDefinition = { schema_version: 3, scenario_key: "print", title: "Проблемы с печатью", service_code: "it", offering_full_code: "it.print", entry_block_id: "q1", process_binding: { request_template_key: "print" }, entry_points: [{ key: "main", title: "Проблемы с печатью", target_block_id: "q1" }, { key: "special", title: "Быстрый вход", target_block_id: "q3" }], processing: { routes: { support: { title: "Поддержка печати", queue_code: "support" } }, sla_profiles: { urgent: { title: "Срочный", first_response_minutes: 30, resolution_minutes: 120, time_basis: "calendar" }, standard: { title: "Стандартный", first_response_minutes: 120, resolution_minutes: 300, time_basis: "calendar" } }, defaults: { route: "support", sla_profile: "standard" }, assignment_mode: "last_matching_branch" }, blocks: [
    { id: "q1", title: "Тип проблемы", kind: "form_page", fields: [{ key: "issue", label: "Что не работает?", type: "radio", required: true, options: [{ value: "printer", label: "Принтер" }, { value: "network", label: "Сеть" }] }], transitions: [{ to: "q2" }] },
    { id: "q2", title: "Масштаб проблемы", kind: "form_page", fields: [{ key: "scope", label: "Кого затронуло?", type: "radio", required: true, options: [{ value: "department", label: "Весь отдел" }, { value: "single", label: "Один сотрудник" }] }], transitions: [{ to: "q3" }] },
    { id: "q3", title: "Возможность работать", kind: "form_page", fields: [{ key: "work", label: "Можно продолжать работу?", type: "radio", required: true, options: [{ value: "blocked", label: "Нет" }, { value: "can_work", label: "Да" }] }], transitions: [{ to: "logic" }] },
    { id: "logic", title: "Выбрать обработку", kind: "decision", transitions: [{ to: "end", priority: 10, when: { op: "and", conditions: [{ op: "eq", source: "answer", field: "issue", value: "printer" }, { op: "eq", source: "answer", field: "scope", value: "department" }, { op: "eq", source: "answer", field: "work", value: "blocked" }] }, processing: { route: "support", sla_profile: "urgent" } }, { to: "end" }] },
    { id: "end", title: "Передать в поддержку", kind: "submit_ticket" },
  ] };
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", request => errors.push(request.url()));
  page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  await page.route("**/api/web/**", async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    let data: unknown = {};
    if (path.endsWith("/session/me")) data = { user_login: "studio-fixture@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
    else if (path.endsWith("/request-studio/catalog")) data = { categories: [], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.print", service_code: "it", public_title: definition.title, request_template_key: "print" }], scenarios: [{ id: "v3", title: definition.title, schema_version: 3, status: "draft", offering_full_code: "it.print", issues: [] }], total: 1, offset: 0, limit: 100 };
    else if (path.endsWith("/helpdesk-model/policies")) data = { policies: {} };
    else if (path === "/api/web/settings") data = { queues: [{ id: 1, code: "support", name: "Поддержка рабочих мест", is_active: true }, { id: 2, code: "network", name: "Сетевые администраторы", is_active: true }, { id: 3, code: "retired", name: "Отключённая очередь", is_active: false }], calendars: [{ id: 8, code: "week", name: "Рабочая неделя", is_active: true }] };
    else if (path.endsWith("/scenarios/v3") || path.endsWith("/scenarios/v3/draft")) {
      if (request.method() === "PUT") { const body = request.postDataJSON(); expect(body.revision).toBe(revision); definition = body.definition; revision++; writes.push("draft"); }
      data = { scenario: { id: "v3", archived: false }, draft: { revision, definition } };
    } else if (path.endsWith("/scenarios/v3/simulate")) {
      const body = request.postDataJSON(); expect(body.revision).toBe(revision); writes.push("simulate");
      const answers: Record<string, unknown> = Object.assign({}, ...body.steps.map((step: { answers?: object }) => step.answers ?? {}));
      const current = ["q1", "q2", "q3", "end"][body.steps.length];
      const step = definition.blocks!.find(block => block.id === current)!;
      const urgent = answers.scope === "department", profile = urgent ? "urgent" : "standard";
      const map = { assignment_mode: "last_matching_branch", route: { key: "support", title: "Поддержка печати", queue_code: "support", source: { kind: "default" } }, sla_profile: { key: profile, ...definition.processing!.sla_profiles[profile], source: urgent ? { kind: "transition", block_id: "logic", transition_index: 0 } : { kind: "default" } }, trace: [{ block_id: "logic", transition_index: urgent ? 0 : 1, to: "end", matched: true, assignments: urgent ? { sla_profile: "urgent" } : {} }], condition_trace: [{ block_id: "logic", transition_index: 0, to: "end", selected: urgent, condition_evaluation: { op: "and", matched: urgent, children: [ { op: "eq", source: "answer", field: "issue", actual: answers.issue, value: "printer", present: true, matched: true }, { op: "eq", source: "answer", field: "scope", actual: answers.scope, value: "department", present: true, matched: urgent }, { op: "eq", source: "answer", field: "work", actual: answers.work, value: "blocked", present: true, matched: true }] } }] };
      data = { revision, state: { revision: body.steps.length + 1, current_block_id: current, history: body.steps.map((step: { expected_block_id: string }) => step.expected_block_id), answers, results: {} }, current_step: step, ...(current === "end" ? { map_processing: map, processing: { priority: { priority_class: urgent ? "P1" : "P3" }, routing: { queue_title: "Поддержка печати" }, sla: { first_response_min: definition.processing!.sla_profiles[profile].first_response_minutes, resolution_min: definition.processing!.sla_profiles[profile].resolution_minutes, first_response_due_preview: "2026-10-15T12:30:00Z", resolution_due_preview: "2026-10-15T14:00:00Z" }, approval: { required: urgent }, validated_facts: answers, map_processing: map, would_create_ticket: false } } : {}) };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    else unexpected.push(`${request.method()} ${path}`);
    await route.fulfill({ json: { status: "success", data } });
  });
  return { errors, unexpected, writes, definition: () => definition };
}
