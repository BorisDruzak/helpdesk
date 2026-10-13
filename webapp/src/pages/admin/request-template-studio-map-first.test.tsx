import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: "admin" } }) }));
const offering = { full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" };
const catalog = { categories: [], services: [{ code: "it", public_title: "ИТ" }], offerings: [offering], entries: [{ offering, scenarios: [], active_mode: "form", category_ids: [] }], scenarios: [], total: 1, offset: 0, limit: 100 };
function response(data:unknown){return new Response(JSON.stringify({status:"success",data}),{headers:{"content-type":"application/json"}});}
function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><RouterProvider router={createMemoryRouter([{path:"*",element:<AdminRequestTemplateStudioPage/>}])}/></QueryClientProvider>);}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });

it("creates a local map from the service creation choice without server writes",async()=>{
 const fetcher=vi.fn(async(_url:unknown,_init?:RequestInit)=>response(catalog));vi.stubGlobal("fetch",fetcher);mount();
 fireEvent.click(await screen.findByRole("button",{name:"Создать услугу"}));fireEvent.change(screen.getByRole("combobox",{name:"Способ помощи"}),{target:{value:"map"}});fireEvent.click(screen.getByRole("button",{name:"Создать карту"}));
 expect(await screen.findByRole("dialog",{name:"С чего начнём?"})).toBeVisible();expect(screen.queryByLabelText("Визуальная карта сценария")).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Название карты"),{target:{value:"Выдать доступ"}});fireEvent.change(screen.getByLabelText("Раздел каталога"),{target:{value:"service:it"}});fireEvent.click(screen.getByRole("button",{name:"Создать карту →"}));
 expect(await screen.findByRole("heading",{name:"Библиотека блоков"})).toBeVisible();expect(fetcher.mock.calls.every(([,init])=>!["POST","PUT","DELETE"].includes(init?.method??"GET"))).toBe(true);
});
it("renders only offering cards supplied by the catalog projection",async()=>{
 const vpn={...offering,full_code:"it.vpn",public_title:"VPN"};vi.stubGlobal("fetch",vi.fn(async()=>response({...catalog,offerings:[offering,vpn]})));mount();
 expect(await screen.findByRole("button",{name:"Настроить услугу Принтер"})).toBeVisible();expect(screen.queryByRole("button",{name:"Настроить услугу VPN"})).not.toBeInTheDocument();
});
it.each([0,2])("discards old map edits before choosing a service with %i maps",async(mapCount)=>{
 const other={...offering,full_code:"it.vpn",public_title:"VPN",request_template_key:"vpn"};
 const definition={scenario_key:"existing",title:"Карта принтера",service_code:"it",offering_full_code:offering.full_code,blocks:[],process_binding:{request_template_key:"printer"}};const item={...definition,id:"s1",archived:false};const maps=Array.from({length:mapCount},(_,index)=>({...item,id:`vpn-${index}`,title:`VPN ${index}`,offering_full_code:other.full_code}));
 const data={...catalog,offerings:[offering,other],scenarios:[item,...maps],entries:[{offering,scenarios:[item],active_mode:"form",category_ids:[]},{offering:other,scenarios:maps,active_mode:"form",category_ids:[]}]};
 const fetcher=vi.fn(async(url:unknown,_init?:RequestInit)=>response(String(url).includes("/scenarios/s1")?{scenario:item,draft:{revision:3,definition}}:data));vi.stubGlobal("fetch",fetcher);mount();
 fireEvent.click(await screen.findByRole("button",{name:"Настроить услугу Принтер"}));fireEvent.click(screen.getByRole("button",{name:"Открыть карту сценария"}));await waitFor(()=>expect(screen.getByLabelText("Название карты")).toHaveValue("Карта принтера"));
 vi.useFakeTimers();fireEvent.change(screen.getByLabelText("Название карты"),{target:{value:"Отброшенная правка"}});fireEvent.click(screen.getByRole("button",{name:"Каталог"}));
 await act(async()=>{await vi.advanceTimersByTimeAsync(1500);});expect(fetcher.mock.calls.some(([,init])=>init?.method==="PUT")).toBe(false);
 fireEvent.click(screen.getByRole("button",{name:"Уйти без сохранения"}));fireEvent.click(screen.getByRole("button",{name:"Настроить услугу VPN"}));
 if(mapCount===0){expect(screen.queryByRole("button",{name:/Открыть карту сценария/})).not.toBeInTheDocument();fireEvent.click(screen.getByRole("tab",{name:"Помощь сотруднику"}));fireEvent.click(screen.getByRole("button",{name:"Создать карту"}));expect(screen.getByLabelText("Название карты")).toHaveValue("VPN");}
 else{expect(screen.getByRole("button",{name:"Открыть карту сценария: VPN 0"})).toBeVisible();expect(screen.getByRole("button",{name:"Открыть карту сценария: VPN 1"})).toBeVisible();expect(screen.queryByLabelText("Название карты")).not.toBeInTheDocument();}
 await act(async()=>{await vi.advanceTimersByTimeAsync(1500);});expect(fetcher.mock.calls.some(([,init])=>init?.method==="PUT")).toBe(false);
});
it("keeps archive and copy absent while a map selected from the inspector is loading",async()=>{
 const definition={scenario_key:"existing",title:"Карта принтера",service_code:"it",offering_full_code:offering.full_code,blocks:[],process_binding:{request_template_key:"printer"}};const item={...definition,id:"s1",archived:false};
 let resolve!:(value:Response)=>void;const fetcher=vi.fn(async(url:unknown,_init?:RequestInit)=>String(url).includes("/scenarios/s1")?new Promise<Response>(done=>{resolve=done;}):response({...catalog,scenarios:[item],entries:[{offering,scenarios:[item],active_mode:"form",category_ids:[]}]}));vi.stubGlobal("fetch",fetcher);mount();
 fireEvent.click(await screen.findByRole("button",{name:"Настроить услугу Принтер"}));fireEvent.click(screen.getByRole("button",{name:"Открыть карту сценария"}));expect(screen.queryByRole("button",{name:"Архивировать сценарий"})).not.toBeInTheDocument();expect(screen.queryByRole("button",{name:"Создать копию"})).not.toBeInTheDocument();
 await act(async()=>{resolve(response({scenario:item,draft:{revision:3,definition}}));});expect(await screen.findByRole("button",{name:"Архивировать сценарий"})).toBeEnabled();expect(fetcher.mock.calls.some(([url])=>String(url).endsWith("/archive"))).toBe(false);
});
