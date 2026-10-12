import { useState } from "react";
import { Button } from "../../components/ui/button";
import { useSession } from "../auth/session-provider";
import { useEndpointTools } from "./use-endpoint-tools";
import { ToolForm } from "./tool-form";
import { EndpointToolResult } from "./tool-result";
import { reasonText } from "./types";
function Workspace({ticketId}:{ticketId:string}) {
  const state=useEndpointTools(ticketId);
  const [selected,setSelected]=useState<string|null>(null);
  const catalog=state.catalog.data;
  const tool=catalog?.items.find(t=>`${t.module_key}:${t.version}`===selected);
  return <section aria-label="Инструменты Endpoint" className="endpoint-tools-container min-w-0 space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="text-base font-semibold text-slate-950">Инструменты Endpoint</h2><p className="text-xs text-slate-500">Проверки на компьютере заявителя</p></div><Button size="sm" variant="outline" onClick={()=>void state.catalog.refetch()}>Обновить</Button></div>
    {state.catalog.isPending?<p role="status">Загружаем доступные инструменты…</p>:state.catalog.isError?<p role="alert">Не удалось получить инструменты Endpoint. {state.catalog.error.message}</p>:catalog&&!catalog.enabled?<p role="status">Рабочее пространство пока выключено</p>:<>
      <div className="flex flex-wrap gap-2" aria-label="Доступные инструменты">{catalog?.items.map(item=><button aria-pressed={selected===`${item.module_key}:${item.version}`} className="rounded-lg border border-border bg-white px-3 py-2 text-left text-sm text-slate-900 aria-pressed:border-brand-600 aria-pressed:bg-brand-50" type="button" key={`${item.module_key}:${item.version}`} onClick={()=>{setSelected(`${item.module_key}:${item.version}`);state.chooseRun(null);}}><span className="block font-medium">{item.title}</span><span className="text-xs text-slate-500">{item.version}{item.availability!=="available"?` · ${reasonText(item.reason_code)}`:""}</span></button>)}</div>
      {!catalog?.items.length&&<p>Для этого компьютера нет опубликованных инструментов.</p>}
      {catalog?.next_cursor&&<Button variant="outline" size="sm" onClick={()=>state.setCursor(catalog.next_cursor)}>Следующая страница</Button>}
      <div className="endpoint-tools-columns grid min-w-0 gap-4"><section className="min-w-0 rounded-xl border border-border bg-white p-4" aria-label="Параметры инструмента">{tool?<ToolForm key={`${state.device}:${tool.module_key}:${tool.version}`} tool={tool} canRun={catalog?.can_run??false} pending={state.create.isPending} onRun={inputs=>state.create.mutate({tool,inputs,selectionVersion:state.selectionVersion()})}/>:<p className="text-sm text-slate-500">Выберите доступный инструмент</p>}{state.create.isError&&<p role="alert" className="mt-3 text-sm text-rose-700">{state.create.error.message}</p>}</section>
        <div className="min-w-0 rounded-xl border border-border bg-white p-4">{state.run.isError?<p role="alert">Не удалось прочитать выбранный результат. {state.run.error.message}</p>:state.selection&&state.run.isPending?<p role="status">Загружаем выбранный запуск…</p>:state.run.data?<EndpointToolResult run={state.run.data}/>:<p className="text-sm text-slate-500">Результат выбранной проверки появится здесь</p>}</div>
      </div>
      <details className="rounded-xl border border-border bg-white p-3"><summary className="cursor-pointer text-sm font-medium">История запусков</summary>{state.history.isError?<p role="alert">История временно недоступна</p>:<div className="mt-3 space-y-2">{state.history.data?.items.map(run=><button className="block w-full rounded-lg border border-border p-2 text-left text-sm" type="button" key={run.run_id} onClick={()=>{state.chooseRun(run);if(run.module_key)setSelected(`${run.module_key}:${run.version}`);}}>{run.module_key??run.profile??"Диагностика"} · {new Date(run.created_at).toLocaleString("ru-RU")}</button>)}</div>}</details>
    </>}
  </section>;
}
export function EndpointToolsPanel({ticketId}:{ticketId:string}) {const {session}=useSession();return <Workspace key={`${session?.user_login??""}:${ticketId}`} ticketId={ticketId}/>;}
