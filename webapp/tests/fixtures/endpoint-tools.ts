import type {Page} from "playwright/test";
import type {ToolBatch,ToolCatalog,ToolItem,ToolRun} from "../../src/features/endpoint-tools/types";
import type {EndpointContextSnapshot} from "../../src/features/admin/endpoint-context-types";
import {endpointDeviceId} from "./endpoint-context";
const now="2026-10-12T10:00:00Z";
const item:ToolItem={module_key:"helpdesk.dns",version:"1.0.0",title:"Проверка DNS",availability:"available",reason_code:null,
 input_controls:[{name:"target",value_type:"string",minimum:null,maximum:null,enum_values:null}],fixed_settings:[{step_id:"dns",parameter:"family",value:"ipv4"}],capabilities:["dns.resolve"]};
const catalog:ToolCatalog={schema_version:"endpoint_tool_catalog_v1",ticket_id:"ticket-1",device_ref:endpointDeviceId,enabled:true,can_run:true,observed_at:now,items:[item,{...item,module_key:"helpdesk.ping",title:"Проверка связи",availability:"unknown",reason_code:"agent_version_unsupported"}],next_cursor:null,profiles:["baseline_v1","health_v1","network_v1","inventory_v1","session_v1","diagnostic_v1"]};
function snapshot(profile:string):EndpointContextSnapshot|null {
 const common={id:crypto.randomUUID(),collected_at:now,semantic_hash:null,warnings:[]};
 switch(profile){
  case "baseline_v1":return {...common,profile,sections:{system:{platform:"linux",distribution:"ALT",architecture:"x86_64"},hardware:{manufacturer:"Fixture",model:"Fixture PC",cpu_model:"Fixture CPU",memory_bytes:8589934592},storage:[],interfaces:[],software:[]}};
  case "health_v1":return {...common,profile,sections:{resources:{uptime_seconds:100,load_1m:0.2,free_bytes:1073741824},services:[]}};
  case "inventory_v1":return {...common,profile,sections:{system:{hostname:"fixture",platform:"linux"},hardware:{model:"Fixture PC"},memory:{module_count:0,modules:[]},storage:{physical_devices:[]},interfaces:[]}};
  case "session_v1":return {...common,profile,sections:{current_user_login:null,interactive_session_present:false}};
  default:return null;
 }
}
function run(id:string,inputs:Record<string,string|number>,module_key="helpdesk.dns"):ToolRun {
 return {schema_version:"endpoint_tool_run_v1",run_id:id,ticket_id:"ticket-1",device_ref:endpointDeviceId,kind:"module",module_key,version:"1.0.0",profile:null,inputs,status:"queued",remote_ref:id,safe_result:null,error_code:null,created_at:now,batch_id:null,attached_steps:[]};
}
function completed(r:ToolRun):ToolRun {
 return {...r,status:"succeeded",safe_result:{schema_version:"endpoint_module_operation_v1",operation_id:r.remote_ref!,device_id:r.device_ref,module_key:r.module_key!,version:r.version!,status:"succeeded",created_at:now,deadline_at:"2026-10-12T10:30:00Z",completed_at:now,expected_step_count:1,steps:[{sequence:0,capability:"dns.resolve",status:"succeeded",error_code:null,safe_result:{schema_version:"dns_resolve_result_v1",target:String(r.inputs.target),canonical_name:null,addresses:[{address:"203.0.113.7",family:"ipv4"}],address_count:1,status:"succeeded",error_code:null,collected_at:now}}]}};
}
export async function installEndpointToolsFixture(page:Page) {
 const runs=new Map<string,ToolRun>(); const pollCounts=new Map<string,number>(); const receipts:Array<Record<string,unknown>>=[];const attached=new Set<string>();let batch:ToolBatch|null=null;let batchReads=0;
 await page.route("**/api/web/notifications/unread_count",route=>route.fulfill({json:{status:"ok",unread_count:0}}));
 await page.route("**/api/web/support/tickets/*/timeline?*",route=>route.fulfill({json:{status:"success",data:{ticket_id:"ticket-1",filter:"all",items:[]}}}));
 await page.route("**/api/web/support/tickets/*/read",route=>route.fulfill({json:{status:"success",data:{ticket_id:"ticket-1",last_read_event_id:1}}}));
 await page.route("**/api/web/support/bootstrap",async route=>{
   const response=await route.fetch();const payload=await response.json();payload.data.features.push("endpoint_tools_workspace");await route.fulfill({response,json:payload});
 });
 await page.route(/\/api\/web\/support\/tickets\/ticket-1\/endpoint-tools(?:[/?]|$)/,async route=>{
  const request=route.request();const path=new URL(request.url()).pathname;let data:unknown;
  if(path.endsWith("/endpoint-tools"))data=catalog;
  else if(path.endsWith("/passport-evidence")) {
   const id=path.split("/").at(-2)!;const body=request.postDataJSON();attached.add(`${id}:${body.step_sequence}`);
   const current=runs.get(id);if(current)runs.set(id,{...current,attached_steps:[body.step_sequence]});
   data={schema_version:"endpoint_tool_attachment_v1",run_id:id,step_sequence:body.step_sequence,passport_evidence_id:1,evidence_id:"fixture-evidence"};
  } else if(path.endsWith("/runs")&&request.method()==="POST"){
   const body=request.postDataJSON();receipts.push(body);const id=crypto.randomUUID();const created=run(id,body.inputs,body.module_key);runs.set(id,created);data=created;
  } else if(path.endsWith("/runs"))data={schema_version:"endpoint_tool_run_history_v1",items:[...runs.values()]};
  else if(path.includes("/runs/")){
   const id=path.split("/").at(-1)!;const current=runs.get(id)!;const count=(pollCounts.get(id)??0)+1;pollCounts.set(id,count);
   data=current.status==="queued"&&count>1?completed(current):current;if(count>1)runs.set(id,data as ToolRun);
  } else if(path.endsWith("/collections")&&request.method()==="POST"){
   const id=crypto.randomUUID();batch={schema_version:"endpoint_tool_batch_v1",batch_id:id,ticket_id:"ticket-1",status:"running",runs:catalog.profiles.map((profile,i)=>({...run(crypto.randomUUID(),{}),kind:i===5?"diagnostic":"context_collection",module_key:null,version:null,profile:i===5?null:profile,batch_id:id,status:"queued"}))};data=batch;
  } else if(path.includes("/collections/")){
   batchReads++;if(batchReads>1&&batch)batch={...batch,status:"partial",runs:batch.runs.map((r,i)=>({...r,status:i===2?"failed":"succeeded",error_code:i===2?"network_failed":null,safe_result:i===5?{profile:"diagnostic_v1",reason:"Диагностика по обращению",collected_at:now,warnings:[],processes:[],log_excerpt:null}:i===2?null:snapshot(r.profile!)}))};data=batch;
  }
  await route.fulfill({json:{status:"success",data}});
 });
 return {catalog,runs,receipts,attached,pollCounts};
}
