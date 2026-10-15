import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioProcessing } from "./scenario-processing";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const definition: ScenarioDraftDefinition = { scenario_key: "p", title: "Печать", service_code: "it", offering_full_code: "it.print", process_binding: { request_template_key: "p", policy_refs: { routing: "route" } }, blocks: [] };
it.each(["closure", "visibility"])("explains every %s field in Russian without exposing configuration keys", async kind => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } })));
  render(<ScenarioProcessing definition={definition} disabled={false} onChange={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: `Создать правило: ${kind === "closure" ? "Закрытие обращения" : "Видимость обращения"}` }));
  const dialog = screen.getByRole("dialog");
  expect(dialog).not.toHaveTextContent(/Evidence|Worklog|fixed_remote|internal_notes|public_messages|Support/);
  for (const input of dialog.querySelectorAll("input")) {
    expect(input).toHaveAccessibleName();
    expect(input).toHaveAccessibleDescription();
  }
  if (kind === "closure") expect(screen.getByLabelText("Запись о выполненной работе обязательна")).toBeVisible();
  else expect(screen.getByLabelText("Показывать сотруднику: Переписка с сотрудником")).toBeChecked();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it.each([["closure", "Закрытие обращения"], ["visibility", "Видимость обращения"]])("publishes %s through the registry and applies its reference only after explicit selection", async (kind, label) => {
  let payload: Record<string, unknown> = {};
  const request = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/publish")) {
      payload = JSON.parse(options!.body as string);
      return new Response(JSON.stringify({ status: "success", data: { policy: { ...payload, version: "1", is_active: true, published_at: "2026-10-14" }, message: "Опубликовано" } }), { headers: { "content-type": "application/json" } });
    }
    return new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", request);
  const change = vi.fn();
  render(<ScenarioProcessing definition={definition} disabled={false} onChange={change} />);
  fireEvent.click(await screen.findByRole("button", { name: `Создать правило: ${label}` }));
  fireEvent.change(screen.getByLabelText("Название правила"), { target: { value: "Правило печати" } });
  fireEvent.click(screen.getByRole("button", { name: "Проверить и продолжить" }));
  expect(request).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать правило" }));
  await screen.findByRole("button", { name: "Применить к услуге" });
  expect(screen.getByText(/Изменения услуги ещё не опубликованы/)).toHaveTextContent("Автосохранение");
  expect(payload).toMatchObject({ kind, title: "Правило печати", scope_level: "request_template", scope_ref: null });
  expect(request.mock.calls[1][0]).toBe("/api/web/admin/helpdesk-model/policies/publish");
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Применить к услуге" }));
  expect(change).toHaveBeenCalledWith({ ...definition, process_binding: { ...definition.process_binding, policy_refs: { routing: "route", [kind]: payload.code } } });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(request).toHaveBeenCalledTimes(2); // No service save, ticket creation or publication.
});
it("preserves source policy extras and reports server errors without losing edits", async () => {
  let submitted: any;
  const source = { kind: "closure", code: "shared", title: "Общее закрытие", is_active: true, published_at: "2026-10-14", config: { custom_compatibility: { keep: true }, before_resolved: { require_public_summary: true, preserved: 1 } } };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/publish")) { submitted = JSON.parse(options!.body as string); return new Response(JSON.stringify({ status: "error", error: "Сервер отклонил правило" }), { status: 400, headers: { "content-type": "application/json" } }); }
    return new Response(JSON.stringify({ status: "success", data: { policies: { closure: [source] } } }), { headers: { "content-type": "application/json" } });
  }));
  const change = vi.fn();
  render(<ScenarioProcessing definition={{...definition, process_binding: {...definition.process_binding, policy_refs: {closure: "shared"}}}} disabled={false} onChange={change} />);
  fireEvent.click(await screen.findByRole("button", { name: "Настроить выбранное правило: Закрытие обращения" }));
  expect(screen.getByLabelText("Результат решения обязателен")).not.toBeChecked();
  expect(screen.getByLabelText("Сотрудник должен подтвердить решение")).not.toBeChecked();
  expect(screen.getByLabelText("Закрыть автоматически через (дней)")).toHaveValue(0);
  fireEvent.click(screen.getByLabelText("Описание решения для сотрудника обязательно"));
  fireEvent.click(screen.getByRole("button", { name: "Проверить и продолжить" }));
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать правило" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Сервер отклонил правило");
  expect(submitted.code).not.toBe("shared");
  expect(submitted.config).toEqual({...source.config, before_resolved: {...source.config.before_resolved, require_public_summary: false}});
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Изменить настройки" }));
  expect(screen.getByLabelText("Описание решения для сотрудника обязательно")).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Вернуться к услуге" }));
  expect(screen.getByText("Есть несохранённые изменения правила.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Закрыть без сохранения" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("disables creation in read-only Studio and rejects a blank title before publishing", async () => {
  const request = vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", request);
  const view = render(<ScenarioProcessing definition={definition} disabled onChange={vi.fn()} />);
  expect(await screen.findByRole("button", { name: "Создать правило: Закрытие обращения" })).toBeDisabled();
  view.rerender(<ScenarioProcessing definition={definition} disabled={false} onChange={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Создать правило: Закрытие обращения" }));
  fireEvent.change(screen.getByLabelText("Название правила"), { target: { value: " " } });
  fireEvent.click(screen.getByRole("button", { name: "Проверить и продолжить" }));
  expect(within(screen.getByRole("dialog")).getByRole("alert")).toHaveTextContent("Укажите название правила");
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
});
it("shows legacy closure requirements using the same defaults as the runtime", async () => {
  const source = { kind: "closure", code: "legacy", title: "Старое правило", is_active: true, published_at: "2026-10-14", config: { require_resolution_code: true, require_public_summary: false, auto_close_after_days: 7, require_evidence_for_priorities: ["p0"], evidence: { require_diagnostic_evidence_for_priorities: ["P1"] } } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: { closure: [source] } } }), { headers: { "content-type": "application/json" } })));
  render(<ScenarioProcessing definition={{...definition, process_binding: {...definition.process_binding, policy_refs: {closure: "legacy"}}}} disabled={false} onChange={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Настроить выбранное правило: Закрытие обращения" }));
  expect(screen.getByLabelText("Результат решения обязателен")).toBeChecked();
  expect(screen.getByLabelText("Описание решения для сотрудника обязательно")).not.toBeChecked();
  expect(screen.getByLabelText("Сотрудник должен подтвердить решение")).toBeChecked();
  expect(screen.getByLabelText("Закрыть автоматически через (дней)")).toHaveValue(7);
  expect(screen.getByLabelText("Подтверждение решения для приоритета P0")).toBeChecked();
  expect(screen.getByLabelText("Подтверждение решения для приоритета P1")).toBeChecked();
  fireEvent.click(screen.getByLabelText("Подтверждение решения для приоритета P1"));
  expect(screen.getByLabelText("Подтверждение решения для приоритета P1")).not.toBeChecked();
  expect(screen.getByLabelText("Подтверждение решения для приоритета P0")).toBeChecked();
});
