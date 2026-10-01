import {
  startTransition,
} from "react";
import {
  Badge,
} from "../../../components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  SearchField,
} from "../../../components/ui/search-field";
import {
  type SupportQueueScope,
} from "../../../features/queues/api";
import {
  getTicketStatusPresentation,
} from "../../../features/tickets/status-presentation";
import {
  cn,
} from "../../../shared/ui/cn";
import {
  formatDateTime,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketQueueSidebar({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { navigate, ticketId, scope, setScope, statusFilter, setStatusFilter, queueSearch, setQueueSearch, queueQuery, queue } = controller;
  if (!ticketId) return null;
  return (<Card className="w-full overflow-hidden xl:sticky xl:top-[8.5rem] xl:self-start">
    <CardHeader>
      <CardTitle>Очередь</CardTitle>
      <CardDescription>
        Фиксированное рабочее окно со статусами, поиском и реальной очередью тикетов.
      </CardDescription>
    </CardHeader>
    <CardContent className="flex h-[min(68vh,58rem)] min-h-[30rem] flex-col gap-5 overflow-hidden">
      <div className="grid grid-cols-2 gap-2">
        {(queue?.summary.scope_counts ?? []).map((item) => (
          <button
            key={item.value}
            className={cn(
              "rounded-pill px-3 py-2 text-sm font-medium transition-colors",
              scope === item.value
                ? "bg-brand-600 text-white"
                : "bg-surface-subtle text-slate-600 hover:bg-brand-50 hover:text-brand-800",
            )}
            onClick={() => {
              startTransition(() => {
                setScope(item.value as SupportQueueScope);
              });
            }}
            type="button"
          >
            {item.label} ({item.count})
          </button>
        ))}
      </div>

      <SearchField
        onChange={(event) => setQueueSearch(event.target.value)}
        placeholder="Код, тема, инициатор"
        value={queueSearch}
      />

      <div className="space-y-2">
        {(queue?.summary.status_counts ?? []).map((item) => (
          <button
            key={item.value}
            className={cn(
              "flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors",
              statusFilter === item.value
                ? "border-brand-200 bg-brand-50 text-brand-900"
                : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white",
            )}
            onClick={() => {
              startTransition(() => {
                setStatusFilter(item.value);
              });
            }}
            type="button"
          >
            <span className="font-medium">{item.label}</span>
            <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
              {item.count}
            </span>
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {queueQuery.isLoading ? (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
            Загружаем очередь...
          </div>
        ) : null}

        {queue && queue.tickets.length === 0 ? (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
            По текущим фильтрам тикеты не найдены.
          </div>
        ) : null}

        {queue?.tickets.map((queueTicket) => {
          const active = queueTicket.ticket_id === ticketId;
          const presentation = getTicketStatusPresentation({
            status: queueTicket.status,
            statusLabel: queueTicket.status_label,
            requesterStatusLabel: queueTicket.requester_status_label,
            nextActionOwner: queueTicket.next_action_owner,
            statusReason: queueTicket.status_reason,
          });

          return (
            <button
              key={queueTicket.ticket_id}
              className={cn(
                "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                active
                  ? "border-brand-200 bg-brand-50"
                  : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
              )}
              onClick={() => navigate(`/app/tickets/${queueTicket.ticket_id}`)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">
                    {queueTicket.ticket_code ?? queueTicket.ticket_id}
                  </p>
                  <p className="mt-2 text-base font-semibold text-slate-950">{queueTicket.title}</p>
                </div>
                <Badge tone={presentation.tone}>{presentation.statusLabel}</Badge>
              </div>
              <p className="mt-3 text-sm text-slate-500">
                {queueTicket.requester_display_name ?? "Инициатор не указан"}
              </p>
              <p className="mt-2 text-xs text-slate-400">
                {formatDateTime(queueTicket.updated_at ?? queueTicket.created_at)}
                {queueTicket.unread_user_messages > 0
                  ? ` • ${queueTicket.unread_user_messages} непрочит.`
                  : ""}
              </p>
              <p className="mt-2 text-xs font-medium text-slate-500">
                {presentation.stageLabel} • Ход: {presentation.ownerLabel}
                {presentation.requesterStatusLabel !== "Не указан" ? ` • ${presentation.requesterStatusLabel}` : ""}
              </p>
            </button>
          );
        })}
      </div>
    </CardContent>
  </Card>);
}