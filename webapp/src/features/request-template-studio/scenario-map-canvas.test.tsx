import { createElement, useState, type ComponentType } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioMapCanvas, entranceCardId, transitionCardId, type MapNode } from "./scenario-map-canvas";
it("opens a Start subsection without serializing a definition change", () => {
  const section = vi.fn();
  render(<ScenarioMapCanvas {...props} definition={definition} onStartSection={section} />);
  fireEvent.click(screen.getByRole("button", { name: "Начало: Раздел и категория" }));
  expect(section).toHaveBeenCalledWith("catalog");
});
import type { ScenarioDraftDefinition } from "./scenario-contract";
const { fitProjectedCard }=vi.hoisted(()=>({fitProjectedCard:vi.fn()}));

vi.mock("@xyflow/react", () => ({
  Background: () => null, Controls: () => null, MarkerType: { ArrowClosed: "arrow" }, Position: { Left: "left", Right: "right", Bottom: "bottom" },
  useUpdateNodeInternals: () => vi.fn(),
  useNodesState: (initial: MapNode[]) => { const [nodes, setNodes] = useState(initial); return [nodes, setNodes, vi.fn()]; },
  Handle: ({ id, "aria-label": label, isConnectable }: { id?: string; "aria-label"?: string; isConnectable?: boolean }) => <span data-testid={`handle-${id ?? "target"}`} aria-label={label} data-connectable={String(isConnectable ?? true)} />,
  ReactFlow: ({ nodes, edges, nodeTypes, onNodesChange,onConnect,onReconnect,onInit }: { onInit:(instance:unknown)=>void;onConnect:(connection:{source:string;target:string})=>void;onReconnect:(edge:unknown,connection:{source:string;target:string})=>void;onNodesChange: (changes: unknown[]) => void; nodes: MapNode[]; edges: { id: string; label: string; data?: { editor?: React.ReactNode; attachment?: boolean } }[]; nodeTypes: { scenario: ComponentType<{ id: string; data: MapNode["data"]; selected?: boolean }> } }) => <><button onClick={()=>onInit({fitView:fitProjectedCard,getZoom:()=>1})}>initialize map</button><button onClick={()=>onNodesChange([{type:"position",id:transitionCardId("q",0),position:{x:700,y:400},dragging:false}])}>move transition card</button><button onClick={()=>onConnect({source:transitionCardId("q",0),target:"end"})}>connect transition card</button><button onClick={()=>onConnect({source:"q",target:entranceCardId(null)})}>try route into entrance</button><button onClick={()=>onConnect({source:transitionCardId("q",0),target:entranceCardId(null)})}>try card into entrance</button><button onClick={()=>onReconnect({data:{route:{source:"q",index:0}}},{source:transitionCardId("q",0),target:entranceCardId(null)})}>try reconnect into entrance</button><button onClick={() => onNodesChange([{type: "position", id: "studio:legacy-sla:q", position: {x: 1, y: 2}, dragging: false}])}>simulate auxiliary move</button>{nodes.map(node => <div key={node.id} data-testid={`node-${node.id}`}>{createElement(nodeTypes.scenario, { id: node.id, data: node.data, selected: node.selected })}</div>)}{edges.map(edge => <span key={edge.id} data-testid={`edge-${edge.id}`} data-attachment={String(!!edge.data?.attachment)}>{edge.label}{edge.data?.editor}</span>)}</>,
}));
const definition: ScenarioDraftDefinition = { schema_version: 3, scenario_key: "test", service_code: "it", offering_full_code: "it.test", title: "Test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
  { id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "answer", type: "checkbox", label: "123" }], transitions: [{ to: "d" }] },
  { id: "d", kind: "decision", title: "Условие", transitions: [] },
  { id: "end", kind: "submit_ticket", title: "Обращение" },
] };
const props = { selected: "d", selectedEdge: null, disabled: false, onSelect: vi.fn(), onEdge: vi.fn(), onMove: vi.fn(), onConnect: vi.fn(), onReconnect: vi.fn(), onDropBlock: vi.fn(), onEntrance: vi.fn(), onEntranceReconnect: vi.fn(), onReady: vi.fn() };
it("persists the shifted node origin once when resizing its north-west edge",()=>{
 const move=vi.fn();
 render(<ScenarioMapCanvas {...props} onMove={move} definition={{...definition,editor_layout:{positions:{q:{x:100,y:100}}}}} expandedId="q" inlineEditor={<p>Содержимое</p>}/>);
 fireEvent.keyDown(screen.getByRole("button",{name:"Изменить размер редактора блока: верхний левый угол"}),{key:"ArrowLeft"});
 expect(move).toHaveBeenCalledTimes(1);
 expect(move).toHaveBeenCalledWith("q",{x:80,y:100});
});
it("shows the server-confirmed SLA, queue and actual route at the terminal node", () => {
  render(<ScenarioMapCanvas {...props} definition={definition} simulationResult={{ state: { current_block_id: "end", history: ["q","d"] }, processing: { sla: { first_response_min: 5, resolution_min: 60, time_basis: "calendar" }, routing: { queue_title: "Сетевая поддержка" } } } as never} />);
  const end = screen.getByTestId("node-end");
  expect(end).toHaveTextContent("решение 60 мин.");
  expect(end).toHaveTextContent("Сетевая поддержка");
  expect(end).toHaveTextContent("Пройденный маршрут");
  expect(end).toHaveTextContent("Условие → Обращение");
});
it("offers explicit Yes and No actions on an empty decision without changing the definition", () => {
  const onAnswerAdd = vi.fn(), before = structuredClone(definition);
  render(<ScenarioMapCanvas {...props} definition={definition} onAnswerAdd={onAnswerAdd} />);
  expect(screen.getByText("По ответу: 123")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" }));
  expect(onAnswerAdd).toHaveBeenCalledWith("d", { source: "answer", field: "answer", op: "eq", value: false });
  expect(screen.getByRole("button", { name: "Добавить шаг для «Да» после «Условие»" })).toBeEnabled();
  expect(screen.getByTestId("handle-answer-0")).toBeInTheDocument(); expect(screen.getByTestId("handle-answer-1")).toBeInTheDocument();
  expect(definition).toEqual(before);
});
it("renders the expanded editor inside its own map node", () => {
  const select = vi.fn();
  render(<div onClick={select}><ScenarioMapCanvas {...props} definition={definition} expandedId="q" inlineEditor={<label>Редактор внутри блока<input aria-label="Текст внутри блока" /></label>} /></div>);
  expect(screen.getByTestId("node-q")).toContainElement(screen.getByLabelText("Текст внутри блока"));
  fireEvent.click(screen.getByLabelText("Текст внутри блока")); expect(select).not.toHaveBeenCalled();
});
it("shows an existing typed answer branch with one reconnect handle and keeps the other answer available", () => {
  const next = structuredClone(definition); next.blocks![1].transitions = [{ to: "end", when: { source: "answer", field: "answer", op: "eq", value: true } }, { to: "end" }];
  render(<ScenarioMapCanvas {...props} definition={next} onAnswerAdd={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Добавить шаг для «Да» после «Условие»" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" })).toBeEnabled();
  expect(screen.getAllByTestId("handle-route-0")).toHaveLength(2); // One ordinary question route and one decision route.
  expect(screen.queryByTestId("handle-answer-0")).not.toBeInTheDocument();
  expect(screen.getByText(/123 равно «Да»/)).toBeVisible(); expect(screen.getByText("Иначе")).toBeVisible();
});
it("keeps answer choices visible but prevents answer actions for a read-only canvas", () => {
  const onAnswerAdd = vi.fn(); render(<ScenarioMapCanvas {...props} disabled definition={definition} onAnswerAdd={onAnswerAdd} />);
  const no = screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" });
  expect(no).toBeDisabled(); fireEvent.click(no); expect(onAnswerAdd).not.toHaveBeenCalled();
});
it("shows legacy SLA editor in its expanded auxiliary node without bubbling clicks", () => {
  const outside = vi.fn();
  render(<div onClick={outside}><ScenarioMapCanvas {...props} definition={definition} auxiliaryEditors={{q: <input aria-label="Старые правила SLA" />}} expandedId="studio:legacy-sla:q" /></div>);
  const input = screen.getByLabelText("Старые правила SLA");
  expect(screen.getByTestId("node-studio:legacy-sla:q")).toContainElement(input);
  expect(screen.getByLabelText("Вход блока «SLA по ответам и ветвям»")).toHaveAttribute("data-connectable", "false");
  fireEvent.click(input); expect(outside).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("simulate auxiliary move")); expect(props.onMove).not.toHaveBeenCalledWith("studio:legacy-sla:q", expect.anything());
});

it("opens the selected transition editor inside a draggable transition card rather than in a side inspector",()=>{
 render(<ScenarioMapCanvas {...props} definition={definition} selectedEdge="q:0" edgeEditor={<textarea aria-label="Переход на карте"/>}/>);
 const card=screen.getByTestId(`node-${transitionCardId("q",0)}`);
 expect(card).toContainElement(screen.getByRole("textbox",{name:"Переход на карте"}));
 expect(card.querySelector('[data-testid="handle-in"]')).not.toBeNull();expect(card.querySelector('[data-testid="handle-out"]')).not.toBeNull();
 expect(screen.getByTestId("edge-q:0:input")).toBeInTheDocument();expect(screen.getByTestId("edge-q:0")).toBeInTheDocument();
});
it("puts the catalog entrance editor into its own map card",()=>{
 render(<ScenarioMapCanvas {...props} definition={{...definition,entry_points:[{key:"entry",title:"Название входа",target_block_id:"q"}]}} selectedEdge="studio:entry-point:entry" entranceEditor={<textarea aria-label="Пункт на карте"/>}/>);
 expect(screen.getByTestId(`node-${entranceCardId("entry")}`)).toContainElement(screen.getByRole("textbox",{name:"Пункт на карте"}));
});
it("keeps implicit primary and a named primary entrance as distinct selectable cards and connector pairs",()=>{
 const onEntrance=vi.fn();
 const next={...definition,schema_version:4 as const,execution_semantics:3 as const,entry_points:[{key:"primary",title:"Другой вход",target_block_id:"end"}]};
 render(<ScenarioMapCanvas {...props} definition={next} onEntrance={onEntrance}/>);
 expect(entranceCardId(null)).not.toBe(entranceCardId("primary"));
 const implicit=screen.getByTestId(`node-${entranceCardId(null)}`),named=screen.getByTestId(`node-${entranceCardId("primary")}`);
 expect(implicit).not.toBe(named);
 fireEvent.click(within(implicit).getByRole("button",{name:"Редактировать вход"}));expect(onEntrance).toHaveBeenLastCalledWith(null,"q");
 fireEvent.click(within(named).getByRole("button",{name:"Редактировать вход"}));expect(onEntrance).toHaveBeenLastCalledWith("primary","end");
 for(const edgeId of ["studio:primary","studio:entry-point:primary"]){expect(screen.getByTestId(`edge-${edgeId}:input`)).toBeInTheDocument();expect(screen.getByTestId(`edge-${edgeId}`)).toBeInTheDocument();}
});
it("renders an attached SLA card with a setting link and no flow ports or next-step action",()=>{
 const next={...definition,schema_version:4 as const,execution_semantics:3 as const,blocks:[...definition.blocks!,{id:"policy",kind:"sla_attachment" as const,title:"Политика SLA",attached_to:"q"}]};
 render(<ScenarioMapCanvas {...props} definition={next}/>);
 const card=screen.getByTestId("node-policy");
 expect(card.querySelector('[data-testid="handle-target"]')).toBeNull();
 expect(card.querySelector('[data-testid="handle-policy"]')).not.toBeNull();
 expect(screen.queryByRole("button",{name:"Добавить следующий шаг после «Политика SLA»"})).not.toBeInTheDocument();
 expect(screen.getByTestId("edge-studio:attachment:policy")).toHaveAttribute("data-attachment","true");
});

it("moves projected cards as local layout and reconnects their original transition",()=>{
 localStorage.clear();const move=vi.fn(),reconnect=vi.fn();render(<ScenarioMapCanvas {...props} definition={definition} onMove={move} onReconnect={reconnect}/>);
 fireEvent.click(screen.getByText("move transition card"));expect(move).not.toHaveBeenCalled();
 expect(Object.values(JSON.parse(localStorage.getItem("studio-map-link-positions:v1:test")!))).toContainEqual({x:700,y:400});
 fireEvent.click(screen.getByText("connect transition card"));expect(reconnect).toHaveBeenCalledWith("q",0,"end");
});

it.each(["route","entry"] as const)("fits an expanded projected %s card after layout once, without moving the camera on edits",kind=>{
 const frames:FrameRequestCallback[]=[];vi.stubGlobal("requestAnimationFrame",(callback:FrameRequestCallback)=>{frames.push(callback);return frames.length;});vi.stubGlobal("cancelAnimationFrame",vi.fn());fitProjectedCard.mockClear();
 const next={...definition,entry_points:[{key:"named",title:"Пункт",target_block_id:"q"}]};
 const view=render(<ScenarioMapCanvas {...props} definition={next}/>);fireEvent.click(screen.getByText("initialize map"));
 const editor=<input aria-label="Редактор карточки"/>;
 const expanded=kind==="route"?{selectedEdge:"q:0",edgeEditor:editor}:{selectedEdge:"studio:entry-point:named",entranceEditor:editor};
 view.rerender(<ScenarioMapCanvas {...props} definition={next} {...expanded}/>);
 act(()=>{frames.shift()?.(0);});act(()=>{frames.shift()?.(0);});
 expect(fitProjectedCard).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({nodes:[{id:kind==="route"?transitionCardId("q",0):entranceCardId("named")}]}));
 view.rerender(<ScenarioMapCanvas {...props} definition={{...next,title:"Правка текста"}} {...expanded}/>);
 expect(frames).toHaveLength(0);expect(fitProjectedCard).toHaveBeenCalledOnce();view.unmount();vi.unstubAllGlobals();
});

it("rejects ordinary route, card and reconnect targets pointing into a catalog entrance",()=>{
 const connect=vi.fn(),reconnect=vi.fn();render(<ScenarioMapCanvas {...props} definition={definition} onConnect={connect} onReconnect={reconnect}/>);
 fireEvent.click(screen.getByRole("button",{name:"try route into entrance"}));fireEvent.click(screen.getByRole("button",{name:"try card into entrance"}));fireEvent.click(screen.getByRole("button",{name:"try reconnect into entrance"}));
 expect(connect).not.toHaveBeenCalled();expect(reconnect).not.toHaveBeenCalled();
 const entry=screen.getByTestId(`node-${entranceCardId(null)}`);expect(entry).toHaveTextContent("Вход из каталога");expect(entry).toHaveTextContent("Начало → вход из каталога");
});
