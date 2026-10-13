import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import { ScenarioEntryInspector } from "./scenario-entry-inspector";
import { addMapBlock, connectStart, mapPalette } from "./scenario-map-model";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const data = { services: [{code:"network",public_title:"Сеть",lifecycle_status:"published",visibility:"public"}], categories:[],offerings:[],scenarios:[],entries:[],total:0,offset:0,limit:100 } as unknown as ScenarioCatalog;
const definition: ScenarioDraftDefinition = {schema_version:1,scenario_key:"new",service_code:"network",offering_full_code:"network.vpn",title:"VPN",category_id:"category",blocks:[],entry_points:[],process_binding:{request_template_key:"network"}};

it("opens the map directly from create service without a help-mode selector",()=>{
 const create=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category="service:network" canEdit onQuery={vi.fn()} onStatus={vi.fn()} onCategory={vi.fn()} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} onNewMap={create}/></MemoryRouter></QueryClientProvider>);
 fireEvent.click(screen.getByRole("button",{name:"Создать услугу"}));
 expect(create).toHaveBeenCalledOnce();
 expect(screen.queryByLabelText("Способ помощи")).not.toBeInTheDocument();
});

it("has five useful palette kinds and preserves hidden historical kinds",()=>{
 expect(mapPalette.map(item=>item.kind)).toEqual(["form_page","instruction","decision","resolution_check","submit_ticket"]);
});

it("creates a catalog entrance only on a Start connection and inherits category",()=>{
 const next=addMapBlock({...definition,schema_version:2},"form_page",{x:0,y:0});
 expect(next.entry_points).toHaveLength(0);
 const linked=connectStart(next,next.blocks![0].id);
 expect(linked.entry_points?.[0].category_id).toBe("category");
 expect(linked.blocks![0].transitions).toEqual([]);
});

it("shows entrance naming without duplicate target and category controls",()=>{
 const draft=addMapBlock({...definition,schema_version:2},"form_page",{x:0,y:0});
 const next=connectStart(draft,draft.blocks![0].id);
 render(<ScenarioEntryInspector definition={next} blockId={next.blocks![0].id} catalog={data} disabled={false} onChange={vi.fn()}/>);
 expect(screen.getByLabelText("Название пункта")).toBeVisible();
 expect(screen.queryByLabelText("Начальный блок")).not.toBeInTheDocument();
 expect(screen.queryByLabelText("Категория пункта")).not.toBeInTheDocument();
});
