import {expect,it} from "vitest";
import {catalogServices} from "./catalog-service-model";
import type {ScenarioCatalog} from "./scenario-api";
it("shows one service containing all named entrances and separates draft from published data",()=>{
 const offering={full_code:"work.print",service_code:"work",public_title:"Печать"};
 const points=["Не печатает","Застряла бумага","Бледная печать"].map((title,index)=>({key:String(index),title,target_block_id:"q"}));
 const map={id:"s",title:"Печать",status:"published",category_id:null,archived:false,published_entry_points:points,entry_points:points.map((point,index)=>index===0?{...point,title:"Новое название"}:point)};
 const data={entries:[{offering,scenarios:[map],active_mode:"scenario",active_scenario_id:"s",requester_available:true,category_ids:[]}]} as unknown as ScenarioCatalog;
 const rows=catalogServices(data);
 expect(rows).toHaveLength(1);expect(rows[0].key).toBe(offering.full_code);
 expect(rows[0].title).toBe("Печать");expect(rows[0].draft).toBe(true);
 expect(rows[0].scenario?.published_entry_points?.[0].title).toBe("Не печатает");
 expect(rows[0].scenario?.entry_points?.[0].title).toBe("Новое название");
});
it("preserves current availability while a legacy service has only a draft map",()=>{
 const data={entries:[{offering:{full_code:"work.print",public_title:"Печать"},scenarios:[{id:"s",title:"Печать",archived:false,entry_points:[{key:"paper",title:"Застряла бумага"}]}],active_mode:"form",requester_available:true,category_ids:[]}]} as unknown as ScenarioCatalog;
 const rows=catalogServices(data);expect(rows).toHaveLength(1);expect(rows[0]).toMatchObject({available:true,draft:true});
 expect(rows[0].card.active_mode).toBe("form");
});
it("keeps an unconverted form as one existing service",()=>{
 const data={entries:[{offering:{full_code:"net.vpn",public_title:"VPN"},scenarios:[],active_mode:"form",requester_available:true,category_ids:[]}]} as unknown as ScenarioCatalog;
 expect(catalogServices(data)).toMatchObject([{key:"net.vpn",mode:"form",available:true,draft:false}]);
});
