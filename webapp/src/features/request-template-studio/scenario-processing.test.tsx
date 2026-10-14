import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioProcessing } from "./scenario-processing";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const definition: ScenarioDraftDefinition = { scenario_key: "p", title: "Печать", service_code: "it", offering_full_code: "it.print", process_binding: { request_template_key: "p", policy_refs: { routing: "route" } }, blocks: [] };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it.each([["closure", "Закрытие обращения", "Код решения обязателен"], ["visibility", "Видимость обращения", "Новая публично"]])("opens a real %s editor without leaving or changing the service", async (_kind, label, control) => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } })));
  const change = vi.fn();
  render(<ScenarioProcessing definition={definition} disabled={false} onChange={change} />);
  fireEvent.click(await screen.findByRole("button", { name: `Создать правило: ${label}` }));
  expect(screen.getByRole("dialog", { name: `Настройка правила: ${label}` })).toBeVisible();
  expect(screen.getByLabelText(control)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Вернуться к услуге" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});
it("selects only published rules while preserving other processing and map data", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: { closure: [
    { code: "close", title: "Завершение с подтверждением", is_active: true, published_at: "2026-10-14" },
    { code: "draft", title: "Не опубликовано", is_active: true, published_at: null },
  ] } } }), { headers: { "content-type": "application/json" } })));
  const change = vi.fn();
  const view = render(<ScenarioProcessing definition={definition} disabled={false} onChange={change} focusPolicy="closure" />);
  const select = await screen.findByLabelText("Закрытие обращения");
  expect(select).toHaveFocus();
  expect(screen.queryByRole("option", { name: "Не опубликовано" })).not.toBeInTheDocument();
  fireEvent.change(select, { target: { value: "close" } });
  const next = change.mock.calls[0][0];
  expect(next).toEqual({ ...definition, process_binding: { ...definition.process_binding, policy_refs: { routing: "route", closure: "close" } } });
  view.rerender(<ScenarioProcessing definition={next} disabled={false} onChange={change} focusPolicy="closure" />);
  fireEvent.change(screen.getByLabelText("Закрытие обращения"), { target: { value: "" } });
  expect(change.mock.calls[1][0]).toEqual(definition);
});
it("shows a registry error and can retry without changing the map", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } })));
  const change = vi.fn();
  render(<ScenarioProcessing definition={definition} disabled={false} onChange={change} focusPolicy="visibility" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось загрузить политики обработки");
  fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку политик" }));
  expect(await screen.findByLabelText("Видимость обращения")).toHaveFocus();
  expect(screen.getAllByText(/Нет опубликованных правил/)).toHaveLength(8);
  expect(change).not.toHaveBeenCalled();
});

it("selects only published registry policies and keeps references local to the draft", async () => {
  const request = vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: { routing: [
    { code: "printer_route", title: "Поддержка печати", version: "1", is_active: true, published_at: "2026-10-11" },
    { code: "unpublished", title: "Черновая политика", version: "1", is_active: true, published_at: null },
  ] } } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", request);
  function Harness() {
    const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "printer", title: "Печать", service_code: "it", offering_full_code: "it.printer", process_binding: { request_template_key: "printer" }, blocks: [] });
    return <><ScenarioProcessing definition={definition} disabled={false} onChange={setDefinition} /><output>{definition.process_binding.policy_refs?.routing || "inherit"}</output></>;
  }
  render(<Harness />);
  await screen.findByRole("option", { name: "Поддержка печати" });
  expect(screen.queryByRole("option", { name: "Черновая политика" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Маршрут и очередь"), { target: { value: "printer_route" } });
  expect(screen.getByText("printer_route", { selector: "output" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Маршрут и очередь"), { target: { value: "" } });
  expect(screen.getByText("inherit", { selector: "output" })).toBeInTheDocument();
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
});
