import { expect,it } from "vitest";
import { beginCatalogEntrance,completeCatalogEntrance,moveCatalogEntrance,removeCatalogEntrance } from "./scenario-pending-entrances";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const d:ScenarioDraftDefinition={schema_version:3,scenario_key:"s",service_code:"it",offering_full_code:"it.test",process_binding:{request_template_key:"request"},title:"Test",entry_block_id:"a",entry_points:[{key:"old",title:"Old",target_block_id:"a"}],blocks:[{id:"a",kind:"instruction",title:"A",content:{body:"A"}},{id:"b",kind:"instruction",title:"B",content:{body:"B"}}]};
it("persists a Start-attached unfinished entrance until its output is connected",()=>{
 const next=beginCatalogEntrance(d,"studio:metadata",{x:100,y:50});const pending=next.editor_layout!.pending_entrances![0];
 expect(next.entry_points).toEqual(d.entry_points);expect(next.blocks).toEqual(d.blocks);expect(next.entry_block_id).toBe("a");
 expect(()=>beginCatalogEntrance(d,"a",{x:0,y:0})).toThrow(/Начало/);
 const moved=moveCatalogEntrance(next,pending.key,{x:200,y:100});expect(moved.editor_layout!.pending_entrances![0].position).toEqual({x:200,y:100});
 const done=completeCatalogEntrance(moved,pending.key,"b");expect(done.entry_points?.at(-1)).toMatchObject({key:pending.key,target_block_id:"b",title:"Новый вход"});
 expect(done.editor_layout?.pending_entrances).toHaveLength(0);expect(done.entry_block_id).toBe("a");expect(done.schema_version).toBe(3);
 expect(removeCatalogEntrance(next,pending.key).editor_layout?.pending_entrances).toHaveLength(0);
});
