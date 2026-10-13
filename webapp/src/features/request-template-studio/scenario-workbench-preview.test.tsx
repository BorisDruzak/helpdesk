import { fireEvent,render,screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach,expect,it,vi } from "vitest";
import { ScenarioMapWorkbench } from "./scenario-map-workbench";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-map-canvas",()=>({metadataNodeId:"studio:metadata",transitionId:(source:string,index:number)=>`${source}:${index}`,entranceEdgeId:(key:string|null)=>`entry:${key}`,ScenarioMapCanvas:({onSelect,onEntrance}:{onSelect:(id:string)=>void;onEntrance:(key:string,target:string)=>void})=><div><button onClick={()=>onSelect("q")}>Выбрать вопрос</button><button onClick={()=>onEntrance("named","q")}>Выбрать связь входа</button></div>}));
const definition:ScenarioDraftDefinition={scenario_key:"s",title:"Карта",service_code:"it",offering_full_code:"it.p",process_binding:{request_template_key:"p"},entry_block_id:"q",entry_points:[{key:"named",title:"Вход",target_block_id:"q"}],blocks:[{id:"q",kind:"instruction",title:"Проверка",content:{body:"Шаг"},transitions:[]},{id:"done",kind:"finish",title:"Готово"}]};
const catalog={services:[],offerings:[],categories:[],scenarios:[],total:0,offset:0,limit:100};
afterEach(()=>vi.unstubAllGlobals());
it("policy remediation leaves preview and entrance selection for metadata settings",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 const change=vi.fn();const view=render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={change}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать связь входа"}));fireEvent.click(screen.getByRole("tab",{name:"Как у сотрудника"}));
 view.rerender(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={change} issuePolicy="routing"/></MemoryRouter>);
 expect(screen.getByRole("tab",{name:"Настройки"})).toHaveAttribute("aria-selected","true");expect(screen.getByLabelText("Название сценария")).toBeVisible();expect(screen.queryByRole("heading",{name:"Связь с началом"})).not.toBeInTheDocument();expect(change).not.toHaveBeenCalled();
});
it("a missing-route hint reveals editing controls from employee preview",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));fireEvent.click(screen.getByRole("tab",{name:"Как у сотрудника"}));fireEvent.click(screen.getByRole("button",{name:/Что ещё настроить/}));fireEvent.click(screen.getByRole("button",{name:/«Проверка»: укажите следующий шаг/}));expect(screen.getByRole("tab",{name:"Настройки"})).toHaveAttribute("aria-selected","true");expect(screen.getByLabelText("Название блока")).toBeVisible();
});
