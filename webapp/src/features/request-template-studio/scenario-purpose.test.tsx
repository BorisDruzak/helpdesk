import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPurpose } from "./scenario-purpose";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

afterEach(() => vi.unstubAllGlobals());
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
  await waitFor(() => expect(screen.getByLabelText("Категория")).toHaveValue("printing"));
  expect(screen.getByLabelText("Название сценария")).toHaveValue("Последнее название");
  expect(screen.getByLabelText("Описание")).toHaveValue("Последнее описание");
  expect(request).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("heading", { name: "Новая категория" })).not.toBeInTheDocument();
});
