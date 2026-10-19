import type { SupportQueuePayload } from "../../../features/queues/api";
import { mapWorkspaceTicketItems } from "../../../features/queues/support-workspace-mappers";
import "./simple-support.css";

export type SimpleQueueFilter = "open" | "new" | "mine" | "waiting" | "completed";
export type SimpleSupportQueueProps = {
  queue?: SupportQueuePayload; actorId?: string; canWork: boolean; filter: SimpleQueueFilter;
  search: string; loading?: boolean; error?: boolean; pending?: boolean; compact?: boolean;
  selectedTicketId?: string | null; activeQueueId?: string | null;
  onFilterChange: (filter: SimpleQueueFilter) => void; onSearchChange: (value: string) => void;
  onOpenTicket: (id: string) => void; onTakeTicket: (id: string) => void; onAdvanced: () => void;
  onQueueChange?: (id: string | null) => void;
};
const FILTERS: Array<[SimpleQueueFilter, string]> = [["open", "Открытые"], ["new", "Новые"], ["mine", "Мои"], ["waiting", "Ожидают ответа"], ["completed", "Завершённые"]];

export function SimpleSupportQueue(props: SimpleSupportQueueProps) {
  const { queue, compact, selectedTicketId, actorId, canWork, pending, onOpenTicket, onTakeTicket } = props;
  const tickets = mapWorkspaceTicketItems(queue, selectedTicketId ?? null);
  return <section className={`simple-queue${compact ? " simple-queue--compact" : ""}`} aria-label={compact ? "Моя рабочая очередь" : "Очередь обращений"}>
    <div className="simple-queue__heading"><div><p className="simple-eyebrow">Рабочее место / заявки</p><h2>{compact ? "Моя рабочая очередь" : "Очередь обращений"}</h2>
      {!compact ? <p className="simple-muted">Выберите обращение, посмотрите приоритет и возьмите его в работу.</p> : null}</div>
      {!compact ? <button className="simple-button" onClick={props.onAdvanced} type="button">Дополнительно</button> : null}</div>
    <div className="simple-queue__toolbar">
      <div className="simple-tabs" role="tablist" aria-label="Фильтры обращений">{FILTERS.map(([id, label]) => <button type="button" role="tab" aria-selected={props.filter === id} key={id} onClick={() => props.onFilterChange(id)}>{label}</button>)}</div>
      <input aria-label="Поиск обращений" placeholder="Поиск по номеру, теме, сотруднику" type="search" value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} />
      {props.onQueueChange && (queue?.summary.queue_counts?.length ?? 0) > 0 ? <select aria-label="Очередь" value={props.activeQueueId ?? ""} onChange={(event) => props.onQueueChange?.(event.target.value || null)}>
        <option value="">Все очереди</option>{queue?.summary.queue_counts?.map((item) => <option key={item.id ?? item.code} value={item.code ?? String(item.id)}>{item.name ?? item.code}</option>)}</select> : null}
    </div>
    {props.error ? <p role="alert" className="simple-notice">{queue ? "Не удалось обновить очередь. Показаны ранее загруженные обращения." : "Не удалось загрузить очередь. Обновите список."}</p> : null}
    {props.loading && !queue ? <p role="status" className="simple-empty">Загружаем обращения…</p> : null}
    {!props.loading && !props.error && tickets.length === 0 ? <p className="simple-empty">В этой очереди пока нет обращений. Измените фильтр или поиск.</p> : null}
    {compact ? <div className="simple-queue__cards">{tickets.map((ticket) => <button className="simple-queue__card" aria-current={ticket.active ? "true" : undefined} type="button" key={ticket.id} onClick={() => onOpenTicket(ticket.id)}>
      <span className="simple-queue__card-top"><b>{ticket.code}</b><span className="simple-badge" data-tone={ticket.statusTone}>{ticket.statusLabel}</span></span>
      <strong>{ticket.subject}</strong><span className="simple-muted">{ticket.requester}</span>
      <span className="simple-queue__card-top"><span className="simple-badge" data-tone={ticket.priorityTone}>{ticket.priority}</span><span className="simple-muted">{ticket.nextDueLabel}</span>{ticket.unread ? <span aria-label="Есть непрочитанные сообщения" className="simple-unread" /> : null}</span>
    </button>)}</div> : tickets.length ? <div className="simple-queue__table-wrap"><table><thead><tr>{["Номер", "Тема", "Сотрудник", "Приоритет", "Статус", "Исполнитель", "SLA", "Сообщения", "Действие"].map((label) => <th key={label}>{label}</th>)}</tr></thead>
      <tbody>{tickets.map((ticket, index) => {
        const raw = queue!.tickets[index];
        const take = canWork && raw.take_in_work?.allowed === true && !raw.assignee_id && ["new", "queued"].includes(raw.status);
        const blocked = !raw.assignee_id && ["new", "queued"].includes(raw.status) && raw.take_in_work?.allowed === false;
        const blockedLabel = raw.take_in_work?.reason_code === "ASSIGNEE_NOT_IN_QUEUE" ? "Не состоите в очереди" : raw.take_in_work?.reason_code === "ASSIGNEE_CAPACITY_REACHED" ? "Лимит нагрузки" : "Взятие недоступно";
        return <tr key={ticket.id} aria-selected={ticket.active}><td><button className="simple-link" type="button" onClick={() => onOpenTicket(ticket.id)}>{ticket.code}</button></td>
          <td><strong>{ticket.subject}</strong></td><td>{ticket.requester}</td><td><span className="simple-badge" data-tone={ticket.priorityTone}>{ticket.priority}</span></td>
          <td><span className="simple-badge" data-tone={ticket.statusTone}>{ticket.statusLabel}</span></td><td>{ticket.assigneeLabel}</td>
          <td><span className={ticket.slaRisk ? "simple-risk" : ""}>{ticket.nextDueLabel}</span></td><td>{raw.unread_user_messages ? <span aria-label={`${raw.unread_user_messages} непрочитанных`} className="simple-badge" data-tone="brand">{raw.unread_user_messages}</span> : "—"}</td>
          <td><button className={`simple-button${take ? " simple-button--primary" : ""}`} type="button" disabled={take && pending} onClick={() => take ? onTakeTicket(ticket.id) : onOpenTicket(ticket.id)}>{take ? "Взять в работу" : raw.assignee_id === actorId ? "Открыть" : "Просмотр"}</button>{blocked ? <span className="simple-queue__blocked" title={raw.take_in_work?.reason ?? undefined}>{blockedLabel}</span> : null}</td></tr>;
      })}</tbody></table></div> : null}
    {!compact ? <p className="simple-queue__footer simple-muted">Обращений в списке: {queue?.summary.visible_count ?? tickets.length}. Обновление каждые 15 секунд.</p> : null}
  </section>;
}
