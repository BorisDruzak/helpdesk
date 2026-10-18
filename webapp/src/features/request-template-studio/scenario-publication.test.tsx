import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPublication } from "./scenario-publication";
import { MemoryRouter } from "react-router-dom";
const definition = { scenario_key: "print", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", description: "Помощь с печатью", process_binding: { request_template_key: "print" },
  blocks: [{ id: "instruction", kind: "instruction" as const, title: "Проверьте бумагу", content: { body: "Добавьте бумагу в лоток" } }] };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(dirty = false) {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><ScenarioPublication id="scenario" revision={2} dirty={dirty} disabled={false} definition={definition} offeringTitle="Проблемы с печатью" /></QueryClientProvider></MemoryRouter>);
}
it("describes publication changes without exposing internal paths and template keys", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
    health: { health_status: "ok" }, readiness: { can_publish: true, variants_checked: 1, issues: [] },
    diff: [{ path: "blocks.instruction.transitions", before: null, after: [{ to: "internal_block_123" }] },
      { path: "process_binding.request_template_key", before: null, after: "internal_template_456" }], confirmation_token: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  mount(); fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  await screen.findByText("Проверено исходов: 1.");
  expect(screen.queryByText(/internal_block_123|internal_template_456|blocks\.instruction\.transitions/)).not.toBeInTheDocument();
});
it("requires reviewed diff and explicit confirmation before publishing saved revision", async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (url.endsWith("/publish-preview")) {
      expect(body).toEqual({ revision: 2 });
      return new Response(JSON.stringify({ status: "success", data: { health: { health_status: "ok" }, readiness: { can_publish: true, issues: [], variants_checked: 3 },
        diff: [{ path: "title", before: "Старое", after: "Новое" }], confirmation_token: "opaque-token", expires_at: "2099-01-01T00:00:00Z" } }), { headers: { "Content-Type": "application/json" } });
    }
    expect(body).toEqual({ revision: 2, confirm: true, confirmation_token: "opaque-token" });
    return new Response(JSON.stringify({ status: "success", data: { version: { version: 3, definition: { ...definition, title: "Опубликованный принтер" } } } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  await screen.findByText("Старое");
  const publish = screen.getByRole("button", { name: "Опубликовать сценарий" });
  expect(publish).toBeDisabled();
  expect(screen.queryByText("opaque-token")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" }));
  fireEvent.click(publish);
  await screen.findByText("Опубликована версия 3.");
  expect(screen.getByRole("link", { name: "Открыть сценарий сотрудника" })).toHaveAttribute("href", "/app/requester/new?offering=it.printer");
  expect(screen.getByText("Услуга: Проблемы с печатью")).toBeVisible();
  expect(screen.getByText("Опубликованный принтер")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Что увидит сотрудник" })).toBeVisible();
  fireEvent.click(screen.getByText("1. Проверьте бумагу"));
  expect(screen.getByText("Добавьте бумагу в лоток")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});

it("does not treat Health OK as publication readiness", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
    health: { health_status: "ok" }, readiness: { can_publish: false, variants_checked: 0, issues: [{ code: "missing_route", message: "Нет маршрута" }] }, diff: [], confirmation_token: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  await screen.findByText("Нет маршрута");
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});

it("requires saving edits before preparing publication", () => {
  mount(true);
  expect(screen.getByRole("button", { name: "Подготовить публикацию" })).toBeDisabled();
});

const readyPreview = { health: { health_status: "ok" }, readiness: { can_publish: true, issues: [], variants_checked: 220 }, diff: [], confirmation_token: "reviewed-token" };
function response(data: unknown) { return new Response(JSON.stringify({ status: "success", data }), { headers: { "Content-Type": "application/json" } }); }
function deferredResponse() {
  let resolve!: (response: Response) => void;
  let reject!: (cause: Error) => void;
  const promise = new Promise<Response>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
it("explains delayed checking and publishing while preventing repeat actions until success", async () => {
  const checking = deferredResponse(), publishing = deferredResponse();
  const fetcher = vi.fn().mockReturnValueOnce(checking.promise).mockReturnValueOnce(publishing.promise);
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(screen.getByRole("status")).toHaveTextContent("Проверяем публикацию");
  const checkingButton = screen.getByRole("button", { name: "Проверяем публикацию…" });
  expect(checkingButton).toBeDisabled(); fireEvent.click(checkingButton); expect(fetcher).toHaveBeenCalledTimes(1);
  await act(async () => { checking.resolve(response(readyPreview)); });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Опубликовать сценарий" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" }));
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать сценарий" }));
  expect(screen.getByRole("status")).toHaveTextContent("Публикуем сценарий");
  const publishingButton = screen.getByRole("button", { name: "Публикуем сценарий…" });
  expect(publishingButton).toBeDisabled(); fireEvent.click(publishingButton); expect(fetcher).toHaveBeenCalledTimes(2);
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ revision: 2, confirm: true, confirmation_token: "reviewed-token" });
  await act(async () => { publishing.resolve(response({ version: { version: 1, definition } })); });
  await screen.findByText("Опубликована версия 1.");
  await waitFor(() => expect(screen.getByRole("button", { name: "Подготовить публикацию" })).toBeEnabled());
  expect(screen.queryByText(/Проверяем публикацию|Публикуем сценарий/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});
it("clears the checking status and re-enables preparation after a failed request", async () => {
  const checking = deferredResponse(); vi.stubGlobal("fetch", vi.fn(() => checking.promise)); mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  expect(screen.getByRole("status")).toHaveTextContent("Проверяем публикацию");
  await act(async () => { checking.reject(new Error("network unavailable")); });
  expect(screen.getByRole("alert")).toHaveTextContent("Не удалось проверить публикацию");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Подготовить публикацию" })).toBeEnabled();
});
it("clears the publishing status after an error and requires a new reviewed preview", async () => {
  const publishing = deferredResponse();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(readyPreview)).mockReturnValueOnce(publishing.promise)); mount();
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" }));
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать сценарий" }));
  expect(screen.getByRole("status")).toHaveTextContent("Публикуем сценарий");
  await act(async () => { publishing.resolve(new Response(JSON.stringify({ status: "error", error_code: "CONFLICT" }), { status: 409, headers: { "Content-Type": "application/json" } })); });
  expect(screen.getByRole("alert")).toHaveTextContent("Подготовьте публикацию заново");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Подготовить публикацию" })).toBeEnabled();
});
it.each(["checking", "publishing"])("resets a stale %s status when the saved revision changes", async phase => {
  const pending = deferredResponse();
  vi.stubGlobal("fetch", phase === "checking" ? vi.fn(() => pending.promise) : vi.fn().mockResolvedValueOnce(response(readyPreview)).mockReturnValueOnce(pending.promise));
  const cache = new QueryClient();
  const ui = (revision: number) => <QueryClientProvider client={cache}><ScenarioPublication id="scenario" revision={revision} dirty={false} disabled={false} definition={definition} /></QueryClientProvider>;
  const view = render(ui(2));
  fireEvent.click(screen.getByRole("button", { name: "Подготовить публикацию" }));
  if (phase === "publishing") {
    fireEvent.click(await screen.findByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" }));
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать сценарий" }));
  }
  expect(screen.getByRole("status")).toHaveTextContent(phase === "checking" ? "Проверяем публикацию" : "Публикуем сценарий");
  view.rerender(ui(3));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Подготовить публикацию" })).toBeEnabled();
  await act(async () => { pending.resolve(response(phase === "checking" ? readyPreview : { version: { version: 1, definition } })); });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Открыть сценарий сотрудника" })).not.toBeInTheDocument();
});
