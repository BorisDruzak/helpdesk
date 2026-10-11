import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSimulationPanel } from "./scenario-simulation";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([true, false])("preserves explicit unknown versus unchecked omission (unknown=%s)", async unknownSelected => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (body.steps.length) {
      return new Response(JSON.stringify({ status: "success", data: { state: { revision: 2, results: {}, history: ["questions"] }, current_step: { id: "review", kind: "review", title: "Проверка ответов" } } }), { headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify({ status: "success", data: { state: { revision: 1, results: {}, history: [] }, current_step: { id: "questions", kind: "form_page", title: "Принтер", fields: [{ key: "printer", label: "Модель", type: "text", allow_unknown: true }] } } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSimulationPanel id="scenario" revision={1} dirty={false} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  const unknown = await screen.findByRole("checkbox", { name: "Не знаю" });
  fireEvent.change(screen.getByRole("textbox", { name: "Модель" }), { target: { value: "temporary" } });
  fireEvent.click(unknown);
  expect(unknown).toBeChecked();
  if (!unknownSelected) { fireEvent.click(unknown); expect(unknown).not.toBeChecked(); }
  fireEvent.click(screen.getByRole("button", { name: "Продолжить проверку" }));
  await screen.findByRole("heading", { name: "Проверка ответов" });
  const sent = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body));
  expect(sent.steps[0].answers).toEqual(unknownSelected ? { printer: null } : {});
});

it.each([false, true])("shows canonical facts and processing with canonical OLA object (configured=%s)", async configured => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
    state: { revision: 3, results: {}, answers: { scope: "team" }, history: ["questions", "review"] },
    current_step: { id: "submit", kind: "submit_ticket", title: "Отправка" },
    processing: { priority: { priority_class: "P2", reason: "impact=team" }, routing: { queue_code: "print" },
      sla: { first_response_min: 30, resolution_min: 120 }, ola: configured ? { ack_min: 15, processing_min: 60 } : {},
      approval: { required: false }, closure: { requires_public_summary: true, requires_resolution_code: true },
      validated_facts: { affected_scope: "team" }, notification: { would_send: false, recipient_groups: ["queue"], channels: [] }, would_create_ticket: false },
  } }), { headers: { "Content-Type": "application/json" } })));
  render(<ScenarioSimulationPanel id="printer" revision={1} dirty={false} disabled={false} definition={{ scenario_key: "printer", title: "Печать", service_code: "it", offering_full_code: "it.printer", process_binding: { request_template_key: "printer" }, blocks: [
    { id: "questions", title: "Кого затронуло?", kind: "form_page", fields: [{ key: "scope", label: "Влияние", type: "radio", options: [{ value: "team", label: "Весь отдел" }], process_mapping: { fact_key: "affected_scope", roles: ["priority_impact"] } }] },
    { id: "review", title: "Проверка ответов", kind: "review" }, { id: "submit", title: "Отправка", kind: "submit_ticket" },
  ] }} />);
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  await screen.findByText("Весь отдел");
  expect(screen.getByText("Кого затронуло? → Проверка ответов → Отправка")).toBeInTheDocument();
  expect(screen.getByText(configured ? "Подтверждение поддержки: 15 мин.; обработка: 60 мин." : "Внутренние сроки поддержки не настроены.")).toBeInTheDocument();
  expect(screen.getByText("При закрытии обязательны итог для сотрудника и код решения.")).toBeInTheDocument();
  expect(screen.getByText("Уведомления не отправлялись. Правила для групп: участники очереди.")).toBeInTheDocument();
});

it("labels a configured failure outcome as simulation without an operation", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    expect(JSON.parse(String(init?.body)).diagnostic_outcomes).toEqual({ diagnostic: "timeout" });
    return new Response(JSON.stringify({ status: "success", data: { revision: 1,
      state: { revision: 1, results: { diagnostic: { status: "timeout", simulated: true, operation_created: false, consent_required: true } }, answers: {}, history: [] },
      current_step: { id: "review", kind: "review", title: "Проверка ответов", answers: [] },
    } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSimulationPanel id="scenario" revision={1} dirty={false} disabled={false} definition={{ scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Принтер", process_binding: { request_template_key: "printer" }, blocks: [
    { id: "diagnostic", kind: "diagnostic", title: "Проверка устройства", require_consent: true, transitions: [{ to: "review" }] }, { id: "review", kind: "review", title: "Проверка ответов" },
  ] }} />);
  fireEvent.change(screen.getByRole("combobox", { name: "Исход симуляции: Проверка устройства" }), { target: { value: "timeout" } });
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  await screen.findByText("Проверка устройства: Истёк срок ожидания");
  expect(screen.getByText("Симуляция — реальная операция не выполнялась.")).toBeInTheDocument();
  expect(screen.queryByText(/успешно/i)).not.toBeInTheDocument();
});

it("can acknowledge an optional instruction before a conditional transition", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (body.steps.length) expect(body.steps[0].current_result).toBe("acknowledged");
    return new Response(JSON.stringify({ status: "success", data: { revision: 1,
      state: { revision: body.steps.length + 1, results: {}, answers: {}, history: [] },
      current_step: { id: "instruction", kind: "instruction", title: "Проверьте бумагу", acknowledgment_required: false, content: { body: "Добавьте бумагу" } },
    } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSimulationPanel id="scenario" revision={1} dirty={false} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  const acknowledge = await screen.findByRole("checkbox", { name: "Инструкция выполнена" });
  fireEvent.click(acknowledge);
  fireEvent.click(screen.getByRole("button", { name: "Продолжить проверку" }));
  await screen.findByRole("button", { name: "Назад в проверке" });
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("simulates an explicitly allowed instruction escape without acknowledgment", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ status: "success", data: { revision: 1,
      state: { revision: body.steps.length + 1, results: {}, answers: {}, history: [] },
      current_step: body.steps.length ? { id: "review", kind: "review", title: "Проверьте ответы", answers: [] }
        : { id: "instruction", kind: "instruction", title: "Проверьте бумагу", acknowledgment_required: true, can_request_ticket: true, content: { body: "Добавьте бумагу" } },
    } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSimulationPanel id="scenario" revision={1} dirty={false} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  const escape = await screen.findByRole("button", { name: "Нужна помощь поддержки" });
  expect(screen.getByRole("button", { name: "Продолжить проверку" })).toBeDisabled();
  fireEvent.click(escape);
  await screen.findByRole("heading", { name: "Проверьте ответы" });
  const sent = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body));
  expect(sent.steps).toEqual([{ expected_block_id: "instruction", revision: 1, current_result: "request_ticket" }]);
  expect(fetchMock.mock.calls.every(([url]) => url.endsWith("/simulate"))).toBe(true);
});

it("sends typed answers through the server and shows actual dry-run processing", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    const initial = !body.steps.length;
    if (!initial) expect(body.steps[0]).toEqual({ expected_block_id: "question", revision: 1, answers: { summary: "Cannot print" } });
    return new Response(JSON.stringify({ status: "success", data: { revision: 3, state: { current_block_id: initial ? "question" : "submit", revision: initial ? 1 : 2, state: "active", answers: {}, history: [], results: {} },
      current_step: initial ? { id: "question", kind: "form_page", title: "Вопрос", fields: [{ key: "summary", type: "text", label: "Проблема", required: true }] } : { id: "submit", kind: "submit_ticket", title: "Отправка", answers: [] },
      processing: initial ? null : { priority: { priority_class: "P2" }, routing: { queue_code: "test-queue" }, sla: { resolution_min: 60 }, approval: { required: false }, would_create_ticket: false },
    } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSimulationPanel id="scenario" revision={3} dirty={false} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Начать проверку" }));
  fireEvent.change(await screen.findByLabelText(/Проблема/), { target: { value: "Cannot print" } });
  fireEvent.click(screen.getByRole("button", { name: "Продолжить проверку" }));
  await screen.findByText("Приоритет: P2");
  expect(screen.getByText("Очередь: test-queue")).toBeInTheDocument();
  expect(screen.getByText("Срок выполнения: 60 мин.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
});
