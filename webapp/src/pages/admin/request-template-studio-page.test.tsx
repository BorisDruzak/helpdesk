import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: "admin" } }) }));
const category = { id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", description: "", sort_order: 0, revision: 1, visibility: "internal", lifecycle_status: "draft" };
const catalog = { categories: [category], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [], total: 0, offset: 0, limit: 100 };
function response(data: unknown, status = 200) { return new Response(JSON.stringify({ status: status === 200 ? "success" : "error", data }), { status, headers: { "content-type": "application/json" } }); }
function mount(path = "/") { const router = createMemoryRouter([{ path: "/app/admin/request-template-studio/services/:offeringCode", element: <AdminRequestTemplateStudioPage /> }, { path: "*", element: <AdminRequestTemplateStudioPage /> }], { initialEntries: [path] }); render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>); return router; }

async function ready() { await screen.findByLabelText("Поиск услуг"); }
function mock() {
 const fetcher=vi.fn(async(url:unknown,init?:RequestInit)=>init?.method==="POST"&&String(url).endsWith("/services") ? response({scenario:{id:"s1",archived:false},draft:{revision:1,definition:{...JSON.parse(String(init.body)).definition,offering_full_code:"it.generated",process_binding:{request_template_key:"printer"}}}}) : response(catalog));
 vi.stubGlobal("fetch",fetcher);return fetcher;
}
async function start(kind="Простая заявка", _bound=false) {
 await ready();fireEvent.click(await screen.findByRole("button",{name:"Создать услугу"}));
 fireEvent.change(screen.getByLabelText("Название услуги"),{target:{value:"Выдать доступ"}});
 fireEvent.change(screen.getByLabelText("Раздел каталога"),{target:{value:"it"}});
 if(kind!=="Пустая карта")fireEvent.click(screen.getByRole("button",{name:"+ Вопрос"}));
 await screen.findByLabelText("Визуальная карта сценария");
}

afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});
describe("Guided Studio workflow",()=>{
 it("protects an unsaved import from unload and navigation and clears the guard after explicit discard",async()=>{
  const fetcher=mock();fetcher.mockImplementation(async(url:unknown)=>String(url).endsWith("/services/document-preview")?response(null,400):response(catalog));const router=mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Создать услугу из JSON/YAML"}));
  fireEvent.change(screen.getByLabelText("Документ новой услуги"),{target:{value:"title: Мой документ"}});
  fireEvent.click(screen.getByRole("button",{name:"Проверить документ"}));await screen.findByRole("alert");
  const event=new Event("beforeunload",{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);await act(()=>router.navigate("/other"));expect(router.state.location.pathname).toBe("/");
  expect(screen.getByLabelText("Документ новой услуги")).toHaveValue("title: Мой документ");
  confirm.mockReturnValue(true);fireEvent.click(screen.getByRole("button",{name:"Отмена"}));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();const clean=new Event("beforeunload",{cancelable:true});window.dispatchEvent(clean);expect(clean.defaultPrevented).toBe(false);
 });
 it("imports a new service from the catalog only after preview and explicit draft creation",async()=>{
  const definition={schema_version:3,scenario_key:"imported",title:"Импортированная печать",service_code:"it",offering_full_code:"it.imported",process_binding:{request_template_key:"imported"},blocks:[{id:"first",kind:"decision",title:"Первый шаг"}],entry_block_id:"first",entry_points:[]};
  const fetcher=vi.fn(async(url:unknown,init?:RequestInit)=>String(url).endsWith("/services/document-preview")?response({creation_key:JSON.parse(String(init?.body)).creation_key,source_hash:"checked",definition,issues:[]}):String(url).endsWith("/services/from-document")?response({scenario:{id:"imported",archived:false},draft:{revision:1,definition}}):response(catalog));
  vi.stubGlobal("fetch",fetcher);mount("/?service=it");await ready();
  fireEvent.click(screen.getByRole("button",{name:"Создать услугу из JSON/YAML"}));
  expect(screen.getByRole("dialog",{name:"Создать услугу из JSON/YAML"})).toBeVisible();
  fireEvent.change(screen.getByLabelText("Документ новой услуги"),{target:{value:"schema_version: 3\ntitle: Импортированная печать"}});
  fireEvent.click(screen.getByRole("button",{name:"Проверить документ"}));
  const create=await screen.findByRole("button",{name:"Создать услугу-черновик"});
  expect(fetcher.mock.calls.filter(([url,init])=>init?.method==="POST").map(([url])=>url)).toEqual(["/api/web/admin/request-studio/services/document-preview"]);
  fireEvent.click(create);await screen.findByLabelText("Визуальная карта сценария");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();expect(screen.queryByRole("button",{name:"Создать услугу из JSON/YAML"})).not.toBeInTheDocument();
  const clean=new Event("beforeunload",{cancelable:true});window.dispatchEvent(clean);expect(clean.defaultPrevented).toBe(false);
  expect(fetcher.mock.calls.some(([url])=>String(url).includes("publish"))).toBe(false);
 });
 it("starts in the catalog with a compact new-map action",async()=>{mock();mount();await ready();expect(screen.getByRole("button",{name:"Создать услугу"})).toBeVisible();expect(screen.queryByRole("button",{name:"Новая карта"})).not.toBeInTheDocument();expect(screen.queryByLabelText("Визуальная карта сценария")).not.toBeInTheDocument();});
 it("updates category filtering when URL changes",async()=>{const fetcher=mock();const router=mount("/?service=it");await ready();expect(fetcher.mock.calls.some(([url])=>String(url).includes("service_code=it"))).toBe(true);await act(()=>router.navigate("/?service=mail"));await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>String(url).includes("service_code=mail"))).toBe(true));});
 it("does not bind from incomplete paginated deep-link context",async()=>{const fetcher=mock();fetcher.mockResolvedValue(response({...catalog,total:200}));mount("/?offering=it.printer");expect(await screen.findByText(/Каталог содержит несколько страниц/)).toBeVisible();expect(screen.queryByRole("dialog")).not.toBeInTheDocument();});
 it("keeps legacy services until conversion, without offering independent form creation",async()=>{const fetcher=mock();fetcher.mockResolvedValue(response({...catalog,legacy_offerings:catalog.offerings,total:1}));mount();fireEvent.click(await screen.findByRole("button",{name:"Настроить услугу Принтер"}));expect(screen.getByRole("button",{name:"Перенести в сценарий"})).toBeVisible();expect(screen.queryByLabelText("Шаблон обработки")).not.toBeInTheDocument();});
 it("blocks navigation and unload while a new map is dirty",async()=>{mock();const router=mount();await start();const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);await act(()=>router.navigate("/other"));expect(confirm).toHaveBeenCalled();expect(router.state.location.pathname).toBe("/");const event=new Event("beforeunload",{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);confirm.mockReturnValue(true);await act(()=>router.navigate("/other"));expect(router.state.location.pathname).toBe("/other");});
 it("offers an explicit conversion error for unavailable linked legacy forms",async()=>{mock();mount("/?offering=it.printer&template=printer");expect(await screen.findByText(/Не удалось перенести форму/)).toBeVisible();expect(screen.queryByLabelText("Тип создаваемого обращения")).not.toBeInTheDocument();});
 it("shows loading while catalog is pending",()=>{vi.stubGlobal("fetch",()=>new Promise(()=>{}));mount();expect(screen.getByText("Загрузка Студии")).toBeVisible();});
 it("creates an editable local draft even when no offering exists",async()=>{const fetcher=mock();fetcher.mockResolvedValue(response({...catalog,offerings:[]}));mount();await start();expect(screen.getByRole("button",{name:"Сохранить черновик"})).toBeEnabled();expect(screen.getByLabelText("Что спросить?")).toBeVisible();expect(fetcher.mock.calls.every(([,init])=>!["POST","PUT","DELETE"].includes(init?.method ?? "GET"))).toBe(true);});
 it("retries a failed catalog",async()=>{const fetcher=mock();fetcher.mockResolvedValue(response({...catalog,offerings:[]})).mockResolvedValueOnce(response(null,500));mount();fireEvent.click(await screen.findByRole("button",{name:/Повторить/}));expect(await screen.findByText("Услуги не найдены")).toBeVisible();});
 it("searches and filters through the server",async()=>{const fetcher=mock();mount();fireEvent.change(await screen.findByLabelText("Поиск услуг"),{target:{value:"принтер"}});await waitFor(()=>expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("q=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80"));fireEvent.change(screen.getByLabelText("Статус"),{target:{value:"draft"}});await waitFor(()=>expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("status=draft"));});
 it("filters categories on the server",async()=>{const fetcher=mock();mount();fireEvent.click(await screen.findByRole("button",{name:"Оборудование"}));await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>String(url).includes("category_id=c1"))).toBe(true));});
 it("saves a v3 map through automatic internal binding without publication",async()=>{const fetcher=mock();mount();await start("Простая заявка",true);fireEvent.click(screen.getByRole("button",{name:"Сохранить черновик"}));expect(await screen.findByText("Черновик сохранён. Ревизия 1.")).toBeVisible();const body=JSON.parse(String(fetcher.mock.calls.find(([,init])=>init?.method==="POST")?.[1]?.body));expect(body.definition.blocks.map((b:{kind:string})=>b.kind)).toEqual(["form_page"]);expect(body.definition.offering_full_code).toBe("");expect(body.definition.schema_version).toBe(3);expect(fetcher.mock.calls.some(([url])=>String(url).includes("/publish"))).toBe(false);});
 it("keeps three sections and contextual testing",async()=>{mock();mount();await start();expect(screen.getByRole("navigation",{name:"Разделы Студии"})).toBeVisible();expect(screen.getByRole("button",{name:"Согласования"})).toBeVisible();fireEvent.click(screen.getByRole("button",{name:"Тестировать"}));expect(screen.getByText("Сначала сохраните сценарий.")).toBeVisible();});
 it("requires an explicit decision before replacing unsaved edits",async()=>{mock();mount();await start();fireEvent.change(screen.getByLabelText("Что спросить?"),{target:{value:"Мой вопрос"}});fireEvent.click(screen.getByRole("button",{name:"Создать услугу"}));expect(screen.getByText("Переключить карту без сохранения локальных изменений?" )).toBeVisible();fireEvent.click(screen.getByRole("button",{name:"Отмена"}));expect(screen.getByLabelText("Что спросить?")).toHaveValue("Мой вопрос");});
 it("selects the service category once on Start",async()=>{const fetcher=mock();mount();await start("Пустая карта");fireEvent.change(screen.getByLabelText("Категория (необязательно)"),{target:{value:"c1"}});expect(screen.getByLabelText("Категория (необязательно)")).toHaveValue("c1");expect(fetcher.mock.calls.some(([url,init])=>init?.method==="POST"&&String(url).includes("categories"))).toBe(false);});
});
