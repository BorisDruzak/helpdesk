import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioWizard } from "./scenario-wizard";
import type { ScenarioCatalog, ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const definition: ScenarioDraftDefinition = { scenario_key: "print", service_code: "it", offering_full_code: "it.printer", title: "Печать", process_binding: { request_template_key: "print" }, entry_block_id: "first", blocks: [
  { id: "first", kind: "instruction", title: "Первый шаг", content: { body: "Проверьте бумагу" }, transitions: [{ to: "broken", when: null }] },
  { id: "broken", kind: "instruction", title: "Проверка принтера", content: { body: "Проверьте питание" }, transitions: [{ to: "missing", when: null }] },
] };
function mount(code: string, path: string) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({ status: "success", data: url.endsWith("/publish-preview") ? {
    health: { health_status: "ok" }, readiness: { can_publish: false, variants_checked: 0, issues: [{ code, path, message: "Исправьте ошибку" }] }, diff: [], confirmation_token: null,
  } : { policies: {} } }), { headers: { "Content-Type": "application/json" } })));
  const change = vi.fn();
  render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><ScenarioWizard definition={definition} detail={{ scenario: { id: "scenario" }, draft: { revision: 2, definition } } as ScenarioDetail} catalog={{ offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер" }], categories: [], services: [], scenarios: [] } as unknown as ScenarioCatalog} dirty={false} disabled={false} onChange={change} /></QueryClientProvider></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать" }));
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  return change;
}
it("opens the source of a broken transition and focuses its visible target", async () => {
  const change = mount("unknown_target", "blocks.broken.transitions");
  fireEvent.click(await screen.findByRole("button", { name: "Исправить: Проверка принтера" }));
  expect(screen.getByRole("group", { name: "Переход из «Проверка принтера»" })).toBeVisible();
  await waitFor(() => expect(screen.getByLabelText("Следующий блок")).toHaveFocus());
  expect(screen.getByLabelText("Следующий блок")).toBeVisible();

  expect(change).not.toHaveBeenCalled();
});
it.each([["routing_unavailable", "Маршрут и очередь"], ["sla_unavailable", "Сроки обслуживания"], ["closure_missing", "Закрытие обращения"]])("jumps %s to its policy control after registry loading", async (code, label) => {
  const change = mount(code, "process_binding");
  fireEvent.click(await screen.findByRole("button", { name: `Исправить: ${label}` }));
  await waitFor(() => expect(screen.getByLabelText(label)).toHaveFocus());
  expect(change).not.toHaveBeenCalled();
});
