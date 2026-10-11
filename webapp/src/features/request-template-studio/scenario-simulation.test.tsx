import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSimulationPanel } from "./scenario-simulation";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

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
