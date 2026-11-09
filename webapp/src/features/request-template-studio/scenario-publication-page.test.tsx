import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPublication } from "./scenario-publication";
import type { ScenarioPublicationPreview } from "./scenario-api";

const definition = { scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Печать", process_binding: { request_template_key: "printer" },
  entry_points: [{ key: "paper", title: "Нет бумаги", target_block_id: "submit", category_id: null }],
  blocks: [{ id: "submit", kind: "submit_ticket" as const, title: "Передать специалисту" }, { id: "done", kind: "finish" as const, title: "Печать восстановлена" }] };
const preview = { revision: 2, source_hash: "server-hash", health: { health_status: "ok" }, readiness: { can_publish: true, variants_checked: 2, issues: [] }, diff: [],
  confirmation_token: "opaque", expires_at: "2099-01-01T00:00:00Z", outcomes: [
    { terminal: "submit", kind: "ticket", entry_point_key: "paper", priority: { priority_class: "normal" }, routing: { queue_title: "Служба поддержки", queue_code: "support" }, sla: { first_response_min: 20, resolution_min: 180, time_basis: "business" }, approval_required: false },
    { terminal: "done", kind: "self_service", entry_point_key: null },
  ] } satisfies ScenarioPublicationPreview;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function response(value: unknown) { return new Response(JSON.stringify({ status: "success", data: value }), { headers: { "content-type": "application/json" } }); }
function mount(extra: Partial<React.ComponentProps<typeof ScenarioPublication>> = {}) {
  const cache = new QueryClient();
  const props = { id: "s", revision: 2, dirty: false, disabled: false, definition, ...extra };
  const view = render(<QueryClientProvider client={cache}><ScenarioPublication {...props} /></QueryClientProvider>);
  return { ...view, update: (changed: Partial<typeof props>) => view.rerender(<QueryClientProvider client={cache}><ScenarioPublication {...props} {...changed} /></QueryClientProvider>) };
}
it("shows authoritative outcomes by catalogue entrance, terminal, queue and actual SLA", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response(preview)));
  mount(); fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  const outcomes = await screen.findByRole("region", { name: "Проверенные исходы" });
  expect(within(outcomes).getByText("Нет бумаги")).toBeVisible();
  expect(within(outcomes).getByText("Передать специалисту")).toBeVisible();
  expect(within(outcomes).getByText("Служба поддержки")).toBeVisible();
  expect(within(outcomes).getByText("20 мин.")).toBeVisible();
  expect(within(outcomes).getByText("180 мин.")).toBeVisible();
  expect(within(outcomes).getByText("Рабочее время")).toBeVisible();
  expect(within(outcomes).getByText(/Без обращения в поддержку/)).toBeVisible();
  expect(within(outcomes).queryByText(/server-hash|support|opaque/)).not.toBeInTheDocument();
});
it("groups server issues by their editable area and jumps to the correct map block", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...preview, readiness: { can_publish: false, variants_checked: 0, issues: [
    { code: "missing_fallback", path: "blocks.submit.transitions", message: "Настройте иначе" },
    { code: "entry_category_unavailable", path: "entry_points.paper.category_id", message: "Категория скрыта" },
    { code: "sla_unavailable", message: "Нет срока" },
  ] }, confirmation_token: null })));
  const onIssue = vi.fn(); mount({ onIssue });
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(await screen.findByRole("heading", { name: "Карта и переходы" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Каталог и доступность" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Обработка и сроки" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Исправить: Передать специалисту" }));
  expect(onIssue).toHaveBeenCalledWith(expect.objectContaining({ blockId: "submit" }));
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});
it("rejects a preview bound to a different saved revision", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...preview, revision: 1 })));
  mount(); fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/изменил|повтор|заново/i);
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});
it("discards a pending preview after edits or saved revision changes", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const view = mount(); fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  view.update({ dirty: true, revision: 3 });
  await act(async () => { resolve(response(preview)); });
  expect(await screen.findByText("Сначала сохраните изменения.")).toBeVisible();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});
it("can recheck a new revision while an obsolete read is pending and ignores its late result", async () => {
  const resolves: ((value: Response) => void)[] = [];
  const fetchMock = vi.fn(() => new Promise<Response>(done => { resolves.push(done); }));
  vi.stubGlobal("fetch", fetchMock);
  const view = mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  view.update({ revision: 3 });
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await act(async () => { resolves[0](response(preview)); });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Проверка…" })).toBeDisabled();
  await act(async () => { resolves[1](response({ ...preview, revision: 3 })); });
  expect(screen.getByRole("checkbox")).toBeEnabled();
});
it("requires a fresh check after live catalogue visibility changes", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response(preview)));
  const view = mount({ offeringVisibility: "internal" });
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  fireEvent.click(await screen.findByRole("checkbox"));
  view.update({ offeringVisibility: "public" });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});
it("does not offer confirmation for an expired token", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...preview, expires_at: "2000-01-01T00:00:00Z" })));
  mount(); fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/срок|заново/i);
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});
