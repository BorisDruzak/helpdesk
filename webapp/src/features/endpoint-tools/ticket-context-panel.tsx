import {useState,type ReactNode} from "react";
import type {SupportTicketInventoryContext} from "../queues/api";
export function TicketContextPanel({requester,device,agent,observer,criticalSummary,children}:{requester:ReactNode;device:ReactNode;agent:ReactNode;observer:ReactNode;criticalSummary:ReactNode;children?:ReactNode}) {
  const [open,setOpen]=useState(false);
  return <div className="space-y-3"><div data-context-layer="requester">{requester}</div><div data-context-layer="device">{device}</div><div data-context-layer="agent">{agent}</div>{children}<section className="rounded-xl border border-border p-3" data-context-layer="observer">{criticalSummary}<details onToggle={event=>setOpen(event.currentTarget.open)}><summary aria-expanded={open} className="mt-2 cursor-pointer text-sm font-semibold">Observer · подробности</summary>{open&&<div className="mt-3">{observer}</div>}</details></section></div>;
}
export function EndpointAgentContext({inventoryContext}:{inventoryContext?:SupportTicketInventoryContext|null}) {
  const device=inventoryContext?.context?.device;
  const online=device&&!device.retired_at?device.online:null;
  return <section className="rounded-xl border border-white/10 p-4" aria-label="Агент Endpoint"><h3 className="font-semibold">Агент Endpoint</h3><dl className="mt-3 space-y-2 text-sm"><div><dt className="text-xs text-slate-500">Соединение</dt><dd>{online===null?"Нет данных":online?"В сети":"Не в сети"}</dd></div><div><dt className="text-xs text-slate-500">Последняя связь</dt><dd>{device?.last_seen_at?new Date(device.last_seen_at).toLocaleString("ru-RU"):"Нет данных"}</dd></div><div><dt className="text-xs text-slate-500">Версия агента</dt><dd>Нет данных</dd></div><div><dt className="text-xs text-slate-500">Версия загрузчика</dt><dd>Нет данных</dd></div></dl></section>;
}
