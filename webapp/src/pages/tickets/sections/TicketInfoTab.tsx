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
  formatDateTime,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketInfoTab({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { activeTab, queue, detail } = controller;
  return (detail && activeTab === "info" ? (
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="border-dashed shadow-none">
        <CardHeader>
          <CardTitle>Контекст обращения</CardTitle>
          <CardDescription>
            Реальные поля тикета, очередь, устройство и состав участников.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div>
            <p className="text-slate-500">Описание</p>
            <p className="mt-1 whitespace-pre-line text-slate-800">
              {detail.ticket.description ?? "Описание не заполнено."}
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-panel bg-white px-4 py-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Очередь</p>
              <p className="mt-2 font-semibold text-slate-950">
                {detail.ticket.queue.name ?? detail.ticket.queue.code ?? "Не указана"}
              </p>
            </div>
            <div className="rounded-panel bg-white px-4 py-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Устройство</p>
              <p className="mt-2 font-semibold text-slate-950">
                {detail.snapshot.device.hostname ?? detail.snapshot.device.device_id ?? "Нет привязки"}
              </p>
            </div>
          </div>
          <div className="rounded-panel bg-white px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Участники очереди</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {detail.ticket.queue_members.length ? (
                detail.ticket.queue_members.map((member) => (
                  <Badge key={member.actor_id} tone="neutral">
                    {member.actor_id}
                    {member.role_in_queue ? ` • ${member.role_in_queue}` : ""}
                  </Badge>
                ))
              ) : (
                <p className="text-sm text-slate-500">Состав очереди не передан.</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-dashed shadow-none">
        <CardHeader>
          <CardTitle>Observer</CardTitle>
          <CardDescription>
            Тот же observer summary, который backend уже отдаёт для тикета.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-2">
          <div className="rounded-panel bg-white px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Root trace</p>
            <p className="mt-2 break-all font-semibold text-slate-950">
              {detail.observer.summary.root_trace_id ?? "Нет trace"}
            </p>
          </div>
          <div className="rounded-panel bg-white px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Трассы / ошибки</p>
            <p className="mt-2 font-semibold text-slate-950">
              {detail.observer.summary.trace_count} / {detail.observer.summary.error_trace_count}
            </p>
          </div>
          <div className="rounded-panel bg-white px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Signatures</p>
            <p className="mt-2 font-semibold text-slate-950">
              {detail.observer.summary.signature_count}
            </p>
          </div>
          <div className="rounded-panel bg-white px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Последняя trace</p>
            <p className="mt-2 font-semibold text-slate-950">
              {formatDateTime(detail.observer.summary.latest_trace_at)}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  ) : null);
}