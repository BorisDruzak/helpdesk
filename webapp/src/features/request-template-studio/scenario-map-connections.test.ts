import { expect,it } from "vitest";
import { addConnectedMapBlock } from "./scenario-map-connections";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const d:ScenarioDraftDefinition={schema_version:4,scenario_key:"s",service_code:"it",offering_full_code:"it.test",process_binding:{request_template_key:"request"},title:"Test",entry_block_id:"q",blocks:[{id:"q",kind:"instruction",title:"Q",content:{body:"Q"},transitions:[{to:"end"}]},{id:"end",kind:"submit_ticket",title:"End"},{id:"sla",kind:"sla_attachment",title:"SLA"}]};
it("creates new visual flow branches, preserves old continuation on route insertion and attaches policies",()=>{
 const at={x:200,y:100};const next=addConnectedMapBlock(d,{type:"source",source:"q",handle:"new",point:at},"instruction",at);
 expect(next.blocks).toHaveLength(4);expect(next.blocks![0].transitions).toHaveLength(2);expect(next.blocks![0].transitions![0].to).toBe("end");
 const inserted=addConnectedMapBlock(d,{type:"route",source:"q",index:0,point:at},"decision",at);expect(inserted.blocks?.at(-1)?.transitions).toEqual([{to:"end"}]);
 const attached=addConnectedMapBlock(d,{type:"source",source:"sla",handle:"policy",point:at},"instruction",at);expect(attached.blocks?.find(b=>b.id==="sla")).toMatchObject({attached_to:attached.blocks?.at(-1)?.id});expect(attached.blocks?.find(b=>b.id==="q")?.transitions).toEqual(d.blocks![0].transitions);
});
