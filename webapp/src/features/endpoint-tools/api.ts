import { SupportBootstrapApiError } from "../queues/api";
import type { ToolBatch,ToolCatalog,ToolRun } from "./types";
const base=(ticket:string)=>`/api/web/support/tickets/${encodeURIComponent(ticket)}/endpoint-tools`;
async function request<T>(url:string,init:RequestInit={},schema?:string):Promise<T> {
  const response=await fetch(url,{credentials:"same-origin",...init});
  const payload=await response.json().catch(()=>null);
  if(!response.ok || payload?.status!=="success") throw new SupportBootstrapApiError(payload?.error??"Не удалось связаться с Endpoint",response.status,payload?.error_code);
  if(schema && payload.data?.schema_version!==schema) throw new SupportBootstrapApiError("Формат ответа Endpoint не поддерживается",502,"endpoint_schema_not_supported");
  return payload.data as T;
}
const json=(body:unknown)=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export function getCatalog(ticket:string,cursor:string|null,signal?:AbortSignal) {return request<ToolCatalog>(`${base(ticket)}${cursor?`?cursor=${encodeURIComponent(cursor)}`:""}`,{signal},"endpoint_tool_catalog_v1");}
export function getRuns(ticket:string,signal?:AbortSignal) {return request<{schema_version:"endpoint_tool_run_history_v1";items:ToolRun[]}>(`${base(ticket)}/runs`,{signal},"endpoint_tool_run_history_v1");}
export async function getRun(ticket:string,runId:string,signal?:AbortSignal) {
  const run=await request<ToolRun>(`${base(ticket)}/runs/${encodeURIComponent(runId)}`,{signal},"endpoint_tool_run_v1");
  if(run.run_id!==runId || run.ticket_id!==ticket) throw new SupportBootstrapApiError("Выбранный запуск не совпадает с ответом",502,"endpoint_invalid_projection");
  return run;
}
export async function createRun(ticket:string,module_key:string,version:string,inputs:Readonly<Record<string,string|number>>,caller_key:string,expected_device_ref:string) {
  const run=await request<ToolRun>(`${base(ticket)}/runs`,json({schema_version:"endpoint_tool_run_create_v1",module_key,version,inputs,caller_key,expected_device_ref}),"endpoint_tool_run_v1");
  if(run.ticket_id!==ticket || run.device_ref!==expected_device_ref || run.module_key!==module_key || run.version!==version) throw new SupportBootstrapApiError("Ответ не совпадает с отправленной проверкой",502,"endpoint_invalid_projection");
  return run;
}
function validateBatch(result:ToolBatch,ticket:string,batch:string,device?:string) {
  if(result.batch_id!==batch || result.ticket_id!==ticket || result.runs.length!==6 || new Set(result.runs.map(r=>r.run_id)).size!==6 || result.runs.some(r=>r.ticket_id!==ticket || r.batch_id!==batch || device!=null&&r.device_ref!==device)) throw new SupportBootstrapApiError("Ответ общего сбора не совпадает с запросом",502,"endpoint_invalid_projection");
  return result;
}
export async function createBatch(ticket:string,caller_key:string,expected_device_ref:string) {
  const result=await request<ToolBatch>(`${base(ticket)}/collections`,json({schema_version:"endpoint_tool_batch_create_v1",caller_key,expected_device_ref}),"endpoint_tool_batch_v1");
  return validateBatch(result,ticket,result.batch_id,expected_device_ref);
}
export async function getBatch(ticket:string,batch:string,signal?:AbortSignal) {
  const result=await request<ToolBatch>(`${base(ticket)}/collections/${encodeURIComponent(batch)}`,{signal},"endpoint_tool_batch_v1");
  return validateBatch(result,ticket,batch);
}
export async function attachSelectedToolResult(ticket:string,run:string,step:number) {
  const result=await request<{schema_version:"endpoint_tool_attachment_v1";run_id:string;step_sequence:number}>(`${base(ticket)}/runs/${encodeURIComponent(run)}/passport-evidence`,json({schema_version:"endpoint_tool_attach_v1",step_sequence:step}),"endpoint_tool_attachment_v1");
  if(result.run_id!==run || result.step_sequence!==step) throw new SupportBootstrapApiError("Подтверждение не совпадает с выбранным результатом",502,"endpoint_invalid_projection");
  return result;
}

// Save before dispatch. An uncertain response keeps the same request identity on reload.
export function pendingToolKey(account:string,ticket:string,device:string,intent:unknown) {
  if(!account || !ticket || !device) throw new Error("Не определён пользователь или устройство");
  const storage=`endpoint-tool-intent-v1:${JSON.stringify([account,ticket,device,intent])}`;
  try {
    const saved=sessionStorage.getItem(storage);
    if(saved) {if(!/^[0-9a-f-]{36}$/.test(saved)) throw new Error("Invalid request identity");return {storage,key:saved};}
    const key=crypto.randomUUID();sessionStorage.setItem(storage,key);return {storage,key};
  } catch {throw new Error("Не удалось сохранить запрос для безопасного повтора. Проверьте хранилище браузера.");}
}
export function acceptedToolKey(intent:{storage:string;key:string}) {try {if(sessionStorage.getItem(intent.storage)===intent.key) sessionStorage.removeItem(intent.storage);} catch { /* Accepted identity remains safe to replay. */ }}
