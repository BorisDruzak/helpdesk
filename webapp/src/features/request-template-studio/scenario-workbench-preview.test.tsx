import { fireEvent,render,screen,waitFor,within } from "@testing-library/react";
import { act, useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach,expect,it,vi } from "vitest";
import { ScenarioMapWorkbench } from "./scenario-map-workbench";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const { canvasState }=vi.hoisted(()=>({canvasState:{current:null as any}}));
vi.mock("./scenario-map-canvas",()=>({metadataNodeId:"studio:metadata",transitionId:(source:string,index:number)=>`${source}:${index}`,entranceEdgeId:(key:string|null)=>`entry:${key}`,entranceCardId:(key:string|null)=>`card:${key}`,ScenarioMapCanvas:(props:any)=>{canvasState.current=props;const {onSelect,onEntrance,expandedId,inlineEditor,entranceEditor}=props;return <div><button onClick={()=>onSelect("q")}>Выбрать вопрос</button><button onClick={()=>onSelect("branch")}>Выбрать второе условие</button><button onClick={()=>onEntrance("named","q")}>Выбрать связь входа</button>{expandedId && inlineEditor}{entranceEditor}</div>;}}));

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
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 fireEvent.click(screen.getByRole("button",{name:"Добавить шаг для «Да»"}));
 fireEvent.click(screen.getByRole("button",{name:/^Показать инструкцию/}));
 const yes=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;
 expect(yes.blocks).toHaveLength(3);
 const yesEdge=yes.blocks![1].transitions![0];
 expect(yesEdge.when).toEqual({source:"answer",field:"working",op:"eq",value:true});
 fireEvent.click(screen.getByRole("button",{name:"Выбрать второе условие"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
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
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 expect(screen.getAllByLabelText("Название блока")).toHaveLength(1);
 expect(screen.getByLabelText("Название блока")).toHaveValue("Второе");
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 expect(screen.getAllByLabelText("Название блока")).toHaveLength(1);
 expect(screen.getByLabelText("Название блока")).toHaveValue("Первое");
});
it("keeps historical questions read-only until an explicit source migration",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 const change=vi.fn();const view=render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing disabled={false} onChange={change}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 expect(screen.getByLabelText("Текст инструкции")).toBeDisabled();
 fireEvent.click(screen.getByRole("button",{name:"Перевести карту на единую модель"}));
 const migrated=change.mock.calls[0][0];expect(migrated.schema_version).toBe(2);expect(migrated.blocks).toEqual(definition.blocks);
 view.rerender(<MemoryRouter><ScenarioMapWorkbench definition={migrated} catalog={catalog} existing disabled={false} onChange={change}/></MemoryRouter>);
 expect(screen.getByLabelText("Текст инструкции")).toBeEnabled();
});
it("opens deletion in a visible dialog and keeps errors next to confirmation",()=>{
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 fireEvent.click(screen.getByRole("button",{name:"Удалить блок"}));
 expect(screen.getByRole("dialog",{name:"Удалить блок «Проверка»?"})).toBeVisible();
 expect(screen.getByLabelText("Что сделать со связями?")).toBeVisible();
});
it("edits decision conditions directly in the selected block",()=>{
 const d:ScenarioDraftDefinition={...definition,entry_block_id:"branch",blocks:[{id:"q",kind:"form_page",title:"Вопрос",fields:[{key:"vpn",type:"checkbox",label:"Нужен VPN?"}],transitions:[{to:"branch"}]},{id:"branch",kind:"decision",title:"Маршрут",transitions:[{to:"done",when:{op:"eq",source:"answer",field:"vpn",value:true}}]},definition.blocks![1]]};
 render(<MemoryRouter><ScenarioMapWorkbench definition={{...d,blocks:[d.blocks![1],d.blocks![0],d.blocks![2]]}} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать второе условие"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 fireEvent.click(screen.getByRole("button", {name:/Ветвь 1/}));
 expect(screen.getByLabelText("Значение условия")).toBeVisible();
 fireEvent.click(screen.getByRole("button", {name:/^Иначе/}));
 expect(screen.getByLabelText("Если ни одно условие не выполнено")).toBeVisible();
});
it("an unbound v2 map needs no canonical type picker",()=>{
 render(<MemoryRouter><ScenarioMapWorkbench definition={{...definition,schema_version:2,offering_full_code:"",blocks:[],entry_block_id:null,entry_points:[]}} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 expect(screen.queryByLabelText("Тип обращения")).not.toBeInTheDocument();
 expect(screen.queryByLabelText("Название услуги")).not.toBeInTheDocument();
 expect(screen.getByRole("button",{name:"+ Вход из каталога"})).toBeEnabled();
});
it("opens service-wide rules through publication callback without mounting generic processing",()=>{
 const change=vi.fn(), openRules=vi.fn();
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={change} onPublicationRules={openRules}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Правила услуги на публикации"}));
 expect(openRules).toHaveBeenCalledTimes(1);
 expect(screen.queryByLabelText("Маршрут и очередь")).not.toBeInTheDocument();
 expect(screen.queryByRole("heading",{name:"Обработка услуги"})).not.toBeInTheDocument();
 expect(change).not.toHaveBeenCalled();
});

it("a missing-route hint reveals editing controls from employee preview",()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"success",data:{policies:{}}}),{headers:{"content-type":"application/json"}})));
 render(<MemoryRouter><ScenarioMapWorkbench definition={definition} catalog={catalog} existing={false} disabled={false} onChange={vi.fn()}/></MemoryRouter>);
 fireEvent.click(screen.getByRole("button",{name:"Выбрать вопрос"}));
 fireEvent.click(screen.getByRole("button",{name:"Редактировать выбранный блок"}));fireEvent.click(screen.getByRole("tab",{name:"Как у сотрудника"}));fireEvent.click(screen.getByRole("button",{name:/«Проверка»: укажите следующий шаг/}));fireEvent.click(screen.getByRole("button",{name:/Исправить: «Проверка»: укажите следующий шаг/}));expect(screen.getByRole("tab",{name:"Настройки"})).toHaveAttribute("aria-selected","true");expect(screen.getByLabelText("Название блока")).toBeVisible();
});

it("keeps inspection and help under More without duplicate preview or metadata editors",()=>{
 const change=vi.fn();
 render(<ScenarioMapWorkbench definition={definition} catalog={catalog} existing disabled={false} onChange={change}/>);
 const more=screen.getByText("Ещё",{selector:"summary"}).closest("details")!;
 expect(more).toContainElement(screen.getByRole("button",{name:"Редактировать выбранный блок"}));
 expect(more).toContainElement(screen.getByText("Как работать с картой",{selector:"summary"}));
 expect(screen.queryByRole("button",{name:"Предпросмотр страницы"})).not.toBeInTheDocument();
 expect(screen.queryByRole("button",{name:"Настройки карты"})).not.toBeInTheDocument();
 expect(screen.queryByLabelText("Название услуги")).not.toBeInTheDocument();
 expect(change).not.toHaveBeenCalled();
});

it("creates a persistent pending library entrance with no step selection and undoes it atomically",()=>{
 const initial={...definition,schema_version:3 as const};const change=vi.fn();
 function Harness(){const [d,setD]=useState(initial);return <MemoryRouter><ScenarioMapWorkbench definition={d} catalog={catalog} existing disabled={false} onChange={next=>{change(next);setD(next as typeof initial);}}/></MemoryRouter>;}
 render(<Harness/>);fireEvent.click(within(screen.getByRole("complementary",{name:"Библиотека блоков"})).getByRole("button",{name:"+ Вход из каталога"}));
 const next=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;expect(next.entry_points).toEqual(initial.entry_points);expect(next.blocks).toEqual(initial.blocks);expect(next.entry_block_id).toBe("q");expect(next.schema_version).toBe(3);
 expect(next.editor_layout?.pending_entrances).toHaveLength(1);expect(screen.getByLabelText("Первый блок для сотрудника").closest("details")).not.toHaveAttribute("open");
 expect(screen.getByText(/Потяните связь из правой точки/)).toBeVisible();fireEvent.click(screen.getByRole("button",{name:"Отменить изменение"}));expect(change.mock.calls.at(-1)![0]).toEqual(initial);
});

it("creates navigation from the library then connects an existing source without a replacement step",()=>{
 const initial={...definition,schema_version:4 as const};const change=vi.fn();
 function Harness(){const [d,setD]=useState<ScenarioDraftDefinition>(initial);return <MemoryRouter><ScenarioMapWorkbench definition={d} catalog={catalog} existing disabled={false} onChange={next=>{change(next);setD(next);}}/></MemoryRouter>;}
 render(<Harness/>);
 fireEvent.click(screen.getByRole("button",{name:"+ Переходы · кнопки"}));
 const created=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition,nav=created.blocks!.at(-1)!;
 expect(nav.kind).toBe("navigation");expect(created.blocks!.slice(0,-1)).toEqual(initial.blocks);
 act(()=>canvasState.current.onConnect("q",nav.id,"new"));
 const connected=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;
 expect(connected.blocks).toHaveLength(initial.blocks!.length+1);
 expect(connected.blocks!.find(block=>block.id==="q")!.transitions).toEqual([{to:nav.id}]);
 expect(connected.blocks!.find(block=>block.id===nav.id)!.kind).toBe("navigation");
 expect(connected.entry_points).toEqual(initial.entry_points);
});
it("creates a root entrance on an empty map and completes it with a new visual step",()=>{
 const initial={...definition,schema_version:4 as const,blocks:[],entry_points:[],entry_block_id:null};const change=vi.fn();
 function Harness(){const [d,setD]=useState<ScenarioDraftDefinition>(initial);return <MemoryRouter><ScenarioMapWorkbench definition={d} catalog={catalog} existing disabled={false} onChange={next=>{change(next);setD(next);}}/></MemoryRouter>;}
 render(<Harness/>);
 fireEvent.click(screen.getByRole("button",{name:"+ Вход из каталога"}));
 const pending=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition,entry=pending.editor_layout!.pending_entrances![0];
 expect(pending.blocks).toEqual([]);expect(pending.entry_block_id).toBeNull();expect(pending.entry_points).toEqual([]);
 const bounds=screen.getByRole("complementary",{name:"Библиотека блоков"}).parentElement!;vi.spyOn(bounds,"getBoundingClientRect").mockReturnValue({left:0,top:0,width:900,height:500} as DOMRect);
 act(()=>canvasState.current.onConnectionDrop({type:"entrance",key:entry.key,point:{x:500,y:200}}));
 fireEvent.click(screen.getByRole("menuitem",{name:"Вопрос"}));
 const next=change.mock.calls.at(-1)![0] as ScenarioDraftDefinition;
 expect(next.blocks).toHaveLength(1);expect(next.blocks![0].kind).toBe("form_page");
 expect(next.entry_points?.[0]).toMatchObject({key:entry.key,target_block_id:next.blocks![0].id});
 expect(next.entry_block_id).toBe(next.blocks![0].id);expect(next.editor_layout?.pending_entrances).toEqual([]);
});
