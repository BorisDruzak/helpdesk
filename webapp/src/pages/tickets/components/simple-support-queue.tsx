import type { ReactNode } from "react";
import { ArrowUpRight, Menu } from "lucide-react";
import type { SupportQueuePayload } from "../../../features/queues/api";
import { mapWorkspaceTicketItems } from "../../../features/queues/support-workspace-mappers";
import "./simple-support.css";

export type SimpleQueueFilter = "open" | "new" | "mine" | "waiting" | "completed" | "sla_risk";
export type SimpleSupportQueueProps = {
  queue?: SupportQueuePayload; actorId?: string; canWork: boolean; filter: SimpleQueueFilter;
  search: string; loading?: boolean; error?: boolean; pending?: boolean; compact?: boolean;
  collapsed?: boolean; onToggleCollapsed?: () => void; selectedTicketId?: string | null; activeQueueId?: string | null;
  onFilterChange: (filter: SimpleQueueFilter) => void; onSearchChange: (value: string) => void;
  onOpenTicket: (id: string) => void; onTakeTicket: (id: string) => void; onAdvanced: () => void;
  onOpenQueue?: () => void;
  onReturnToTicket?: () => void; returnTicketLabel?: string;
  view?: "tickets" | "actions"; onViewChange?: (view: "tickets" | "actions") => void; actionCenter?: ReactNode;
  onQueueChange?: (id: string | null) => void;
};
const FILTERS: Array<[SimpleQueueFilter, string]> = [["open", "Открытые"], ["new", "Новые"], ["mine", "Мои"], ["waiting", "Ожидают ответа"], ["completed", "Завершённые"]];

export function SimpleSupportQueue(props: SimpleSupportQueueProps) {
  const { queue, compact, selectedTicketId, actorId, canWork, pending, onOpenTicket, onTakeTicket } = props;
  const actionsView = !compact && props.view === "actions";
  const tickets = mapWorkspaceTicketItems(queue, selectedTicketId ?? null);
  const compactControls = <div className="simple-queue__compact-controls">
    {props.onToggleCollapsed ? <button className="simple-button" aria-label={props.collapsed ? "Показать список заявок" : "Скрыть список заявок"} aria-expanded={!props.collapsed} title={props.collapsed ? "Раскрыть очередь рядом с тикетом" : "Свернуть очередь до миниатюр"} onClick={props.onToggleCollapsed} type="button"><Menu size={17} aria-hidden /></button> : null}
    {props.onOpenQueue ? <button className="simple-button simple-queue__full" aria-label="Открыть всю очередь" title="Открыть всю очередь" onClick={props.onOpenQueue} type="button"><ArrowUpRight size={17} aria-hidden />{!props.collapsed ? <span>Вся очередь</span> : null}</button> : null}
  </div>;
  if (compact && props.collapsed) return <section className="simple-queue simple-queue--compact simple-queue--collapsed" aria-label="Список заявок">
    {compactControls}<span className="simple-queue__mini-count">{tickets.length}</span>
    <div className="simple-queue__miniatures">{tickets.map(ticket=><button type="button" key={ticket.id} className="simple-queue__miniature" aria-current={ticket.active ? "true" : undefined} aria-label={`${ticket.code} · ${ticket.statusLabel} · SLA: ${ticket.nextDueLabel}${ticket.unread ? " · Есть непрочитанные сообщения" : ""}`} title={`${ticket.subject}\n${ticket.statusLabel}\nSLA: ${ticket.nextDueLabel}`} onClick={()=>onOpenTicket(ticket.id)}>
      <strong><span>{ticket.code}</span>{ticket.unread ? <i className="simple-unread" aria-hidden /> : null}</strong>
      <span className="simple-badge" data-tone={ticket.statusTone}>{ticket.statusLabel}</span>
      <span className="simple-queue__mini-sla" data-risk={ticket.slaRisk} data-overdue={ticket.nextDueLabel.startsWith("Просрочено")} data-empty={ticket.nextDueLabel === "Нет срока"}>{ticket.slaRisk ? ticket.nextDueLabel.startsWith("Просрочено") ? "SLA нарушен" : "SLA скоро срок" : ticket.nextDueLabel === "Нет срока" ? "SLA: нет данных" : "SLA в норме"}</span>
    </button>)}</div>
  </section>;
  return <section className={`simple-queue${compact ? " simple-queue--compact" : ""}`} aria-label={compact ? "Моя рабочая очередь" : "Очередь обращений"}>
    {compact ? compactControls : null}
    {!compact ? <div className="simple-queue__heading simple-queue__heading--unified"><div><p className="simple-eyebrow">Рабочее место / заявки</p><button className="simple-link simple-queue__return" type="button" disabled={!props.onReturnToTicket} title={props.onReturnToTicket ? "Вернуться к открытому обращению без потери ответа" : "Сначала откройте обращение из списка"} onClick={props.onReturnToTicket}>← Вернуться к обращению{props.returnTicketLabel ? ` ${props.returnTicketLabel}` : ""}</button><h2>Очередь обращений</h2>
      {!compact && props.onViewChange ? <div className="simple-tabs simple-queue__views" role="tablist" aria-label="Вид очереди">{([["tickets", "Обращения"], ["actions", "Действия"]] as const).map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={(props.view ?? "tickets") === id} onClick={() => props.onViewChange?.(id)}>{label}</button>)}</div> : null}</div>
      {!compact ? <input className="simple-queue__shared-search" aria-label="Поиск обращений" placeholder="Номер, тема, сотрудник, услуга или устройство" type="search" value={props.search} onChange={event => props.onSearchChange(event.target.value)} /> : null}
      <details className="simple-queue__more"><summary>Ещё</summary><button className="simple-button" onClick={props.onAdvanced} type="button">Расширенные инструменты очереди</button></details></div> : null}
    {queue?.queue_mode === "unified" ? <p className="simple-queue__mode">Единая очередь · все операторы поддержки</p> : null}
    <div className="simple-queue__toolbar" hidden={actionsView && (queue?.queue_mode === "unified" || !props.onQueueChange || !(queue?.summary.queue_counts?.length))}>
      {!actionsView ? <div className="simple-tabs simple-queue__filters" role="tablist" aria-label="Фильтры обращений">{FILTERS.map(([id, label]) => <button type="button" role="tab" data-filter={id} aria-selected={props.filter === id} key={id} onClick={() => props.onFilterChange(id)}>{label}</button>)}</div> : null}
      {compact ? <input aria-label="Поиск обращений" placeholder="Поиск по номеру, теме, сотруднику" type="search" value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} /> : null}
      {queue?.queue_mode !== "unified" && props.onQueueChange && (queue?.summary.queue_counts?.length ?? 0) > 0 ? <select aria-label="Очередь" value={props.activeQueueId ?? ""} onChange={(event) => props.onQueueChange?.(event.target.value || null)}>
        <option value="">Все очереди</option>{queue?.summary.queue_counts?.map((item) => <option key={item.id ?? item.code} value={item.code ?? String(item.id)}>{item.name ?? item.code}</option>)}</select> : null}
    </div>
    {actionsView ? props.actionCenter : <>
    {props.error ? <p role="alert" className="simple-notice">{queue ? "Не удалось обновить очередь. Показаны ранее загруженные обращения." : "Не удалось загрузить очередь. Обновите список."}</p> : null}
    {props.loading && !queue ? <p role="status" className="simple-empty">Загружаем обращения…</p> : null}
    {!props.loading && !props.error && tickets.length === 0 ? <p className="simple-empty">В этой очереди пока нет обращений. Измените фильтр или поиск.</p> : null}
    {compact ? <><p className="simple-queue__count">Рабочий список · {tickets.length}</p><div className="simple-queue__cards">{tickets.map((ticket) => <button className="simple-queue__card" aria-current={ticket.active ? "true" : undefined} type="button" key={ticket.id} onClick={() => onOpenTicket(ticket.id)}>
      <span className="simple-queue__card-top"><b>{ticket.code}</b><span className="simple-badge" data-tone={ticket.statusTone}>{ticket.statusLabel}</span></span>
      <strong>{ticket.subject}</strong><span className="simple-muted">{ticket.requester}</span>{ticket.hiddenFromWorkspace ? <span className="simple-badge">Скрыт</span> : null}{ticket.archivedAt ? <span className="simple-badge">Архив</span> : null}
      <span className="simple-queue__card-top"><span className="simple-badge" data-tone={ticket.priorityTone}>{ticket.priority}</span><span className={ticket.slaRisk ? "simple-risk" : "simple-muted"}>{ticket.nextDueLabel}</span>{ticket.unread ? <span aria-label="Есть непрочитанные сообщения" className="simple-unread" /> : null}</span>
    </button>)}</div></> : tickets.length ? <div className="simple-queue__table-wrap"><table><thead><tr>{["Номер", "Тема", "Сотрудник", "Приоритет", "Статус", "Исполнитель", "SLA", "Сообщения", "Действие"].map((label) => <th key={label}>{label}</th>)}</tr></thead>
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
    </>}
  </section>;
}
