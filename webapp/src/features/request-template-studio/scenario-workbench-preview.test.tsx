import { fireEvent,render,screen,waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach,expect,it,vi } from "vitest";
import { ScenarioMapWorkbench } from "./scenario-map-workbench";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-map-canvas",()=>({metadataNodeId:"studio:metadata",transitionId:(source:string,index:number)=>`${source}:${index}`,entranceEdgeId:(key:string|null)=>`entry:${key}`,ScenarioMapCanvas:({onSelect,onEntrance}:{onSelect:(id:string)=>void;onEntrance:(key:string,target:string)=>void})=><div><button onClick={()=>onSelect("q")}>Выбрать вопрос</button><button onClick={()=>onSelect("branch")}>Выбрать второе условие</button><button onClick={()=>onEntrance("named","q")}>Выбрать связь входа</button></div>}));
const definition:ScenarioDraftDefinition={scenario_key:"s",title:"Карта",service_code:"it",offering_full_code:"it.p",process_binding:{request_template_key:"p"},entry_block_id:"q",entry_points:[{key:"named",title:"Вход",target_block_id:"q"}],blocks:[{id:"q",kind:"instruction",title:"Проверка",content:{body:"Шаг"},transitions:[]},{id:"done",kind:"finish",title:"Готово"}]};
const catalog={services:[],offerings:[],categories:[],scenarios:[],total:0,offset:0,limit:100};
afterEach(()=>vi.unstubAllGlobals());
it("builds independent yes and no steps from an empty condition and undoes each addition atomically", () => {
 const initial:ScenarioDraftDefinition={...definition,schema_version:3,blocks:[
  {id:"q",kind:"form_page",title:"Вопрос",fields:[{key:"working",label:"Работает?",type:"checkbox"}],transitions:[{to:"branch"}]},
  {id:"branch",kind:"decision",title:"Условие",transitions:[]},
 ]};
 const change=vi.fn();
 function Harness(){const [draft,setDraft]=useState(initial);return <MemoryRouter><ScenarioMapWorkbench definition={draft} catalog={catalog} existing disabled={false} onChange={next=>{change(next);setDraft(next);}}/></MemoryRouter>;}
 render(<Harness/>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать второе условие"}));
 fireEvent.click(screen.getByRole("button",{name:"Добавить шаг для «Да»"}));
 fireEvent.click(screen.getByRole("button",{name:/^Показать инструкцию/}));
 const yes=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;
 expect(yes.blocks).toHaveLength(3);
 const yesEdge=yes.blocks![1].transitions![0];
 expect(yesEdge.when).toEqual({source:"answer",field:"working",op:"eq",value:true});
 fireEvent.click(screen.getByRole("button",{name:"Выбрать второе условие"}));
 fireEvent.click(screen.getByRole("button",{name:"Добавить шаг для «Нет»"}));
 fireEvent.click(screen.getByRole("button",{name:/^Спросить сотрудника/}));
 const both=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;
 expect(both.blocks).toHaveLength(4);
 expect(both.blocks![1].transitions![0]).toEqual(yesEdge);
 expect(both.blocks![1].transitions![1].when).toEqual({source:"answer",field:"working",op:"eq",value:false});
 expect(both.blocks![2]).toEqual(yes.blocks![2]);
 expect(both.blocks![0].transitions).toEqual([{to:"branch"}]);
 fireEvent.click(screen.getByRole("button",{name:"Отменить изменение"}));
 expect(change.mock.calls.at(-1)![0]).toEqual(yes);
 fireEvent.click(screen.getByRole("button",{name:"Отменить изменение"}));
 expect(change.mock.calls.at(-1)![0]).toEqual(initial);
});
it("keeps exactly one block editor when switching between decision blocks",()=>{
 const d:ScenarioDraftDefinition={...definition,schema_version:2,blocks:[{id:"q",kind:"decision",title:"Первое",transitions:[{to:"branch"}]},{id:"branch",kind:"decision",title:"Второе",transitions:[{to:"done"}]},definition.blocks![1]]};
 render(<MemoryRouter><ScenarioMapWorkbench definition={d} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать второе условие"}));
 expect(screen.getAllByLabelText("Название блока")).toHaveLength(1);
 expect(screen.getByLabelText("Название блока")).toHaveValue("Второе");
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 expect(screen.getAllByLabelText("Название блока")).toHaveLength(1);
 expect(screen.getByLabelText("Название блока")).toHaveValue("Первое");
});
it("keeps historical questions read-only until an explicit source migration",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 const change=vi.fn();const view=render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing disabled={false} onChange={change}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 expect(screen.getByLabelText("Текст инструкции")).toBeDisabled();
 fireEvent.click(screen.getByRole("button",{name:"Перевести карту на единую модель"}));
 const migrated=change.mock.calls[0][0];expect(migrated.schema_version).toBe(2);expect(migrated.blocks).toEqual(definition.blocks);
 view.rerender(<MemoryRouter><ScenarioMapWorkbench definition={migrated} catalog={catalog} existing disabled={false} onChange={change}/></MemoryRouter>);
 expect(screen.getByLabelText("Текст инструкции")).toBeEnabled();
});
it("opens deletion in a visible dialog and keeps errors next to confirmation",()=>{
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Удалить блок"}));
 expect(screen.getByRole("dialog",{name:"Удалить блок «Проверка»?"})).toBeVisible();
 expect(screen.getByLabelText("Что сделать со связями?")).toBeVisible();
});
it("edits decision conditions directly in the selected block",()=>{
 const d:ScenarioDraftDefinition={...definition,entry_block_id:"branch",blocks:[{id:"q",kind:"form_page",title:"Вопрос",fields:[{key:"vpn",type:"checkbox",label:"Нужен VPN?"}],transitions:[{to:"branch"}]},{id:"branch",kind:"decision",title:"Маршрут",transitions:[{to:"done",when:{op:"eq",source:"answer",field:"vpn",value:true}}]},definition.blocks![1]]};
 render(<MemoryRouter><ScenarioMapWorkbench definition={{...d,blocks:[d.blocks![1],d.blocks![0],d.blocks![2]]}} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button", {name:/Ветвь 1/}));
 expect(screen.getByLabelText("Значение условия")).toBeVisible();
 fireEvent.click(screen.getByRole("button", {name:/^Иначе/}));
 expect(screen.getByLabelText("Если ни одно условие не выполнено")).toBeVisible();
});
it("an unbound v2 map needs no canonical type picker",()=>{
 render(<MemoryRouter><ScenarioMapWorkbench definition={{...definition,schema_version:2,offering_full_code:"",blocks:[],entry_block_id:null,entry_points:[]}} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 expect(screen.queryByLabelText("Тип обращения")).not.toBeInTheDocument();
 expect(screen.getByLabelText("Название услуги")).toBeVisible();
});
it("policy remediation leaves preview and entrance selection for service processing",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 const change=vi.fn();const view=render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={change}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать связь входа"}));fireEvent.click(screen.getByRole("tab",{name:"Как у сотрудника"}));
 view.rerender(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={change} issuePolicy="routing"/></MemoryRouter>);
 expect(screen.getByRole("tab",{name:"Настройки"})).toHaveAttribute("aria-selected","true");await screen.findByLabelText("Маршрут и очередь");await waitFor(()=>expect(screen.getByLabelText("Маршрут и очередь")).toHaveFocus());expect(screen.queryByLabelText("Название услуги")).not.toBeInTheDocument();expect(screen.queryByRole("heading",{name:"Связь с началом"})).not.toBeInTheDocument();expect(change).not.toHaveBeenCalled();
});
it("a missing-route hint reveals editing controls from employee preview",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));fireEvent.click(screen.getByRole("tab",{name:"Как у сотрудника"}));fireEvent.click(screen.getByRole("button",{name:/«Проверка»: укажите следующий шаг/}));fireEvent.click(screen.getByRole("button",{name:/Исправить: «Проверка»: укажите следующий шаг/}));expect(screen.getByRole("tab",{name:"Настройки"})).toHaveAttribute("aria-selected","true");expect(screen.getByLabelText("Название блока")).toBeVisible();
});
