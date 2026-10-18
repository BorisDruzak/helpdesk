import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioServiceImportDialog } from "./scenario-service-import-dialog";
import type { ScenarioCatalog } from "./scenario-api";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const category = "10000000-0000-0000-0000-000000000001";
const catalog = { services: [{ code: "it", public_title: "ИТ" }, { code: "access", public_title: "Доступ" }], categories: [{ id: category, service_code: "it", title: "Принтеры" }], offerings: [], scenarios: [], total: 0, offset: 0, limit: 100 } as unknown as ScenarioCatalog;
const yaml = "schema_version: 3\ntitle: Проблемы с печатью\nblocks: []\n";
const definition = { schema_version: 3, title: "Проблемы с печатью", scenario_key: "generated", service_code: "it", offering_full_code: "it.generated", process_binding: { request_template_key: "generated" }, blocks: [{ id: "q", kind: "decision", title: "Выбрать помощь" }], entry_points: [{ key: "main", title: "Не печатает", target_block_id: "q" }] };
const response = (data: unknown, status = 200, error_code?: string, issues?: unknown[]) => new Response(JSON.stringify({ status: status === 200 ? "success" : "error", data, error_code, issues }), { status, headers: { "content-type": "application/json" } });
function setup(issues: unknown[] = []) {
 const onCreated = vi.fn();
 const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
  const body = JSON.parse(String(init?.body));
  return response(url.endsWith("/document-preview") ? { creation_key: body.creation_key, source_hash: "validated", definition, issues } : { scenario: { id: "created" }, draft: { revision: 1, definition } });
 });
 vi.stubGlobal("fetch", fetcher);
 render(<ScenarioServiceImportDialog catalog={catalog} initialCategory={category} onClose={vi.fn()} onCreated={onCreated} />);
 return { fetcher, onCreated };
}
async function preview() {
 fireEvent.change(screen.getByLabelText("Документ новой услуги"), { target: { value: yaml } });
 fireEvent.click(screen.getByRole("button", { name: "Проверить документ" }));
 await screen.findByText("Проблемы с печатью", { selector: "h3" });
}
it("previews an unbound YAML without creating and explicitly creates only a draft in the selected category", async () => {
 const { fetcher, onCreated } = setup();
 expect(screen.getByLabelText("Раздел каталога")).toHaveValue("it");
 expect(screen.getByLabelText("Категория новой услуги")).toHaveValue(category);
 expect(screen.queryByRole("button", { name: "Создать услугу-черновик" })).not.toBeInTheDocument();
 await preview();
 expect(fetcher).toHaveBeenCalledTimes(1);
 expect(fetcher.mock.calls[0][0]).toMatch(/\/services\/document-preview$/);
 expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ content: yaml, format: "yaml", service_code: "it", category_id: category });
 expect(screen.getByText("Шагов: 1. Входов в каталог: 1.")).toBeVisible();
 fireEvent.click(screen.getByRole("button", { name: "Создать услугу-черновик" }));
 await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
 expect(fetcher.mock.calls[1][0]).toMatch(/\/services\/from-document$/);
 expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toMatchObject({ content: yaml, source_hash: "validated", creation_key: JSON.parse(String(fetcher.mock.calls[0][1]?.body)).creation_key });
 expect(fetcher.mock.calls.some(([url]) => url.includes("publish"))).toBe(false);
});
it("renders semantic resource error paths and cannot create a service with an invalid queue", async () => {
 const { fetcher, onCreated } = setup([{ code: "processing_queue_unavailable", path: "processing.routes.printer.queue_code", message: "Очередь недоступна" }]);
 await preview();
 expect(screen.getByText("processing.routes.printer.queue_code")).toBeVisible(); expect(screen.getByText(/Очередь недоступна/)).toBeVisible();
 expect(screen.queryByRole("button", { name: "Создать услугу-черновик" })).not.toBeInTheDocument();
 expect(fetcher).toHaveBeenCalledTimes(1); expect(onCreated).not.toHaveBeenCalled(); expect(screen.getByLabelText("Документ новой услуги")).toHaveValue(yaml);
});
it.each(["document", "format", "section", "category"])("invalidates the checked preview when %s changes", async field => {
 setup(); await preview();
 if (field === "document") fireEvent.change(screen.getByLabelText("Документ новой услуги"), { target: { value: yaml + "description: Изменено\n" } });
 if (field === "format") fireEvent.change(screen.getByLabelText("Формат документа"), { target: { value: "json" } });
 if (field === "section") fireEvent.change(screen.getByLabelText("Раздел каталога"), { target: { value: "access" } });
 if (field === "category") fireEvent.change(screen.getByLabelText("Категория новой услуги"), { target: { value: "" } });
 expect(screen.queryByRole("button", { name: "Создать услугу-черновик" })).not.toBeInTheDocument();
});
it("preserves the source and creation key when retrying an uncertain creation", async () => {
 const { fetcher, onCreated } = setup(); await preview();
 fetcher.mockResolvedValueOnce(response(null, 503));
 fireEvent.click(screen.getByRole("button", { name: "Создать услугу-черновик" }));
 await screen.findByRole("alert");
 expect(screen.getByLabelText("Документ новой услуги")).toHaveValue(yaml);
 fireEvent.click(screen.getByRole("button", { name: "Создать услугу-черновик" }));
 await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
 expect(fetcher.mock.calls[1][1]?.body).toBe(fetcher.mock.calls[2][1]?.body);
});
it.each(["SERVICE_PROCESSING_DEFAULT_REQUIRED", "IMPORT_PREVIEW_CHANGED"])("explains %s and requires revalidation", async code => {
 const { fetcher, onCreated } = setup(); await preview();
 fetcher.mockResolvedValueOnce(response(null, 409, code, [{ code: "processing_queue_unavailable", path: "processing.routes.printer.queue_code", message: "Очередь недоступна" }]));
 fireEvent.click(screen.getByRole("button", { name: "Создать услугу-черновик" }));
 expect(await screen.findByRole("alert")).toHaveTextContent(code === "IMPORT_PREVIEW_CHANGED" ? "Проверка устарела" : "Обработка раздела");
 expect(screen.getByText("processing.routes.printer.queue_code")).toBeVisible();
 expect(screen.queryByRole("button", { name: "Создать услугу-черновик" })).not.toBeInTheDocument(); expect(onCreated).not.toHaveBeenCalled();
});
it("rejects a file over 1 MiB without changing the pasted source or sending a request", () => {
 const { fetcher } = setup();
 fireEvent.change(screen.getByLabelText("Документ новой услуги"), { target: { value: yaml } });
 const file = new File([new Uint8Array(1048577)], "printer.yaml");
 fireEvent.change(screen.getByLabelText("Загрузить JSON/YAML"), { target: { files: [file] } });
 expect(screen.getByRole("alert")).toHaveTextContent("1 МиБ"); expect(screen.getByLabelText("Документ новой услуги")).toHaveValue(yaml); expect(fetcher).not.toHaveBeenCalled();
});
it("prefers a public published section when no destination is selected", () => {
 render(<ScenarioServiceImportDialog catalog={{ ...catalog, services: [{ code: "draft", public_title: "Черновой раздел", lifecycle_status: "draft", visibility: "internal" }, { code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" }] as ScenarioCatalog["services"] }} onClose={vi.fn()} onCreated={vi.fn()} />);
 expect(screen.getByLabelText("Раздел каталога")).toHaveValue("it");
});
it("keeps malformed input and shows safe structural validation errors without creation", async () => {
 const { fetcher, onCreated } = setup();
 fetcher.mockResolvedValueOnce(response(null, 400, "SCENARIO_INVALID", [{ code: "invalid_document", path: "schema_version", message: "Проверьте версию документа" }]));
 fireEvent.change(screen.getByLabelText("Документ новой услуги"), { target: { value: "invalid: [" } });
 fireEvent.click(screen.getByRole("button", { name: "Проверить документ" }));
 await screen.findByRole("alert"); expect(screen.getByText("schema_version")).toBeVisible(); expect(screen.getByText(/Проверьте версию документа/)).toBeVisible();
 expect(screen.getByLabelText("Документ новой услуги")).toHaveValue("invalid: ["); expect(screen.queryByRole("button", { name: "Создать услугу-черновик" })).not.toBeInTheDocument();
 expect(fetcher).toHaveBeenCalledTimes(1); expect(onCreated).not.toHaveBeenCalled();
});
it("keeps pasted input and preview when close or Escape discard confirmation is refused", async () => {
 const onClose = vi.fn(), onDirty = vi.fn(), confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
 vi.stubGlobal("fetch",vi.fn(async(_url:string,init?:RequestInit)=>response({creation_key:JSON.parse(String(init?.body)).creation_key,source_hash:"checked",definition,issues:[]})));
 render(<ScenarioServiceImportDialog catalog={catalog} onClose={onClose} onCreated={vi.fn()} onDirty={onDirty} />);
 fireEvent.change(screen.getByLabelText("Документ новой услуги"), { target: { value: yaml } });
 fireEvent.click(screen.getByRole("button",{name:"Проверить документ"}));await screen.findByRole("button",{name:"Создать услугу-черновик"});
 fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
 expect(confirm).toHaveBeenCalled(); expect(onClose).not.toHaveBeenCalled(); expect(onDirty).toHaveBeenLastCalledWith(true);
 fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
 expect(onClose).not.toHaveBeenCalled(); expect(screen.getByLabelText("Документ новой услуги")).toHaveValue(yaml);
 expect(screen.getByRole("button",{name:"Создать услугу-черновик"})).toBeEnabled();
 confirm.mockReturnValue(true); fireEvent.click(screen.getByRole("button", { name: "Отмена" })); expect(onClose).toHaveBeenCalledTimes(1);
});
it("closes an empty import without a discard warning", () => {
 const onClose = vi.fn(), confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
 render(<ScenarioServiceImportDialog catalog={catalog} onClose={onClose} onCreated={vi.fn()} />);
 fireEvent.click(screen.getByRole("button", { name: "Отмена" })); expect(onClose).toHaveBeenCalledTimes(1); expect(confirm).not.toHaveBeenCalled();
});
