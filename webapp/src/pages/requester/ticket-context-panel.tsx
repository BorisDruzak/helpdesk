import { Clock3, Monitor, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { formatRussianDateTime } from "../../components/ui-page";
import type { RequesterSlaTimer, RequesterTicketHandling } from "../../features/requester/types";

function remaining(seconds: number) {
  const minutes = Math.max(1, Math.ceil(Math.abs(seconds) / 60));
  return minutes >= 60 ? `${Math.floor(minutes / 60)} ч ${minutes % 60} мин` : `${minutes} мин`;
}

export function requesterTimerLabel(timer: RequesterSlaTimer, resolution = false) {
  const completed = timer.status === "completed";
  return completed ? resolution ? "Решение подготовлено" : "Ответ получен"
    : timer.status === "paused" ? `На паузе${typeof timer.remaining_seconds === "number" ? ` · ${timer.remaining_seconds < 0 ? "просрочено на" : "осталось"} ${remaining(timer.remaining_seconds)}` : ""}`
      : timer.status === "canceled" ? "Обращение отменено"
        : timer.status === "stopped" ? "Отсчёт завершён"
          : timer.status === "unknown" ? "Срок не назначен"
            : timer.status === "breached" && typeof timer.remaining_seconds === "number" && timer.remaining_seconds >= 0 ? "Срок был нарушен"
            : typeof timer.remaining_seconds === "number" ? `${timer.remaining_seconds < 0 ? "Просрочено на" : "Осталось"} ${remaining(timer.remaining_seconds)}` : "Срок не назначен";
}

export function RequesterTicketContextBrief({ handling }: { handling: RequesterTicketHandling }) {
  return <>
    {handling.sla?.first_response ? <span className="mt-1 block text-xs font-normal text-slate-600">Первый ответ: {requesterTimerLabel(handling.sla.first_response)}</span> : null}
    {handling.sla?.resolution ? <span className="mt-1 block text-xs font-semibold text-slate-800">Решение: {requesterTimerLabel(handling.sla.resolution, true)}</span> : null}
    {handling.device ? <span className="mt-1 block truncate text-xs font-normal text-slate-600">{handling.device.state === "none" ? "Устройство не указано" : handling.device.display_name || "Компьютер по обращению"}</span> : null}
  </>;
}

function SlaTarget({ timer, resolution }: { timer: RequesterSlaTimer; resolution?: boolean }) {
  const completed = timer.status === "completed";
  const label = requesterTimerLabel(timer, resolution);
  const late = timer.status === "breached" || timer.status === "paused" && typeof timer.remaining_seconds === "number" && timer.remaining_seconds < 0 || completed && timer.completed_within_target === false;
  const due = completed ? timer.completed_at : timer.effective_due_at || timer.due_at;
  return <div className="min-w-0">
    <h3 className="text-xs font-semibold text-slate-500">{resolution ? "Решение" : "Первый ответ"}</h3>
    <p className={`mt-1 text-sm font-semibold ${late ? "text-red-700" : timer.status === "paused" || timer.status === "at_risk" ? "text-amber-800" : "text-slate-900"}`}>{label}</p>
    {due && !["canceled", "stopped"].includes(timer.status || "") ? <p className="mt-1 text-xs text-slate-600">{completed ? "Получено" : timer.status === "paused" ? "Плановый срок" : "До"}: {formatRussianDateTime(due)}</p> : null}
    {completed && timer.completed_within_target === false ? <p className="mt-1 text-xs text-red-700">Срок был нарушен</p> : null}
  </div>;
}

export function RequesterTicketContext({ handling }: { handling: RequesterTicketHandling }) {
  const device = handling.device;
  const next = handling.next_action_owner === "requester" ? "Нужен ваш ответ" : handling.next_action_owner === "support" ? "Действие за поддержкой" : null;
  const presence = device?.presence === "online" ? "В сети" : device?.presence === "offline" ? "Не в сети" : device?.presence === "retired" ? "Выведено из эксплуатации" : "Состояние недоступно";
  return <section aria-label="Сведения об обращении" className="rounded-panel border border-slate-200 bg-white p-3 xl:p-4">
    <h2 className="text-sm font-semibold text-slate-950">Обработка обращения</h2>
    <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-1">
      {handling.assignee ? <div className="min-w-0"><p className="flex items-center gap-1 text-xs text-slate-500"><UserRound className="h-3.5 w-3.5" />Ваш специалист</p><p className="mt-1 break-words text-sm font-semibold text-slate-900">{handling.assignee.assigned ? handling.assignee.display_name || "Специалист поддержки" : "Специалист ещё не назначен"}</p></div> : null}
      {next ? <div><p className="text-xs text-slate-500">Следующий шаг</p><p className={`mt-1 text-sm font-semibold ${handling.next_action_owner === "requester" ? "text-amber-800" : "text-slate-700"}`}>{next}</p></div> : null}
    </div>
    {handling.team ? <p className="mt-2 text-xs text-slate-600">{handling.team}</p> : null}
    {handling.sla?.first_response || handling.sla?.resolution ? <section aria-label="Сроки обращения" className="mt-4 border-t border-slate-100 pt-3"><h2 className="flex items-center gap-1.5 text-sm font-semibold text-slate-950"><Clock3 className="h-4 w-4" />Сроки · SLA</h2><div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-1">{handling.sla.first_response ? <SlaTarget timer={handling.sla.first_response} /> : null}{handling.sla.resolution ? <SlaTarget timer={handling.sla.resolution} resolution /> : null}</div></section> : null}
    {device ? <section className="mt-4 border-t border-slate-100 pt-3"><h2 className="flex items-center gap-1.5 text-sm font-semibold text-slate-950"><Monitor className="h-4 w-4" />Устройство</h2>
      {device.state === "none" ? <><p className="mt-2 text-sm text-slate-700">Устройство не указано</p><p className="mt-1 text-xs text-slate-500">Поддержка может решить обращение без привязанного компьютера.</p></> : <><p className="mt-2 break-words text-sm font-semibold text-slate-900">{device.display_name || "Компьютер по обращению"}</p><p className={`mt-1 text-xs ${device.presence === "online" ? "text-brand-700" : "text-slate-500"}`}>{presence}</p>{device.last_seen_at ? <p className="mt-1 text-xs text-slate-500">Последняя связь: {formatRussianDateTime(device.last_seen_at)}</p> : null}{device.details_path?.startsWith("/app/requester/devices/") ? <Link className="mt-2 inline-flex min-h-8 items-center text-xs font-semibold text-brand-700 underline" to={device.details_path}>Открыть устройство</Link> : null}</>}
    </section> : null}
  </section>;
}
