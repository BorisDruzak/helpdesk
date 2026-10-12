import { useState } from "react";
import { Button } from "../../components/ui/button";
import {Select} from "../../components/ui/select";
import { useSession } from "../auth/session-provider";
import { useEndpointTools } from "./use-endpoint-tools";
import { ToolForm } from "./tool-form";
import { EndpointToolResult } from "./tool-result";
import { reasonText } from "./types";
import { ContextBatchPanel } from "./context-batch-panel";
import { useToolAttachment } from "./use-tool-attachment";
function Workspace({ticketId}:{ticketId:string}) {
  const state=useEndpointTools(ticketId);
  const [selected,setSelected]=useState<string|null>(null);
  const catalog=state.catalog.data;
  const attachment=useToolAttachment(ticketId,state.device);
  const tool=catalog?.items.find(t=>`${t.module_key}:${t.version}`===selected);
  return <section aria-label="Инструменты Endpoint" className="endpoint-tools-container min-w-0 space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="text-base font-semibold text-slate-950">Инструменты Endpoint</h2><p className="text-xs text-slate-500">Проверки на компьютере заявителя</p></div><Button size="sm" variant="outline" onClick={()=>void state.catalog.refetch()}>Обновить</Button></div>
    {state.catalog.isPending?<p role="status">Загружаем доступные инструменты…</p>:state.catalog.isError?<p role="alert">Не удалось получить инструменты Endpoint. {state.catalog.error.message}</p>:catalog&&!catalog.enabled?<p role="status">Рабочее пространство пока выключено</p>:<>
      <label className="block space-y-1"><span className="text-sm font-medium">Инструмент Endpoint</span><Select value={selected??""} onChange={event=>{setSelected(event.target.value||null);state.chooseRun(null);}}><option value="">Выберите инструмент…</option>{catalog?.items.map(item=><option key={`${item.module_key}:${item.version}`} value={`${item.module_key}:${item.version}`}>{item.title} · {item.version}{item.availability!=="available"?` · ${reasonText(item.reason_code)}`:""}</option>)}</Select></label>
      {!catalog?.items.length&&<p>Для этого компьютера нет опубликованных инструментов.</p>}
      {catalog?.next_cursor&&<Button variant="outline" size="sm" onClick={()=>state.setCursor(catalog.next_cursor)}>Следующая страница</Button>}
      <div className="endpoint-tools-columns grid min-w-0 gap-4"><section className="min-w-0 rounded-xl border border-border bg-white p-4" aria-label="Параметры инструмента">{tool?<ToolForm key={`${state.device}:${tool.module_key}:${tool.version}`} tool={tool} canRun={catalog?.can_run??false} pending={state.create.isPending} onRun={inputs=>state.create.mutate({tool,inputs,selectionVersion:state.selectionVersion()})}/>:<p className="text-sm text-slate-500">Выберите доступный инструмент</p>}{state.create.isError&&<p role="alert" className="mt-3 text-sm text-rose-700">{state.create.error.message}</p>}</section>
        <div className="min-w-0 rounded-xl border border-border bg-white p-4">{state.run.isError?<p role="alert">Не удалось прочитать выбранный результат. {state.run.error.message}</p>:state.selection&&state.run.isPending?<p role="status">Загружаем выбранный запуск…</p>:state.run.data?<EndpointToolResult run={state.run.data} onAttach={attachment.canAttach?attachment.attach:undefined} attaching={attachment.mutation.isPending} attachedSteps={[...new Set([...(state.run.data.attached_steps??[]),...Array.from({length:8},(_,i)=>i).filter(i=>attachment.known(state.run.data!.run_id,i))])]}/>:<p className="text-sm text-slate-500">Результат выбранной проверки появится здесь</p>}</div>
      </div>
      {attachment.mutation.isError&&<p role="alert">Не удалось приложить выбранный результат: {attachment.mutation.error.message}</p>}
      {state.device&&<ContextBatchPanel key={`${state.account}:${ticketId}:${state.device}`} ticketId={ticketId} deviceRef={state.device} canRun={catalog?.can_run??false}/>}
      <details className="rounded-xl border border-border bg-white p-3"><summary className="cursor-pointer text-sm font-medium">История запусков</summary>{state.history.isError?<p role="alert">История временно недоступна</p>:<div className="mt-3 space-y-2">{state.history.data?.items.map(run=><button className="block w-full rounded-lg border border-border p-2 text-left text-sm" type="button" key={run.run_id} onClick={()=>{state.chooseRun(run);if(run.module_key)setSelected(`${run.module_key}:${run.version}`);}}>{run.module_key??run.profile??"Диагностика"} · {new Date(run.created_at).toLocaleString("ru-RU")}</button>)}</div>}</details>
    </>}
  </section>;
}
export function EndpointToolsPanel({ticketId}:{ticketId:string}) {const {session}=useSession();return <Workspace key={`${session?.user_login??""}:${ticketId}`} ticketId={ticketId}/>;}
