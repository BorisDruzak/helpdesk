import {
  Badge,
} from "../../../components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  getTicketStatusTone,
} from "../../../features/tickets/status-presentation";
import {
  formatDateTime,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketInfoSidebar({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { ticketId, detail } = controller;
  if (!ticketId) return null;
  if (!detail) return null;
  return (<Card>
    <CardHeader>
      <CardTitle>Информация о тикете</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-slate-500">ID</span>
        <span className="font-medium text-slate-900">{detail?.ticket.ticket_code ?? ticketId}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-slate-500">Статус</span>
        <Badge tone={getTicketStatusTone(detail?.ticket.status ?? "")}>
          {detail?.ticket.status_label ?? "Загружаем"}
        </Badge>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-slate-500">Создан</span>
        <span className="font-medium text-slate-900">{formatDateTime(detail?.ticket.created_at)}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-slate-500">Обновлён</span>
        <span className="font-medium text-slate-900">{formatDateTime(detail?.ticket.updated_at)}</span>
      </div>
      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Инициатор</p>
        <p className="mt-2 font-semibold text-slate-950">
          {detail?.ticket.requester_display_name ?? "Не указан"}
        </p>
      </div>
    </CardContent>
  </Card>);
}