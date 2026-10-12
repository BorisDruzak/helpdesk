import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPurpose } from "./scenario-purpose";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

afterEach(() => vi.unstubAllGlobals());
it("keeps offering creation unavailable when templates fail and allows retry without losing input", async () => {
  const request = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(new Response(JSON.stringify({ status: "success", data: { request_templates: [] } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", request);
  const catalog = { services: [{ code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" }], offerings: [], categories: [] } as unknown as ScenarioCatalog;
  const definition = { scenario_key: "test", title: "Тест", service_code: "", offering_full_code: "", process_binding: { request_template_key: "" } };
  render(<QueryClientProvider client={new QueryClient()}><ScenarioPurpose definition={definition} catalog={catalog} disabled={false} existing={false} onChange={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Создать услугу здесь" }));
  fireEvent.change(screen.getByLabelText("Название услуги"), { target: { value: "Моя услуга" } });
  fireEvent.click(await screen.findByRole("button", { name: "Повторить загрузку шаблонов" }));
  await screen.findByText("Нет опубликованных шаблонов обработки. Подготовьте шаблон в существующем реестре Helpdesk.");
  expect(screen.getByLabelText("Название услуги")).toHaveValue("Моя услуга");
  expect(screen.getByRole("button", { name: "Создать черновик услуги" })).toBeDisabled();
  expect(request).toHaveBeenCalledTimes(2);
});
it("creates only a draft offering inline, binds publication intent and preserves current edits", async () => {
  let complete!: (response: Response) => void;
  let saved: Record<string, unknown> = {};
  const request = vi.fn((url: unknown, options?: RequestInit) => {
    if (String(url).endsWith("/helpdesk-model/policies")) return Promise.resolve(new Response(JSON.stringify({ status: "success", data: { request_templates: [
      { template_code: "printer", version: "1", public_title: "Проблема печати", ticket_type: "incident", is_active: true, published_at: "2026-01-01" },
      { template_code: "hidden", version: "1", public_title: "Неопубликованный шаблон", is_active: true, published_at: null }
    ] } }), { headers: { "Content-Type": "application/json" } }));
    saved = JSON.parse(String(options?.body));
    expect(url).toBe("/api/web/admin/service-catalog/offerings/save-draft");
    return new Promise<Response>(resolve => { complete = resolve; });
  });
  vi.stubGlobal("fetch", request);
  const catalog = { services: [{ code: "workplace", public_title: "Рабочее место", lifecycle_status: "published", visibility: "public" }, { code: "hidden", public_title: "Закрытый раздел", lifecycle_status: "published", visibility: "internal" }], offerings: [], categories: [], scenarios: [], total: 0, offset: 0, limit: 100 } as ScenarioCatalog;
  function Harness() {
    const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "printer", title: "Мой сценарий", service_code: "", offering_full_code: "", process_binding: { request_template_key: "" } });
    return <><ScenarioPurpose definition={definition} catalog={catalog} disabled={false} existing={false} onChange={setDefinition} /><output aria-label="Совместная публикация">{String(definition.publish_offering)}</output></>;
  }
  render(<QueryClientProvider client={new QueryClient()}><Harness /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Создать услугу здесь" }));
  await screen.findByRole("option", { name: "Проблема печати" });
  expect(screen.queryByRole("option", { name: "Закрытый раздел" })).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Неопубликованный шаблон" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Название услуги"), { target: { value: "Не печатает" } });
  fireEvent.change(screen.getByLabelText("Шаблон обработки"), { target: { value: "printer" } });
  fireEvent.change(screen.getByLabelText("Тип запроса"), { target: { value: "software_install" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать черновик услуги" }));
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
  expect(saved).toMatchObject({ service_code: "workplace", public_title: "Не печатает", lifecycle_status: "draft", visibility: "public", request_type: "service_request", metadata: { studio_profile: "software_install" }, request_template_key: "printer", ticket_type_code: "incident" });
  expect(saved.code).toMatch(/^scenario_[a-f0-9]{32}$/);
  fireEvent.change(screen.getByLabelText("Название сценария"), { target: { value: "Последнее название" } });
  complete(new Response(JSON.stringify({ status: "ok", offering: { ...saved, full_code: `workplace.${saved.code}` } }), { headers: { "Content-Type": "application/json" } }));
  await waitFor(() => expect(screen.getByLabelText("Услуга")).toHaveValue(`workplace.${saved.code}`));
  expect(screen.getByLabelText("Название сценария")).toHaveValue("Последнее название");
  expect(screen.getByLabelText("Совместная публикация")).toHaveTextContent("true");
  expect(request).toHaveBeenCalledTimes(2);
});
it("creates a category inside the purpose step and preserves the unsaved scenario", async () => {
  let complete!: (response: Response) => void;
  let categoryInput: Record<string, unknown> = {};
  const request = vi.fn((_url: unknown, options: RequestInit) => {
    const input = JSON.parse(String(options.body));
    categoryInput = input;
    expect(input.service_code).toBe("workplace");
    expect(input.parent_id).toBe("printers");
    return new Promise<Response>(resolve => { complete = resolve; });
  });
  vi.stubGlobal("fetch", request);
  const catalog = { services: [{ code: "other", public_title: "Другое", lifecycle_status: "published", visibility: "internal" }, { code: "workplace", public_title: "Рабочее место", lifecycle_status: "published", visibility: "internal" }], offerings: [{ code: "printer_issue", full_code: "workplace.printer_issue", service_code: "workplace", public_title: "Не печатает", request_template_key: "printer", lifecycle_status: "published", visibility: "internal" }], categories: [{ id: "printers", service_code: "workplace", parent_id: null, slug: "printers", title: "Принтеры и МФУ", description: "", sort_order: 0, visibility: "internal", revision: 1, lifecycle_status: "draft" }], scenarios: [], total: 0, offset: 0, limit: 100 } as ScenarioCatalog;
  function Harness() {
    const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "printer", title: "Несохранённое название", description: "Мой черновик", service_code: "workplace", offering_full_code: "workplace.printer_issue", category_id: "printers", process_binding: { request_template_key: "printer" }, blocks: [] });
    return <ScenarioPurpose definition={definition} catalog={catalog} disabled={false} existing={false} onChange={setDefinition} />;
  }
  render(<QueryClientProvider client={new QueryClient()}><Harness /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Создать категорию здесь" }));
  expect(screen.getByLabelText("Сервис")).toHaveValue("workplace");
  expect(screen.getByLabelText("Сервис")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Название категории"), { target: { value: "Проблемы с печатью" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить категорию" }));
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText("Название сценария"), { target: { value: "Последнее название" } });
  fireEvent.change(screen.getByLabelText("Описание"), { target: { value: "Последнее описание" } });
  complete(new Response(JSON.stringify({ status: "success", data: { ...categoryInput, id: "printing", revision: 1 } }), { headers: { "Content-Type": "application/json" } }));
  await waitFor(() => expect(screen.getByLabelText("Подкатегория")).toHaveValue("printing"));
  expect(screen.getByLabelText("Название сценария")).toHaveValue("Последнее название");
  expect(screen.getByLabelText("Описание")).toHaveValue("Последнее описание");
  expect(request).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("heading", { name: "Новая категория" })).not.toBeInTheDocument();
});
