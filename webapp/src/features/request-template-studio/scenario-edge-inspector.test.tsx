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
