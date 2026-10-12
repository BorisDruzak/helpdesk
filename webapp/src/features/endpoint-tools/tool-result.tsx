import type { ReactNode } from "react";
import type { EndpointContextSnapshot } from "../admin/endpoint-context-types";
import type { EndpointPrimitiveResult } from "./endpoint-module-types.generated";
import { fixedValue } from "./tool-inputs";
import { STATUS_LABELS,activeStatus,reasonText,type ToolRun } from "./types";
type Fact=readonly [string,ReactNode];
const state=(value:string|null|undefined)=>({running:"Работает",stopped:"Остановлено",paused:"Приостановлено",failed:"Ошибка",not_found:"Не найдено",unknown:"Неизвестно",up:"Подключён",down:"Отключён",automatic:"Автоматически",manual:"Вручную",disabled:"Отключено",ready:"Готов",offline:"Не в сети",error:"Ошибка",missing:"Отсутствует"} as Record<string,string>)[value??""]??value??"Нет данных";
const yes=(value:boolean)=>value?"Да":"Нет";
const bytes=(value:number|null|undefined)=>value==null?"Нет данных":`${(value/1024**3).toLocaleString("ru-RU",{maximumFractionDigits:2})} ГБ`;
const date=(value:string|null|undefined)=>value && !Number.isNaN(Date.parse(value))?new Date(value).toLocaleString("ru-RU"):"Нет данных";
export function ResultFacts({rows}:{rows:readonly Fact[]}) {return <dl className="grid min-w-0 gap-3">{rows.map(([label,value],i)=><div className="min-w-0 rounded-lg bg-surface-subtle p-3" key={`${label}:${i}`}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-900">{value??"Нет данных"}</dd></div>)}</dl>;}
export function primitiveFacts(r:EndpointPrimitiveResult):Fact[] {
  switch(r.schema_version) {
    case "dns_resolve_result_v1":return [["Адрес",r.target],["Каноническое имя",r.canonical_name],["Найденные адреса",r.addresses?.length?r.addresses.map(a=>`${a.address} · ${fixedValue(a.family)}`).join("\n"):"Список пуст"]];
    case "network_ping_result_v1":return [["Адрес",r.target],["IP-адрес",r.resolved_ip],["Узел отвечает",yes(r.reachable)],["Отправлено / получено",`${r.transmitted} / ${r.received}`],["Потери пакетов",`${r.packet_loss_percent}%`],["Задержка мин. / сред. / макс., мс",[r.min_ms,r.avg_ms,r.max_ms].map(v=>v??"Нет данных").join(" / ")]];
    case "tcp_connect_result_v1":return [["Адрес",r.target],["Порт",r.port],["IP-адрес",r.resolved_ip],["Соединение установлено",yes(r.reachable)],["Задержка, мс",r.latency_ms]];
    case "route_get_result_v1":return [["Адрес",r.target],["Порт",r.port],["IP-адрес",r.resolved_ip],["Исходный адрес",r.source_ip],["Интерфейс",r.interface_name],["Метод","Определение через UDP-сокет"]];
    case "adapter_list_result_v1":return [["Всего / подключено",`${r.adapter_count} / ${r.up_count}`],...(r.adapters??[]).map(a=>[a.name,`${state(a.state)} · ${a.ipv4_addresses?.join(", ")||"Нет IPv4"} · ${a.ipv6_addresses?.join(", ")||"Нет IPv6"} · ${a.speed_mbps} Мбит/с`] as Fact)];
    case "service_status_result_v1":return [["Служба",fixedValue(r.service_key)],["Установлена",yes(r.installed)],["Состояние",state(r.state)],["Запуск",state(r.start_mode)]];
    case "system_resource_snapshot_result_v1":return [["Время работы, сек",r.uptime_seconds],["CPU, %",r.cpu_percent],["Память всего",bytes(r.memory_total_bytes)],["Память доступна",bytes(r.memory_available_bytes)],["Свободно на системном диске",bytes(r.system_drive_free_bytes)]];
    case "process_list_result_v1":return [["Процессов",r.process_count],...(r.processes??[]).map(p=>[`${p.name} · PID ${p.pid}`,`${state(p.state)} · CPU ${p.cpu_percent??"Нет данных"}% · ${bytes(p.memory_bytes)}`] as Fact)];
    case "process_find_result_v1":return [["Найден",yes(r.present)],["Совпадений",r.process_count],...(r.matches??[]).map(p=>[`${p.name} · PID ${p.pid}`,`${state(p.state)} · ${bytes(p.memory_bytes)}`] as Fact)];
    case "service_list_result_v1":return (r.services??[]).length?(r.services??[]).map(s=>[s.display_name,`${state(s.state)} · ${state(s.startup_type)} · Установлена: ${yes(s.installed)}`] as Fact):[["Службы","Список пуст"]];
    case "service_status_v2_result_v1":return r.service?[["Служба",r.service.display_name],["Установлена",yes(r.service.installed)],["Состояние",state(r.service.state)],["Запуск",state(r.service.startup_type)]]:[["Служба","Нет данных"]];
    case "printer_list_result_v1":return (r.printers??[]).length?(r.printers??[]).map(p=>[p.name,`${state(p.state)} · ${p.driver_name??"Нет данных о драйвере"}${p.default?" · По умолчанию":""}`] as Fact):[["Принтеры","Список пуст"]];
    case "printer_status_result_v1":return [["Принтер существует",yes(r.exists)],["Состояние",state(r.state)],["Не в сети",yes(r.offline)],["Приостановлен",yes(r.paused)],["Ошибка",yes(r.error)]];
    case "printer_queue_summary_result_v1":return [["Заданий",r.job_count],["В очереди",r.queued_count],["Печатается",r.printing_count],["Приостановлено",r.paused_count],["С ошибкой",r.error_count],["Самое старое задание, сек",r.oldest_job_age_seconds]];
    case "software_list_result_v1":return (r.software??[]).length?(r.software??[]).map(s=>[s.name,`${s.version??"Нет версии"} · ${s.publisher??"Издатель не указан"}`] as Fact):[["Программы","Список пуст"]];
    case "software_find_result_v1":return [["Программа найдена",yes(r.present)],...(r.matches??[]).map(s=>[s.name,`${s.version??"Нет версии"} · ${s.publisher??"Издатель не указан"}`] as Fact)];
    case "filesystem_free_space_result_v1":return (r.volumes??[]).length?(r.volumes??[]).map(v=>[v.volume_key,`Свободно ${bytes(v.free_bytes)} из ${bytes(v.total_bytes)} · ${v.filesystem_type}`] as Fact):[["Диски","Список пуст"]];
    case "filesystem_path_exists_result_v1":return [["Расположение",fixedValue(r.path_key)],["Существует",yes(r.exists)],["Тип",state(r.kind)]];
    case "filesystem_file_metadata_result_v1":return [["Расположение",fixedValue(r.path_key)],["Существует",yes(r.exists)],["Размер, байт",r.size],["Изменён",date(r.modified_at)],["Версия",r.version]];
    case "eventlog_query_result_v1":case "eventlog_recent_errors_result_v1":return [["Событий",r.event_count],...(r.events??[]).map(e=>[`${e.provider} · ${e.event_id}`,`${fixedValue(e.severity)} · ${date(e.timestamp)} · ${e.message_code}`] as Fact)];
    default:return [["Формат","Результат не поддерживается"]];
  }
}
function contextFacts(snapshot:EndpointContextSnapshot):Fact[] {
  const s=snapshot.sections;
  switch(snapshot.profile) {
    case "baseline_v1": {const v=snapshot.sections;return [["ОС",v.system.distribution],["Модель",v.hardware.model],["CPU",v.hardware.cpu_model],["Память",bytes(v.hardware.memory_bytes)],["Диски",v.storage.map(d=>`${d.model} · ${bytes(d.size_bytes)}`).join("\n")||"Список пуст"],["Программы",v.software.map(x=>`${x.name} ${x.version}`).join("\n")||"Список пуст"]];}
    case "inventory_v1": {const v=snapshot.sections;return [["Устройство",v.system.hostname],["ОС",[v.system.os_name,v.system.os_version].filter(Boolean).join(" ")],["Модель",v.hardware.model],["CPU",v.hardware.cpu_model],["Память",bytes(v.memory.total_bytes)],["Сетевые интерфейсы",v.interfaces.map(x=>`${x.name} · ${[...x.ipv4,...x.ipv6].join(", ")}`).join("\n")||"Список пуст"]];}
    case "health_v1": {const v=snapshot.sections;return [["Время работы, сек",v.resources.uptime_seconds],["Нагрузка за минуту",v.resources.load_1m],["Свободно на диске",bytes(v.resources.free_bytes)],...v.services.map(x=>[x.name,state(x.status)] as Fact)];}
    case "network_v1": {const v=snapshot.sections;return [["Маршрут по умолчанию",v.default_route.gateway],["Интерфейс маршрута",v.default_route.interface],["Интерфейсы",v.interfaces.map(x=>`${x.name} · ${x.addresses.join(", ")}`).join("\n")||"Список пуст"]];}
    case "session_v1":return [["Пользователь",snapshot.sections.current_user_login],["Интерактивный сеанс",yes(snapshot.sections.interactive_session_present)]];
    default:void s;return [];
  }
}
export function EndpointToolResult({run,onAttach,attaching=false,attachedSteps=[]}:{run:ToolRun;onAttach?:(runId:string,step:number)=>void;attaching?:boolean;attachedSteps?:readonly number[]}) {
  const result=run.safe_result;
  return <section aria-label="Выбранный результат" className="min-w-0 space-y-3"><div><h3 className="font-semibold text-slate-950">Результат проверки</h3><p className="mt-1 text-sm">{STATUS_LABELS[run.status]}</p><p className="break-words text-xs text-slate-500">Endpoint · {run.module_key??run.profile??"Диагностика"}{run.version?` · ${run.version}`:""}</p><p className="text-xs text-slate-500">Запуск: {date(run.created_at)}</p>{Object.keys(run.inputs).length>0&&<p className="break-words text-xs text-slate-500">Параметры запуска: {Object.entries(run.inputs).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>}</div>
    {run.error_code&&<p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{reasonText(run.error_code)}</p>}
    {!result?<p className="text-sm text-slate-500">{activeStatus(run.status)?"Ожидаем результат Endpoint. Проверка ещё не завершена.":run.status==="expired"?"Результат не получен до окончания срока ожидания.":"Сохранённый результат отсутствует. Запустите новую проверку."}</p>:
      "schema_version" in result&&result.schema_version==="endpoint_module_operation_v1"?<div className="space-y-4">{result.steps.map(step=><section key={step.sequence} className="space-y-3 rounded-xl border border-border p-3"><h4 className="text-sm font-semibold">{step.capability} · {STATUS_LABELS[step.status]}</h4>{step.safe_result?<><p className="text-xs text-slate-500">Собрано: {date(step.safe_result.collected_at)}</p>{step.safe_result.status==="failed"&&<p className="text-sm text-rose-700">Проверка завершена с ошибкой</p>}<ResultFacts rows={primitiveFacts(step.safe_result)}/></>:<p className="text-sm text-slate-500">Результат шага пока недоступен</p>}{onAttach&&<button type="button" className="button-base w-full border border-border p-2 text-sm" disabled={attaching||!step.safe_result||!["succeeded","failed"].includes(step.status)||attachedSteps.includes(step.sequence)} onClick={()=>onAttach(run.run_id,step.sequence)}>{attachedSteps.includes(step.sequence)?"В паспорте":"Приложить к паспорту"}</button>}</section>)}</div>:
      "profile" in result?<><p className="text-xs text-slate-500">Собрано: {date(result.collected_at)}</p>{result.profile==="diagnostic_v1"?<ResultFacts rows={[["Причина",result.reason],["Процессы",result.processes.length?result.processes.map(p=>`${p.name} · ${state(p.state)}`).join("\n"):"Список пуст"],["Предупреждения",result.warnings.length?result.warnings.join(" · "):"Нет"],["Журнал",result.log_excerpt??"Нет данных"]]}/>:<ResultFacts rows={contextFacts(result)}/>} {onAttach&&<button type="button" className="button-base w-full border border-border p-2 text-sm" disabled={attaching||activeStatus(run.status)||attachedSteps.includes(0)} onClick={()=>onAttach(run.run_id,0)}>{attachedSteps.includes(0)?"В паспорте":"Приложить к паспорту"}</button>}</>:<p role="alert">Формат результата не поддерживается</p>}
    {!result&&onAttach&&<button type="button" className="button-base w-full border border-border p-2 text-sm" disabled>{attachedSteps.includes(0)?"В паспорте":"Приложить к паспорту"}</button>}
  </section>;
}
