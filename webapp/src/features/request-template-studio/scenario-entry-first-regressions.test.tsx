import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioWizard } from "./scenario-wizard";
import type { ScenarioCatalog, ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-map-canvas",()=>({metadataNodeId:"studio:metadata",transitionId:(source:string,index:number)=>`${source}:${index}`,entranceEdgeId:(key:string|null)=>`entry:${key}`,entranceCardId:(key:string|null)=>`card:${key}`,ScenarioMapCanvas:({expandedId,inlineEditor,entranceEditor}:any)=><div aria-label="Визуальная карта сценария">{expandedId&&inlineEditor}{entranceEditor}</div>}));
vi.mock("../settings/api",()=>({fetchWebSettingsPayload:vi.fn(async()=>({queues:[],calendars:[]}))}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const initial:ScenarioDraftDefinition={schema_version:4,execution_semantics:3,scenario_key:"history",title:"Прежняя услуга",description:"Описание",service_code:"it",offering_full_code:"it.test",category_id:"a",process_binding:{request_template_key:"request"},entry_block_id:"q",entry_points:[{key:"main",title:"Вход",target_block_id:"q",category_id:"a"}],blocks:[{id:"q",kind:"instruction",title:"Первый шаг",content:{body:"Текст"},transitions:[]}],processing:{routes:{desk:{title:"Поддержка",queue_code:"desk"},network:{title:"Сеть",queue_code:"network"}},sla_profiles:{},defaults:{route:"desk",sla_profile:""}}};
const catalog={services:[{code:"it",public_title:"ИТ"}],categories:[{id:"a",service_code:"it",title:"Первая"},{id:"b",service_code:"it",title:"Вторая"}],offerings:[],scenarios:[]} as unknown as ScenarioCatalog;
function mount(initialDefinition=initial){
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{sla:[{code:"new_sla",title:"Новые сроки",is_active:true,published_at:"2026-11-09"}]}}}),{headers:{"content-type":"application/json"}})));
 function Harness(){const[d,setD]=useState(initialDefinition);return <><button onClick={()=>setD({...d,blocks:[{id:"replacement",kind:"submit_ticket",title:"Новая карта"}]})}>Внешняя замена карты</button><ScenarioWizard definition={d} detail={{scenario:{id:"s"},draft:{revision:1,definition:d}} as ScenarioDetail} catalog={catalog} disabled={false} dirty={false} onChange={setD}/><output data-testid="draft">{JSON.stringify(d)}</output></>;}
 render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Harness/></QueryClientProvider></MemoryRouter>);
}
const draft=()=>JSON.parse(screen.getByTestId("draft").textContent!) as ScenarioDraftDefinition;
it("keeps publication title, category and service policy edits across real map Undo and Redo",async()=>{
 mount();fireEvent.click(screen.getByRole("button",{name:"+ Инструкция"}));expect(draft().blocks).toHaveLength(2);
 fireEvent.click(screen.getByRole("button",{name:"Опубликовать"}));fireEvent.click(screen.getByRole("button",{name:"Настройки услуги"}));
 fireEvent.change(screen.getByLabelText("Название услуги"),{target:{value:"Новое название"}});
 fireEvent.click(screen.getByText("Раздел и категория",{selector:"summary"}));fireEvent.change(screen.getByLabelText("Категория (необязательно)"),{target:{value:"b"}});
 await screen.findByRole("option",{name:"Новые сроки"});fireEvent.change(screen.getByLabelText("Сроки обслуживания"),{target:{value:"new_sla"}});
 fireEvent.click(screen.getByRole("button",{name:"Вернуться к карте"}));
 for(const[name,count]of [["Отменить изменение",1],["Повторить изменение",2]] as const){
  expect(screen.getByRole("button",{name})).toBeEnabled();fireEvent.click(screen.getByRole("button",{name}));
  expect(draft().blocks).toHaveLength(count);expect(draft().title).toBe("Новое название");expect(draft().category_id).toBe("b");
  expect(draft().entry_points?.[0].category_id).toBe("b");expect(draft().process_binding.policy_refs?.sla).toBe("new_sla");expect(draft().processing?.defaults.route).toBe("desk");
 }
});
it("invalidates stale map history after external graph replacement",()=>{
 mount();fireEvent.click(screen.getByRole("button",{name:"+ Инструкция"}));expect(screen.getByRole("button",{name:"Отменить изменение"})).toBeEnabled();
 fireEvent.click(screen.getByRole("button",{name:"Внешняя замена карты"}));expect(screen.getByRole("button",{name:"Отменить изменение"})).toBeDisabled();expect(draft().blocks?.[0].id).toBe("replacement");
});
it("completes a library-created pending root from an optional keyboard section and preserves its key",()=>{
 mount();fireEvent.click(within(screen.getByRole("complementary",{name:"Библиотека блоков"})).getByRole("button",{name:"+ Вход из каталога"}));
 const pending=draft().editor_layout!.pending_entrances![0];const editor=screen.getByRole("region",{name:"Незавершённый вход из каталога"});
 const summary=within(editor).getByText("Подключение с клавиатуры",{selector:"summary"});expect(summary.closest("details")).not.toHaveAttribute("open");
 fireEvent.click(summary);fireEvent.change(within(editor).getByLabelText("Первый блок для сотрудника"),{target:{value:"q"}});
 expect(draft().entry_points?.at(-1)).toMatchObject({key:pending.key,target_block_id:"q"});expect(draft().editor_layout?.pending_entrances).toEqual([]);
});

it.each([true,false])("invalidates history safely after map SLA creation and publication editing (renamed=%s)",renamed=>{
 mount({...initial,blocks:[...initial.blocks!,{id:"legacy-sla",kind:"sla",title:"Сроки карты",transitions:[]}]});
 fireEvent.click(within(screen.getByRole("list",{name:"Блоки сценария"})).getByRole("button",{name:"Сроки карты"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 fireEvent.click(screen.getByRole("button",{name:"Создать профиль сроков для сотрудника"}));
 const key=Object.keys(draft().processing!.sla_profiles)[0];
 expect(draft().processing!.sla_profiles[key]).toEqual({title:"Новый профиль сроков для сотрудника",first_response_minutes:30,resolution_minutes:480,time_basis:"calendar"});
 fireEvent.click(screen.getByRole("button",{name:"Опубликовать"}));
 fireEvent.click(screen.getByRole("button",{name:"Настроить направления и профили карты"}));fireEvent.click(screen.getByRole("button",{name:"Профили сроков карты"}));
 if(renamed)fireEvent.change(within(screen.getByRole("region",{name:"Публикация сценария"})).getByLabelText("Название профиля"),{target:{value:"Переименованный профиль"}});
 fireEvent.change(screen.getByLabelText("Резервный профиль сроков для сотрудника"),{target:{value:key}});
 fireEvent.click(screen.getByRole("button",{name:"Вернуться к карте"}));
 for(const name of ["Отменить изменение","Повторить изменение"]){
  expect(screen.getByRole("button",{name})).toBeDisabled();fireEvent.click(screen.getByRole("button",{name}));
  const value=draft();expect(value.processing!.sla_profiles[key]).toEqual({title:renamed?"Переименованный профиль":"Новый профиль сроков для сотрудника",first_response_minutes:30,resolution_minutes:480,time_basis:"calendar"});
  expect(value.processing!.sla_profiles[value.processing!.defaults.sla_profile]).toBeDefined();
  const block=value.blocks!.find(block=>block.id==="legacy-sla")!;
  if(block.kind!=="sla")throw new Error("Expected legacy SLA block");
  expect(block.sla_profile).toBe(key);expect(value.processing!.sla_profiles[block.sla_profile!]).toBeDefined();
 }
});

it("cannot restore a map assignment after its profile is explicitly deleted in publication",()=>{
 const profile={title:"Старый профиль",first_response_minutes:30,resolution_minutes:480,time_basis:"calendar" as const};
 mount({...initial,processing:{...initial.processing!,sla_profiles:{old:profile}},blocks:[...initial.blocks!,{id:"legacy-sla",kind:"sla",title:"Сроки карты",sla_profile:"old",transitions:[]}]});
 fireEvent.click(within(screen.getByRole("list",{name:"Блоки сценария"})).getByRole("button",{name:"Сроки карты"}));fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 fireEvent.change(screen.getByLabelText("Профиль сроков для сотрудника"),{target:{value:""}});expect(screen.getByRole("button",{name:"Отменить изменение"})).toBeEnabled();
 fireEvent.click(screen.getByRole("button",{name:"Опубликовать"}));fireEvent.click(screen.getByRole("button",{name:"Настроить направления и профили карты"}));fireEvent.click(screen.getByRole("button",{name:"Профили сроков карты"}));
 fireEvent.click(screen.getByRole("button",{name:"Удалить профиль"}));fireEvent.click(screen.getByRole("button",{name:"Вернуться к карте"}));
 expect(screen.getByRole("button",{name:"Отменить изменение"})).toBeDisabled();expect(screen.getByRole("button",{name:"Повторить изменение"})).toBeDisabled();expect(draft().processing!.sla_profiles).toEqual({});
 const block=draft().blocks!.find(block=>block.id==="legacy-sla")!;expect(block.kind==="sla"&&block.sla_profile).toBeNull();
});
it("preserves the current complete 32-profile collection instead of restoring historical dictionaries",()=>{
 const profiles=Object.fromEntries(Array.from({length:32},(_,index)=>[`profile-${index}`,{title:`Профиль ${index}`,first_response_minutes:30,resolution_minutes:480,time_basis:"calendar" as const}]));
 mount({...initial,processing:{...initial.processing!,sla_profiles:profiles}});fireEvent.click(screen.getByRole("button",{name:"+ Инструкция"}));
 fireEvent.click(screen.getByRole("button",{name:"Опубликовать"}));fireEvent.click(screen.getByRole("button",{name:"Настроить направления и профили карты"}));fireEvent.click(screen.getByRole("button",{name:"Профили сроков карты"}));
 fireEvent.change(within(screen.getByRole("region",{name:"Публикация сценария"})).getByLabelText("Название профиля"),{target:{value:"Новые сроки"}});fireEvent.click(screen.getByRole("button",{name:"Вернуться к карте"}));
 expect(screen.getByRole("button",{name:"Отменить изменение"})).toBeDisabled();expect(Object.keys(draft().processing!.sla_profiles)).toHaveLength(32);
 expect(draft().processing!.sla_profiles["profile-0"]).toEqual({...profiles["profile-0"],title:"Новые сроки"});
});
