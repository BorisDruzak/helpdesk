import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioEdgeInspector } from "./scenario-edge-inspector";
import type { ScenarioDraftDefinition } from "./scenario-contract";
it("edits automatic transition priority while preserving its condition and processing", () => {
 const edge={to:"end",priority:7,when:{source:"answer",op:"eq",field:"f",value:"yes"},processing_facts:{urgency:"blocked"}};
 const definition={scenario_key:"x",title:"X",blocks:[{id:"q",kind:"form_page",title:"Q",fields:[],transitions:[edge]},{id:"end",kind:"finish",title:"End"}]} as unknown as ScenarioDraftDefinition;
 const change=vi.fn(); render(<ScenarioEdgeInspector definition={definition} source="q" index={0} disabled={false} onChange={change}/>);
 fireEvent.change(screen.getByLabelText("Приоритет перехода"),{target:{value:"3"}});
 expect(change.mock.lastCall![0].blocks[0].transitions[0]).toEqual({...edge,priority:3});
});
it("does not show automatic precedence for button-mode edges", () => {
 const definition={scenario_key:"x",title:"X",blocks:[{id:"q",kind:"navigation",title:"Q",transition_mode:"buttons",transitions:[{to:"end"}]},{id:"end",kind:"finish",title:"End"}]} as unknown as ScenarioDraftDefinition;
 render(<ScenarioEdgeInspector definition={definition} source="q" index={0} disabled={false} onChange={vi.fn()}/>);
 expect(screen.queryByLabelText("Приоритет перехода")).not.toBeInTheDocument();
});
it("does not offer automatic mode for a navigation block",()=>{
 const definition={schema_version:4,scenario_key:"x",title:"X",blocks:[{id:"q",kind:"navigation",title:"Выбор",transition_mode:"buttons",transitions:[{to:"end",button:{key:"action",label:"Перейти"}}]},{id:"end",kind:"finish",title:"End"}]} as unknown as ScenarioDraftDefinition;
 const change=vi.fn();render(<ScenarioEdgeInspector definition={definition} source="q" index={0} disabled={false} onChange={change}/>);
 expect(screen.queryByRole("option",{name:"Автоматически по условию"})).not.toBeInTheDocument();
 expect(change).not.toHaveBeenCalled();
});
it("explains the button-mode limit and preserves more than ten automatic routes without an uncaught error",()=>{
 const transitions=Array.from({length:11},(_,i)=>({to:`end${i}`,priority:i+1}));
 const definition={schema_version:4,scenario_key:"x",title:"X",blocks:[{id:"q",kind:"form_page",title:"Выбор",fields:[],transitions},...transitions.map(edge=>({id:edge.to,kind:"finish",title:edge.to}))]} as unknown as ScenarioDraftDefinition;
 const change=vi.fn();render(<ScenarioEdgeInspector definition={definition} source="q" index={0} disabled={false} onChange={change}/>);
 expect(screen.getByRole("option",{name:"Выбирает кнопку перехода"})).toBeDisabled();
 expect(()=>fireEvent.change(screen.getByLabelText("Как сотрудник переходит дальше"),{target:{value:"buttons"}})).not.toThrow();
 expect(screen.getByRole("alert")).toHaveTextContent("не более 10");
 expect(change).not.toHaveBeenCalled();expect(definition.blocks![0].transitions).toEqual(transitions);
});
