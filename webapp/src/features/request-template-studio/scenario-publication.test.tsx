import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPublication } from "./scenario-publication";
import { MemoryRouter } from "react-router-dom";
const definition = { scenario_key: "print", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", description: "Помощь с печатью", process_binding: { request_template_key: "print" },
  blocks: [{ id: "instruction", kind: "instruction" as const, title: "Проверьте бумагу", content: { body: "Добавьте бумагу в лоток" } }] };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(dirty = false, extra: Partial<React.ComponentProps<typeof ScenarioPublication>> = {}) {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><ScenarioPublication id="scenario" revision={2} dirty={dirty} disabled={false} definition={definition} offeringTitle="Проблемы с печатью" {...extra} /></QueryClientProvider></MemoryRouter>);
}
it("describes publication changes without exposing internal paths and template keys", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
    revision: 2, health: { health_status: "ok" }, readiness: { can_publish: true, variants_checked: 1, issues: [] },
    diff: [{ path: "blocks.instruction.transitions", before: null, after: [{ to: "internal_block_123" }] },
      { path: "process_binding.request_template_key", before: null, after: "internal_template_456" }], confirmation_token: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  mount();
  await screen.findByText("Проверено исходов: 1.");
  expect(screen.queryByText(/internal_block_123|internal_template_456|blocks\.instruction\.transitions/)).not.toBeInTheDocument();
});
it("requires reviewed diff and explicit confirmation before publishing saved revision", async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (url.endsWith("/publish-preview")) {
      expect(body).toEqual({ revision: 2 });
      return new Response(JSON.stringify({ status: "success", data: { revision: 2, health: { health_status: "ok" }, readiness: { can_publish: true, issues: [], variants_checked: 3 },
        diff: [{ path: "title", before: "Старое", after: "Новое" }], confirmation_token: "opaque-token", expires_at: "2099-01-01T00:00:00Z" } }), { headers: { "Content-Type": "application/json" } });
    }
    expect(body).toEqual({ revision: 2, confirm: true, confirmation_token: "opaque-token" });
    return new Response(JSON.stringify({ status: "success", data: { version: { version: 3, definition: { ...definition, title: "Опубликованный принтер" } } } }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  mount();
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
    revision: 2, health: { health_status: "ok" }, readiness: { can_publish: false, variants_checked: 0, issues: [{ code: "missing_route", message: "Нет маршрута" }] }, diff: [], confirmation_token: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  mount();
  await screen.findByText("Нет маршрута");
  expect(screen.queryByRole("button", { name: "Опубликовать сценарий" })).not.toBeInTheDocument();
});

it("requires saving edits before preparing publication", () => {
  mount(true);
  expect(screen.getByRole("button", { name: "Показать, что исправить" })).toBeDisabled();
});

it("checks immediately and highlighting existing issues does not request a new preview", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
    revision: 2, health: { health_status: "error" }, readiness: { can_publish: false, variants_checked: 0, issues: [{ code: "missing_route", path: "processing.defaults.route", message: "Нет маршрута" }] }, diff: [], confirmation_token: null,
  } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher); mount();
  await screen.findByText("Нет маршрута");
  expect(screen.getByRole("heading", { name: "1. Данные услуги" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "3. Обработка и сроки" })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Показать, что исправить" }));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(document.querySelector('[data-step="3"]')).toHaveAttribute("data-highlighted", "true");
});
it("offers explicit retry when the automatic check fails", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(new Response(JSON.stringify({status:"success",data:{revision:2,health:{health_status:"ok"},readiness:{can_publish:true,variants_checked:1,issues:[]},diff:[],confirmation_token:null}}), {headers:{"Content-Type":"application/json"}}));
  vi.stubGlobal("fetch", fetcher); mount();
  await screen.findByText("Не удалось проверить публикацию. Повторите проверку.");
  expect(screen.queryByRole("checkbox", {name:"Изменения проверены, подтверждаю публикацию"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Повторить проверку"}));
  await screen.findByText("Проверено исходов: 1.");
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("does not auto-check a dirty draft or show stale readiness", async () => {
  const fetcher=vi.fn();vi.stubGlobal("fetch",fetcher);mount(true);
  expect(screen.getByText("Изменения сохраняются автоматически. Проверка обновится после сохранения.")).toBeInTheDocument();
  await new Promise(resolve=>setTimeout(resolve,350));expect(fetcher).not.toHaveBeenCalled();
});
it("detects external policy repairs on returning to the window without changing the draft", async () => {
  let repaired = false;
  const fetcher=vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{revision:2,health:{health_status:"ok"},readiness:{can_publish:repaired,variants_checked:repaired?1:0,issues:repaired?[]:[{code:"missing_route",message:"Нет маршрута"}]},diff:[],confirmation_token:repaired?"test-confirmation":null,expires_at:repaired?"2099-01-01T00:00:00Z":null}}),{headers:{"Content-Type":"application/json"}}));
  vi.stubGlobal("fetch",fetcher);mount();await screen.findByText("Нет маршрута");repaired=true;
  fireEvent(window,new Event("focus"));
  expect(await screen.findByRole("checkbox",{name:"Изменения проверены, подтверждаю публикацию"})).not.toBeChecked();
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("marks an incomplete service name before autosave and only reveals its setting", () => {
  const fetcher=vi.fn(), onIssue=vi.fn();vi.stubGlobal("fetch",fetcher);
  mount(true,{definition:{...definition,title:""},onIssue});
  expect(document.querySelector('[data-step="1"]')).toHaveAttribute("data-state","problem");
  fireEvent.click(screen.getByRole("button",{name:"Показать, что исправить"}));
  expect(onIssue).toHaveBeenCalledWith(expect.objectContaining({step:0,metadataField:"title"}));
  expect(fetcher).not.toHaveBeenCalled();
});
