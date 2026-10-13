import { expect, it } from "vitest";
import { addTemplateQuestions } from "./scenario-template-questions";
import type { ScenarioDraftDefinition } from "./scenario-contract";
it("collects canonical mandatory answers before the result without losing branch conditions",()=>{
 const d:ScenarioDraftDefinition={scenario_key:"s",title:"Map",service_code:"it",offering_full_code:"it.vpn",process_binding:{request_template_key:"vpn"},entry_block_id:"q",blocks:[{id:"q",kind:"resolution_check",title:"Check",transitions:[{to:"ticket",when:{source:"current_result",op:"eq",value:"no"}},{to:"ticket"}]},{id:"ticket",kind:"submit_ticket",title:"Ticket"}]};
 const next=addTemplateQuestions(d,"ticket",[{key:"impact_scope",label:"Who?",type:"select",required:true,options:[{value:"one",label:"Only me"}],process_mapping:{roles:["priority_impact"]}}]);
 const page=next.blocks!.at(-1)!;expect(page.kind).toBe("form_page");
 expect(next.blocks![0].transitions).toEqual(d.blocks![0].transitions!.map(edge=>({...edge,to:page.id})));
 if(page.kind==="form_page")expect(page.fields[0]).toMatchObject({required:true,process_mapping:{fact_key:"impact_scope",roles:["priority_impact"]}});
 expect(page.transitions).toEqual([{to:"ticket"}]); expect(next.editor_layout?.positions?.ticket).toEqual({x:310,y:0});
 expect(addTemplateQuestions(next,"ticket",[{key:"impact_scope",label:"Who?",type:"select",required:true}])).toBe(next);
});
