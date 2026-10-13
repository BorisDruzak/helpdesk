import {expect,it} from "vitest";
import {catalogServices} from "./catalog-service-model";
import type {ScenarioCatalog} from "./scenario-api";
it("projects three services from one published map and keeps draft changes separate",()=>{
  const offering={full_code:"work.print",service_code:"work",public_title:"Печать"};
  const points=["Не печатает","Застряла бумага","Бледная печать"].map((title,index)=>({key:String(index),title,target_block_id:"q"}));
  const map={id:"s",category_id:null,archived:false,published_entry_points:points,entry_points:points.map((point,index)=>index===0?{...point,title:"Новое название"}:point),published_public_entry_keys:["0","1","2"]};
  const data={entries:[{offering,scenarios:[map],active_mode:"scenario",active_scenario_id:"s",requester_available:true,category_ids:[]}]} as unknown as ScenarioCatalog;
  const rows=catalogServices(data);
  expect(rows.map(row=>row.title)).toEqual(points.map(point=>point.title));
  expect(rows.every(row=>row.card.offering===offering&&row.scenario===map&&row.available)).toBe(true);
  expect(rows[0].entry?.title).toBe("Новое название");expect(rows[0].draft).toBe(true);expect(rows[1].draft).toBe(false);
});
it("does not replace a published ordinary form with a draft entrance",()=>{
  const data={entries:[{offering:{full_code:"work.print",public_title:"Печать"},scenarios:[{id:"s",archived:false,entry_points:[{key:"paper",title:"Застряла бумага"}]}],active_mode:"form",requester_available:true,category_ids:[]}]} as unknown as ScenarioCatalog;
  const rows=catalogServices(data);expect(rows).toHaveLength(2);expect(rows[0]).toMatchObject({available:true,mode:"form"});expect(rows[1]).toMatchObject({available:false,mode:"scenario",draft:true});
});
