import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioOfferingForm } from "./scenario-offering-form";
import type { ScenarioCatalog } from "./scenario-api";

const catalog = { services: [{ code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" }, { code: "hidden", public_title: "Закрытый раздел", lifecycle_status: "published", visibility: "internal" }], offerings: [] } as unknown as ScenarioCatalog;
function response(data: unknown) { return new Response(JSON.stringify(data), { headers: { "content-type": "application/json" } }); }
function mount(done = vi.fn()) { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><ScenarioOfferingForm standalone catalog={catalog} initialServiceCode="" onDirty={vi.fn()} onCancel={vi.fn()} onDone={done} /></QueryClientProvider>); return done; }
afterEach(() => vi.unstubAllGlobals());

it("preserves edits when loading templates fails and retries without creating anything", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(response({ status: "success", data: { request_templates: [] } }));
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.change(screen.getByLabelText("Название услуги"), { target: { value: "Моя услуга" } });
  fireEvent.click(await screen.findByRole("button", { name: "Повторить загрузку шаблонов" }));
  await screen.findByText(/Нет опубликованных шаблонов обработки/);
  expect(screen.getByLabelText("Название услуги")).toHaveValue("Моя услуга");
  expect(screen.getByRole("button", { name: "Создать черновик услуги" })).toBeDisabled();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("creates only a service draft with canonical template binding, without creating a scenario", async () => {
  const saved: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    if (String(url).endsWith("/helpdesk-model/policies")) return response({ status: "success", data: { request_templates: [{ template_code: "printer", public_title: "Проблема печати", ticket_type: "incident", is_active: true, published_at: "2026-01-01" }, { template_code: "hidden", public_title: "Неопубликованная форма", is_active: true }] } });
    expect(url).toBe("/api/web/admin/service-catalog/offerings/save-draft");
    const body = JSON.parse(String(init?.body)); saved.push(body);
    return response({ status: "ok", offering: { ...body, full_code: `it.${body.code}` } });
  }));
  const done = mount();
  await screen.findByRole("option", { name: "Проблема печати" });
  expect(screen.queryByRole("option", { name: "Закрытый раздел" })).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Неопубликованная форма" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Название услуги"), { target: { value: "Не печатает" } });
  fireEvent.change(screen.getByLabelText("Шаблон обработки"), { target: { value: "printer" } });
  fireEvent.change(screen.getByLabelText("Тип запроса"), { target: { value: "software_install" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать черновик услуги" }));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(saved).toHaveLength(1);
  expect(saved[0]).toMatchObject({ service_code: "it", lifecycle_status: "draft", request_type: "service_request", metadata: { studio_profile: "software_install" }, request_template_key: "printer", ticket_type_code: "incident" });
});
