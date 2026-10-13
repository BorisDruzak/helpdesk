import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import type { ScenarioCatalog } from "./scenario-api";
afterEach(()=>vi.unstubAllGlobals());

it("lets a read-only user open an archived map without edit permission",()=>{
 const offering={full_code:"it.a",service_code:"it",public_title:"Печать"},map={id:"s",title:"Архив печати",offering_full_code:"it.a",archived:true};
 const data={services:[{code:"it",public_title:"ИТ"}],categories:[],offerings:[offering],scenarios:[map],entries:[{offering,scenarios:[map],active_mode:"form",category_ids:[]}],total:1,offset:0,limit:100} as unknown as ScenarioCatalog;
 const onOpen=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit={false} onCategory={vi.fn()} onQuery={vi.fn()} onStatus={vi.fn()} onOpen={onOpen} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()}/></MemoryRouter></QueryClientProvider>);
 fireEvent.click(screen.getByRole("button",{name:"Настроить услугу Печать"}));
 expect(screen.getByLabelText("Название услуги")).toBeDisabled();
 expect(screen.queryByRole("button",{name:"Открыть карту сценария"})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole("tab",{name:"Помощь сотруднику"}));fireEvent.click(screen.getByText("Архив карт услуги"));
 expect(screen.getByRole("button",{name:"Открыть архивную карту"})).toBeEnabled();fireEvent.click(screen.getByRole("button",{name:"Открыть архивную карту"}));expect(onOpen).toHaveBeenCalledWith(map);
});

it("keeps services together and opens settings in place, map action directly in the inspector", () => {
  const offering = { code: "vpn", full_code: "network.vpn", service_code: "network", public_title: "VPN не подключается", lifecycle_status: "published", visibility: "public", request_template_key: "network" };
  const map = { id: "s", title: "Диагностика VPN", offering_full_code: offering.full_code, status: "draft", archived: false, issues: [] };
  const data = { categories: [], services: [{ code: "network", public_title: "Сеть" }], offerings: [offering], scenarios: [map], entries: [{ offering, scenarios: [map], active_mode: "form", requester_available: true, category_ids: [] }], total: 1, offset: 0, limit: 100 } as unknown as ScenarioCatalog;
  const onOpen=vi.fn();
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit onCategory={vi.fn()} onQuery={vi.fn()} onStatus={vi.fn()} onOpen={onOpen} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole("region", { name: "Карты сценариев" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Настроить услугу VPN не подключается" }));
  expect(screen.getByRole("complementary", { name: "Настройки услуги" })).toBeVisible();
  expect(screen.getByLabelText("Название услуги")).toHaveValue("VPN не подключается");
  expect(screen.getByRole("button",{name:"Услуга VPN не подключается · Обычная форма"})).toBeVisible();
  expect(screen.queryByRole("tab", { name: "Карты сценариев" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Открыть карту сценария" }));
  expect(onOpen).toHaveBeenCalledWith(map,undefined);
});

it("keeps an unfiltered hierarchy and opens a nested form from a filtered list",async()=>{
 const first={full_code:"network.a",service_code:"network",public_title:"Первая"},second={full_code:"network.b",service_code:"network",public_title:"Вторая",metadata:{studio_catalog:{category_id:"c"}}};
 const full={services:[{code:"network",public_title:"Сеть"}],categories:[{id:"c",parent_id:null,service_code:"network",title:"VPN"}],offerings:[first,second],scenarios:[],entries:[first,second].map(offering=>({offering,scenarios:[],active_mode:"form",category_ids:[]})),total:2,offset:0,limit:100} as unknown as ScenarioCatalog;
 const data={...full,entries:full.entries!.slice(0,1),total:1};
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:full}),{headers:{"content-type":"application/json"}})));
 const onQuery=vi.fn(),onStatus=vi.fn(),onCategory=vi.fn();
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioCatalogExplorer data={data} query="Первая" status="all" category={null} canEdit onCategory={onCategory} onQuery={onQuery} onStatus={onStatus} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()}/></MemoryRouter></QueryClientProvider>);
 const leaf=await screen.findByRole("button",{name:"Услуга Вторая · Обычная форма"});
 expect(screen.queryByRole("button",{name:"Настроить услугу Вторая"})).not.toBeInTheDocument();
 fireEvent.click(leaf);expect(screen.getByLabelText("Название услуги")).toHaveValue("Вторая");
 expect(onQuery).toHaveBeenCalledWith("");expect(onStatus).toHaveBeenCalledWith("all");expect(onCategory).toHaveBeenCalledWith("c");
 fireEvent.click(screen.getByRole("button",{name:"Свернуть категорию VPN"}));expect(screen.queryByRole("button",{name:"Услуга Вторая · Обычная форма"})).not.toBeInTheDocument();
});
