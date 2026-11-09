import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioTerminalSla } from "./scenario-terminal-sla";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import type { ScenarioSimulation } from "./scenario-api";
function slaDefinition(): ScenarioDraftDefinition {
 return { schema_version: 4, scenario_key: "test", service_code: "test", offering_full_code: "test.test", title: "Test", process_binding: { request_template_key: "test" }, entry_block_id: "start",
  processing: { defaults: { route: "desk", sla_profile: "normal" }, routes: { desk: { title: "Desk", queue_code: "desk" } }, sla_profiles: {
   normal: { title: "Обычный", first_response_minutes: 30, resolution_minutes: 480, time_basis: "calendar" }, fast: { title: "Срочный", first_response_minutes: 5, resolution_minutes: 60, time_basis: "business", calendar_id: 3 },
  } }, blocks: [{ id: "start", kind: "navigation", title: "Начало", transitions: [{ to: "end" }] }, { id: "end", kind: "submit_ticket", title: "Обращение" }] };
}
vi.mock("../forms-builder/api", () => ({ fetchHelpdeskModelRegistry: vi.fn(async () => ({ policies: { sla: [{ code: "published", title: "Рабочее правило", is_active: true, published_at: "now" }, { code: "draft", title: "Черновик", is_active: true }] } })) }));
it("shows inherited values without writing and removes explicit fields on inheritance", () => {
 const definition = slaDefinition(), change = vi.fn(), block = { ...definition.blocks![1], kind: "submit_ticket" as const, sla_profile: "fast" };
 render(<ScenarioTerminalSla block={block} definition={{ ...definition, blocks: [definition.blocks![0], block] }} disabled={false} onChange={change} />);
 expect(screen.getByText(/Первый ответ: 5 мин/)).toBeInTheDocument(); expect(change).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText("Сроки для сотрудника при создании обращения"), { target: { value: "" } });
 expect(change.mock.lastCall![0]).not.toHaveProperty("sla_profile"); expect(change.mock.lastCall![0]).not.toHaveProperty("policy_ref");
});
it("lets an author select a final profile and test the path", () => {
 const definition = slaDefinition(), change = vi.fn(), test = vi.fn();
 render(<ScenarioTerminalSla block={definition.blocks![1]} definition={definition} disabled={false} onChange={change} onTestPath={test} />);
 fireEvent.change(screen.getByLabelText("Сроки для сотрудника при создании обращения"), { target: { value: "fast" } });
 expect(change.mock.lastCall![0]).toMatchObject({ sla_profile: "fast" });
 fireEvent.click(screen.getByRole("button", { name: "Проверить путь" })); expect(test).toHaveBeenCalledOnce();
});
it("selects and clears an explicit final route independently of SLA", () => {
 const definition = slaDefinition(), change = vi.fn(), block = { ...definition.blocks![1], kind: "submit_ticket" as const, sla_profile: "fast", route: "desk" };
 render(<ScenarioTerminalSla block={block} definition={definition} disabled={false} onChange={change} />);
 fireEvent.change(screen.getByLabelText("Маршрут при создании обращения"), { target: { value: "" } });
 expect(change.mock.lastCall![0]).not.toHaveProperty("route"); expect(change.mock.lastCall![0]).not.toHaveProperty("routing_policy_ref");
 expect(change.mock.lastCall![0]).toMatchObject({ sla_profile: "fast" });
 fireEvent.change(screen.getByLabelText("Маршрут при создании обращения"), { target: { value: "desk" } });
 expect(change.mock.lastCall![0]).toMatchObject({ route: "desk", sla_profile: "fast" });
});
it("loads only published policy choices and never invents policy durations", async () => {
 const definition = slaDefinition(); definition.processing = null; const change = vi.fn();
 render(<ScenarioTerminalSla block={definition.blocks![1]} definition={definition} disabled={false} onChange={change} />);
 await waitFor(() => expect(screen.getByRole("option", { name: "Рабочее правило" })).toBeInTheDocument());
 expect(screen.queryByRole("option", { name: "Черновик" })).not.toBeInTheDocument();
 expect(screen.getByText(/Сроки определит сервер/)).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Сроки для сотрудника при создании обращения"), { target: { value: "published" } });
 expect(change.mock.lastCall![0]).toMatchObject({ policy_ref: "published" }); expect(change.mock.lastCall![0]).not.toHaveProperty("sla_profile");
});
it("does not enable terminal settings on old schemas or self service", () => {
 const definition = slaDefinition(); definition.schema_version = 3;
 const { rerender } = render(<ScenarioTerminalSla block={definition.blocks![1]} definition={definition} disabled={false} onChange={vi.fn()} />);
 expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
 rerender(<ScenarioTerminalSla block={{ id: "done", kind: "finish", title: "Готово" }} definition={definition} disabled={false} onChange={vi.fn()} />);
 expect(screen.getByText(/не создаётся/)).toBeInTheDocument(); expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
});
it("shows exact actual path SLA, route, and terminal source from simulation", () => {
 const definition = slaDefinition(), block = definition.blocks![1];
 const result = { current_block: block, state: { current_block_id: "end", history: ["start"] }, processing: { sla: { first_response_min: 12, resolution_min: 144, time_basis: "business", source: { kind: "terminal", block_id: "end" } }, routing: { queue_title: "Инженеры" } } } as unknown as ScenarioSimulation;
 render(<ScenarioTerminalSla block={block} definition={definition} disabled={false} onChange={vi.fn()} result={result} />);
 expect(screen.getByRole("heading", { name: "Проверенные сроки для сотрудника" })).toBeInTheDocument();
 expect(screen.getByText(/Первый ответ: 12 мин/)).toHaveTextContent("решение: 144 мин.");
 expect(screen.getByText(/Очередь: Инженеры/)).toBeInTheDocument();
 expect(screen.getByText(/Источник: завершение «Обращение»/)).toBeInTheDocument();
});
