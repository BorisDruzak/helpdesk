import { useRef,useState } from "react";
import { useMutation,useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { useSession } from "../auth/session-provider";
import { acceptedToolKey,createBatch,getBatch,pendingToolKey } from "./api";
import { EndpointToolResult } from "./tool-result";
import { PROFILE_LABELS,STATUS_LABELS,type ToolBatch } from "./types";
import { useVisiblePage } from "./use-endpoint-tools";
import { useToolAttachment } from "./use-tool-attachment";
const BATCH_LABELS={running:"Собираем контекст",succeeded:"Контекст собран",partial:"Частичный результат",failed:"Контекст не удалось собрать"};
export function ContextBatchPanel({ticketId,deviceRef,canRun,initialBatch}:{ticketId:string;deviceRef:string;canRun:boolean;initialBatch?:ToolBatch}) {
  const {session,status}=useSession();const account=session?.user_login??"";const visible=useVisiblePage();
  const [accepted,setAccepted]=useState<ToolBatch|undefined>(initialBatch);const [selected,setSelected]=useState<string|null>(null);
  const current=useRef({account,ticketId,deviceRef});current.current={account,ticketId,deviceRef};
  const create=useMutation({mutationKey:["endpoint-tools",account,ticketId,deviceRef,"collection"],mutationFn:async()=>{
    const scope={account,ticketId,deviceRef};const identity=pendingToolKey(account,ticketId,deviceRef,"six-profile-context-v1");
    const batch=await createBatch(ticketId,identity.key);acceptedToolKey(identity);return {batch,scope};
  },onSuccess:({batch,scope})=>{if(current.current.account===scope.account&&current.current.ticketId===scope.ticketId&&current.current.deviceRef===scope.deviceRef){setAccepted(batch);setSelected(null);}}});
  const query=useQuery({queryKey:["endpoint-tools",account,ticketId,deviceRef,"collection",accepted?.batch_id],queryFn:({signal})=>getBatch(ticketId,accepted!.batch_id,signal),
    enabled:!!account&&status!=="anonymous"&&visible&&!!accepted,initialData:accepted,staleTime:accepted?.status==="running"?0:60000,retry:false,
    refetchInterval:q=>q.state.data?.status==="running"?2000:false,refetchIntervalInBackground:false});
  const batch=query.data??accepted;const run=batch?.runs.find(r=>r.run_id===selected);const attachment=useToolAttachment(ticketId,deviceRef);
  return <section aria-label="Общий сбор" className="space-y-3 border-t border-border pt-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">Общий сбор</h3><p className="text-xs text-slate-500">Основной контекст, состояние системы, сеть, оборудование, сеанс и диагностика</p></div><Button size="sm" disabled={!canRun||create.isPending||batch?.status==="running"} onClick={()=>create.mutate()}>{create.isPending?"Отправляем…":"Собрать общий контекст"}</Button></div>
    {create.isError&&<p role="alert" className="text-sm text-rose-700">{create.error.message}</p>}
    {query.isError&&<p role="alert" className="text-sm text-amber-800">Обновление состояния временно недоступно. Показан последний полученный результат.</p>}
    {batch&&<><p role="status" className="text-sm font-semibold">{BATCH_LABELS[batch.status]}</p><div className="grid gap-2">{batch.runs.map(r=><button aria-label={`Выбрать результат: ${PROFILE_LABELS[r.profile??"diagnostic_v1"]??"Контекст"}`} aria-pressed={selected===r.run_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-white p-3 text-left text-sm aria-pressed:border-brand-600" type="button" key={r.run_id} onClick={()=>setSelected(r.run_id)}><span>{PROFILE_LABELS[r.profile??"diagnostic_v1"]??"Контекст"}</span><span className={r.status==="failed"||r.status==="expired"?"text-rose-700":"text-slate-500"}>{STATUS_LABELS[r.status]}</span></button>)}</div></>}
    {run&&<div className="rounded-xl border border-border bg-white p-4"><EndpointToolResult run={run} onAttach={attachment.canAttach?attachment.attach:undefined} attaching={attachment.mutation.isPending} attachedSteps={[...new Set([...(run.attached_steps??[]),...Array.from({length:8},(_,i)=>i).filter(i=>attachment.known(run.run_id,i))])]}/></div>}
    {attachment.mutation.isError&&<p role="alert">Не удалось приложить выбранный результат: {attachment.mutation.error.message}</p>}
  </section>;
}
