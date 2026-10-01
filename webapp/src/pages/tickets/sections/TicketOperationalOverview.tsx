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
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketOperationalOverview({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { detail, priorityDecision, operationalRows, operationalCompleteness } = controller;
  if (!detail) return null;
  return (<Card>
    <CardHeader>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>Операционная карточка</CardTitle>
          <CardDescription>Сводка по 7 вопросам для принятия заявки в работу.</CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={operationalCompleteness >= 7 ? "success" : "warning"}>Passport {operationalCompleteness}/7</Badge>
          <Badge tone="info">{detail.ticket.ticket_type ?? "request"}</Badge>
          <Badge tone="warning">{detail.ticket.priority_class ?? detail.ticket.priority ?? "P3"}</Badge>
        </div>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {operationalRows.map((row) => (
          <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-4 py-3" key={row.question}>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{row.question}</p>
            <p className="mt-2 text-sm font-medium text-slate-900">{row.answer}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-[0.9rem] bg-white px-4 py-3 ring-1 ring-border">
          <p className="text-xs text-slate-500">Влияние</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">{detail.ticket.impact ?? "Не указан"}</p>
        </div>
        <div className="rounded-[0.9rem] bg-white px-4 py-3 ring-1 ring-border">
          <p className="text-xs text-slate-500">Срочность</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">{detail.ticket.urgency ?? "Не указана"}</p>
        </div>
        <div className="rounded-[0.9rem] bg-white px-4 py-3 ring-1 ring-border">
          <p className="text-xs text-slate-500">Важность</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">{detail.ticket.importance ?? "Не указана"}</p>
        </div>
        <div className="rounded-[0.9rem] bg-white px-4 py-3 ring-1 ring-border">
          <p className="text-xs text-slate-500">Почему такой приоритет</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {String(priorityDecision.priority_reason ?? "Нет обоснования")}
          </p>
        </div>
      </div>
    </CardContent>
  </Card>);
}