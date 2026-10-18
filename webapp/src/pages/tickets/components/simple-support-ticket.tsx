import { useState, type ReactNode } from "react";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import type { SupportWorkspaceContext, SupportWorkspaceSelectedTicket } from "../../../features/queues/support-workspace-model";

export type SimpleSupportTicketProps = {
  detail: SupportTicketDetailPayload; ticket?: SupportWorkspaceSelectedTicket | null; context?: SupportWorkspaceContext | null;
  actorId?: string; isAdmin?: boolean; canWork: boolean; canAssign?: boolean; pending?: boolean; error?: string | null;
  onStatus: (value: string) => void; onResolve: () => void; onAdvanced: (mode?: "passport" | "tools" | "sla" | "ticket") => void;
  onQueue: () => void; onManage?: (kind: "queue" | "priority") => void; conversation: ReactNode;
};
export function SimpleSupportTicket(props: SimpleSupportTicketProps) {
  const { detail, context, ticket, actorId, isAdmin, canWork, onStatus, onAdvanced } = props;
  const raw = detail.ticket;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const mine = Boolean(actorId && raw.assignee_id === actorId);
  const other = Boolean(raw.assignee_id && !mine);
  const allowed = (status: string) => canWork && detail.actions.status_options.some((option) => option.value === status);
  let primary: { label: string; hint: string; run: () => void } | null = null;
  if (["new", "queued", "assigned"].includes(raw.status) && (!other || isAdmin) && (raw.assignee_id || props.canAssign !== false) && allowed("in_progress")) {
    primary = { label: raw.assignee_id ? "Начать работу" : "Взять в работу", hint: "После успешного перехода в работу станет доступна переписка.", run: () => onStatus("in_progress") };
  } else if (["in_progress", "waiting_on_user", "waiting_on_internal_team", "waiting_on_vendor"].includes(raw.status) && (mine || isAdmin)) {
    if (raw.status !== "in_progress" && allowed("in_progress")) primary = { label: "Возобновить работу", hint: "Обращение вернётся в работу. Ожидание ответа завершится.", run: () => onStatus("in_progress") };
    else if (allowed("resolved")) primary = { label: "Решить обращение", hint: "Укажите результат. После решения сотрудник сможет подтвердить его, если это требует политика.", run: props.onResolve };
  } else if (raw.status === "waiting_on_approval") {
    primary = { label: "Проверить согласование", hint: "Проверьте ожидаемые решения в центре согласований.", run: () => { window.location.href = "/app/support/approvals"; } };
  } else if (raw.status === "resolved" && allowed("closed")) {
    primary = { label: "Закрыть обращение", hint: "Сервер проверит подтверждение сотрудника и политику закрытия.", run: () => onStatus("closed") };
  } else if (raw.status === "closed" && allowed("in_progress")) {
    primary = { label: "Переоткрыть обращение", hint: "Обращение вернётся в работу с сохранением переписки и истории.", run: () => onStatus("in_progress") };
  }
  const sla = ticket?.timers.find((item) => item.key === "resolution") ?? ticket?.timers.find((item) => item.key === "first_response");
  return <div className="simple-ticket">
    <main className="simple-ticket__main">
      <header className="simple-ticket__header">
        <div className="simple-ticket__title"><button className="simple-link" type="button" onClick={props.onQueue}>← Вся очередь</button><p className="simple-eyebrow">{raw.ticket_code ?? raw.ticket_id} · Рабочая карточка</p>
          <h2>{raw.title}</h2><div className="simple-inline"><span className="simple-badge" data-tone={ticket?.priorityTone ?? "warning"}>{raw.priority_class ?? raw.priority ?? "P3"}</span><span className="simple-badge" data-tone={ticket?.statusTone ?? "info"}>{raw.status_label}</span><span className="simple-muted">{ticket?.createdLabel}</span></div></div>
        <div className="simple-ticket__actions">{primary ? <button className="simple-button simple-button--primary" title={primary.hint} disabled={props.pending} onClick={primary.run} type="button">{props.pending ? "Выполняем…" : primary.label}</button> : null}
          <details className="simple-menu"><summary className="simple-button">Действия ▾</summary><div>
            {raw.status === "in_progress" && allowed("waiting_on_user") && (mine || isAdmin) ? <button type="button" onClick={() => onStatus("waiting_on_user")}>Ожидать ответа сотрудника</button> : null}
            {props.onManage && canWork ? <><button type="button" onClick={() => props.onManage?.("queue")}>Изменить очередь</button><button type="button" onClick={() => props.onManage?.("priority")}>Изменить приоритет</button></> : null}
            <button type="button" onClick={() => onAdvanced("tools")}>Диагностика</button><button type="button" onClick={() => onAdvanced("ticket")}>Дополнительные возможности</button>
          </div></details>
          <button className="simple-button simple-ticket__details-toggle" type="button" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((value) => !value)}>Сведения</button>
        </div>
      </header>
      {props.error ? <p role="alert" className="simple-notice simple-risk">{props.error}</p> : null}
      {!raw.assignee_id && props.canAssign === false ? <p className="simple-notice">Для взятия обращения в работу нужно право назначения исполнителя. Пока доступен просмотр.</p> : null}
      {!raw.assignee_id && props.canAssign === false ? null : other && !isAdmin || !raw.assignee_id || ["new", "queued", "assigned"].includes(raw.status) ? <p className="simple-notice">{other ? "Назначено другому оператору. Доступен просмотр; изменение исполнителя выполняется отдельно с проверкой прав." : "Чтобы начать переписку и обработку, нажмите «" + (raw.assignee_id ? "Начать работу" : "Взять в работу") + "». Дождитесь успешного ответа сервера."}</p> : primary ? <p className="simple-action-hint simple-muted">{primary.hint}</p> : raw.status === "resolved" ? <p className="simple-notice">Решение отправлено сотруднику. Ожидается подтверждение по действующей политике.</p> : raw.status === "closed" ? <p className="simple-muted">Обращение закрыто. Переписка и история доступны для просмотра.</p> : null}
      <div className="simple-ticket__content">
        <details className="simple-panel simple-ticket__description" open><summary>Описание и ответы сотрудника</summary><p>{raw.description || "Описание не указано"}</p>
          {detail.request_form?.rows.length ? <dl className="simple-facts">{detail.request_form.rows.map((row) => <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl> : null}
        </details>
        {props.conversation}
      </div>
    </main>
    <aside className="simple-ticket__facts" data-open={detailsOpen} aria-label="Сведения об обращении">
      <section className="simple-panel"><h3>Заявитель</h3><dl className="simple-facts">
        <div><dt>ФИО</dt><dd>{context?.requester.name ?? raw.requester_display_name ?? "Не указан"}</dd></div>
        <div><dt>Телефон</dt><dd>{context?.requester.phone ?? "Не указан"}</dd></div><div><dt>Email</dt><dd>{context?.requester.email ?? "Не указан"}</dd></div>
        <div><dt>Подразделение</dt><dd>{context?.requester.department ?? "Не указано"}</dd></div><div><dt>Место</dt><dd>{context?.requester.location ?? "Не указано"}</dd></div>
      </dl></section>
      <section className="simple-panel"><h3>Обработка</h3><dl className="simple-facts"><div><dt>Статус</dt><dd>{raw.status_label}</dd></div><div><dt>Исполнитель</dt><dd>{mine ? "Вы" : ticket?.assigneeLabel ?? raw.assignee_id ?? "Не назначен"}</dd></div><div><dt>Очередь</dt><dd>{raw.queue.name ?? raw.queue.code ?? "Не указана"}</dd></div><div><dt>Приоритет</dt><dd>{raw.priority_class ?? raw.priority ?? "P3"}</dd></div></dl></section>
      <section className="simple-panel"><h3>SLA · Срок решения</h3><p className="simple-sla" data-risk={sla?.status === "breached" || sla?.status === "at_risk"}>{sla?.remainingLabel ?? "Не рассчитан"}</p><p className="simple-muted">{sla?.status === "paused" ? "Приостановлен по действующей политике" : "По действующей политике"}</p></section>
      <section className="simple-panel"><h3>Устройство</h3><p>{context?.device.id ? context.device.hostname : "Не указано"}</p><p className="simple-muted">{context?.device.id ? context.device.onlineLabel : "Без агента — обычную заявку можно обработать."}</p></section>
    </aside>
  </div>;
}
