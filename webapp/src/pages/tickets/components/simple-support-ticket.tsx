import { useId, useRef, useState, type ReactNode } from "react";
import { ChevronDown, X } from "lucide-react";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import type { SupportWorkspaceContext, SupportWorkspaceSelectedTicket } from "../../../features/queues/support-workspace-model";

export type SimpleSupportTicketProps = {
  detail: SupportTicketDetailPayload; ticket?: SupportWorkspaceSelectedTicket | null; context?: SupportWorkspaceContext | null;
  actorId?: string; isAdmin?: boolean; canWork: boolean; canAssign?: boolean; pending?: boolean; error?: string | null;
  onStatus: (value: string) => void; onResolve: () => void; onAdvanced: (mode?: "passport" | "tools" | "sla" | "ticket") => void;
  inspector?: ReactNode; unifiedQueue?: boolean; onQueue: () => void; onManage?: (kind: "queue" | "priority") => void; conversation: ReactNode;
};
export function SimpleSupportTicket(props: SimpleSupportTicketProps) {
  const { detail, context, ticket, actorId, isAdmin, canWork, onStatus, onAdvanced } = props;
  const raw = detail.ticket;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const descriptionRef = useRef<HTMLDialogElement>(null);
  const descriptionTitle = useId();
  const mine = Boolean(actorId && raw.assignee_id === actorId);
  const other = Boolean(raw.assignee_id && !mine);
  const allowed = (status: string) => canWork && detail.actions.status_options.some((option) => option.value === status);
  const takeAllowed = detail.actions.take_in_work?.allowed === true;
  const needsStart = ["new", "queued", "assigned"].includes(raw.status);
  const takeReason = needsStart && !takeAllowed ? detail.actions.take_in_work?.reason
    || (props.canAssign === false ? "Для взятия обращения нужно право назначения исполнителя." : "Обновите обращение, чтобы проверить доступность начала работы.") : null;
  let primary: { label: string; hint: string; run: () => void } | null = null;
  if (needsStart && takeAllowed && (!other || isAdmin) && (raw.assignee_id || props.canAssign !== false) && allowed("in_progress")) {
    primary = { label: raw.assignee_id ? "Начать работу" : "Взять в работу", hint: "После успешного перехода в работу станет доступна переписка.", run: () => onStatus("in_progress") };
  } else if (["in_progress", "waiting_on_user", "waiting_on_internal_team", "waiting_on_vendor"].includes(raw.status) && (mine || isAdmin)) {
    if (raw.status !== "in_progress" && takeAllowed && allowed("in_progress")) primary = { label: "Возобновить работу", hint: "Обращение вернётся в работу. Ожидание ответа завершится.", run: () => onStatus("in_progress") };
    else if (allowed("resolved")) primary = { label: "Решить обращение", hint: "Укажите результат. После решения сотрудник сможет подтвердить его, если это требует политика.", run: props.onResolve };
  } else if (raw.status === "waiting_on_approval") {
    primary = { label: "Проверить согласование", hint: "Проверьте ожидаемые решения в центре согласований.", run: () => { window.location.href = "/app/support/approvals"; } };
  } else if (raw.status === "resolved" && allowed("closed")) {
    primary = { label: "Закрыть обращение", hint: "Сервер проверит подтверждение сотрудника и политику закрытия.", run: () => onStatus("closed") };
  } else if (raw.status === "closed" && takeAllowed && allowed("in_progress")) {
    primary = { label: "Переоткрыть обращение", hint: "Обращение вернётся в работу с сохранением переписки и истории.", run: () => onStatus("in_progress") };
  }
  const sla = ticket?.timers.find((item) => item.key === "resolution") ?? ticket?.timers.find((item) => item.key === "first_response");
  const rows = detail.request_form?.rows ?? [];
  const comparable = (value: string) => value.replace(/[\s?:]+/g, "").trim();
  const descriptionIsAnswers = rows.length > 0 && comparable(raw.description ?? "") === comparable(rows.map((row) => `${row.label}: ${row.value}`).join(" "));
  return <div className="simple-ticket">
    <main className="simple-ticket__main">
      <header className="simple-ticket__header">
        <div className="simple-ticket__title"><button className="simple-link" type="button" onClick={props.onQueue}>← Вся очередь</button><p className="simple-eyebrow">{raw.ticket_code ?? raw.ticket_id} · Рабочая карточка</p>
          <h2>{raw.title}</h2><div className="simple-inline"><span className="simple-badge" data-tone={ticket?.priorityTone ?? "warning"}>{raw.priority_class ?? raw.priority ?? "P3"}</span><span className="simple-badge" data-tone={ticket?.statusTone ?? "info"}>{raw.status_label}</span><span className="simple-muted">{ticket?.createdLabel}</span></div></div>
        <div className="simple-ticket__actions">{primary ? <button className="simple-button simple-button--primary" title={primary.hint} disabled={props.pending} onClick={primary.run} type="button">{props.pending ? "Выполняем…" : primary.label}</button> : null}
          <details className="simple-menu"><summary className="simple-button">Действия ▾</summary><div>
            {raw.status === "in_progress" && allowed("waiting_on_user") && (mine || isAdmin) ? <button type="button" onClick={() => onStatus("waiting_on_user")}>Ожидать ответа сотрудника</button> : null}
            {props.onManage && canWork ? <>{!props.unifiedQueue ? <button type="button" onClick={() => props.onManage?.("queue")}>Изменить очередь</button> : null}<button type="button" onClick={() => props.onManage?.("priority")}>Изменить приоритет</button></> : null}
            <button type="button" onClick={() => onAdvanced("tools")}>Диагностика</button><button type="button" onClick={() => onAdvanced("ticket")}>Дополнительные возможности</button>
          </div></details>
          <button className="simple-button simple-ticket__details-toggle" type="button" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((value) => !value)}>Сведения</button>
        </div>
      </header>
      {props.error ? <p role="alert" className="simple-notice simple-risk">{props.error}</p> : null}
      {takeReason ? <p className="simple-notice simple-take-reason">{takeReason}</p> : other && !isAdmin ? <p className="simple-notice">Назначено другому оператору. Доступен просмотр; изменение исполнителя выполняется отдельно с проверкой прав.</p> : raw.status === "resolved" ? <p className="simple-notice">Решение отправлено сотруднику. Ожидается подтверждение по действующей политике.</p> : raw.status === "closed" ? <p className="simple-muted">Обращение закрыто. Переписка и история доступны для просмотра.</p> : null}
      <div className="simple-ticket__content">
        <button className="simple-description-toggle" type="button" onClick={() => descriptionRef.current?.showModal()} aria-haspopup="dialog">Описание и ответы сотрудника{rows.length ? ` · ${rows.length}` : ""}<ChevronDown size={17} aria-hidden /></button>
        <dialog className="simple-description-dialog" ref={descriptionRef} aria-labelledby={descriptionTitle} onClick={(event) => { if (event.target === event.currentTarget) descriptionRef.current?.close(); }}>
          <header><h3 id={descriptionTitle}>Описание и ответы сотрудника</h3><form method="dialog"><button type="submit" className="simple-button" aria-label="Закрыть описание"><X size={18} aria-hidden /></button></form></header>
          {!descriptionIsAnswers ? <p>{raw.description || "Описание не указано"}</p> : null}
          {rows.length ? <dl className="simple-facts">{rows.map((row) => <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl> : null}
        </dialog>
        {props.conversation}
      </div>
    </main>
    <aside className="simple-ticket__facts" data-open={detailsOpen} aria-label="Сведения об обращении">
      <button className="simple-button simple-ticket__facts-close" type="button" onClick={() => setDetailsOpen(false)}>Закрыть сведения <X size={15} aria-hidden /></button>
      {props.inspector ?? <><section className="simple-panel"><h3>Заявитель</h3><dl className="simple-facts">
        <div><dt>ФИО</dt><dd>{context?.requester.name ?? raw.requester_display_name ?? "Не указан"}</dd></div>
        <div><dt>Телефон</dt><dd>{context?.requester.phone ?? "Не указан"}</dd></div><div><dt>Email</dt><dd>{context?.requester.email ?? "Не указан"}</dd></div>
        <div><dt>Подразделение</dt><dd>{context?.requester.department ?? "Не указано"}</dd></div><div><dt>Место</dt><dd>{context?.requester.location ?? "Не указано"}</dd></div>
      </dl></section>
      <section className="simple-panel"><h3>Обработка</h3><dl className="simple-facts"><div><dt>Статус</dt><dd>{raw.status_label}</dd></div><div><dt>Исполнитель</dt><dd>{mine ? "Вы" : ticket?.assigneeLabel ?? raw.assignee_id ?? "Не назначен"}</dd></div><div><dt>Очередь</dt><dd>{raw.queue.name ?? raw.queue.code ?? "Не указана"}</dd></div><div><dt>Приоритет</dt><dd>{raw.priority_class ?? raw.priority ?? "P3"}</dd></div></dl></section>
      <section className="simple-panel"><h3>SLA · Срок решения</h3><p className="simple-sla" data-risk={sla?.status === "breached" || sla?.status === "at_risk"}>{sla?.remainingLabel ?? "Не рассчитан"}</p><p className="simple-muted">{sla?.status === "paused" ? "Приостановлен по действующей политике" : "По действующей политике"}</p></section>
      <section className="simple-panel"><h3>Устройство</h3><p>{context?.device.id ? context.device.hostname : "Не указано"}</p><p className="simple-muted">{context?.device.id ? context.device.onlineLabel : "Без агента — обычную заявку можно обработать."}</p></section>
      </>}
    </aside>
  </div>;
}
