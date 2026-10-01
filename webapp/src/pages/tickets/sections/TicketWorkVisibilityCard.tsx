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
  type SupportTicketDetailPayload,
} from "../../../features/queues/api";
import {
  getTicketStatusPresentation,
} from "../../../features/tickets/status-presentation";
import {
  formatDateTime,
} from '../detail-formatting';
export function TicketWorkVisibilityCard({
  ticket,
}: {
  ticket: Pick<
    SupportTicketDetailPayload["ticket"],
    | "status"
    | "status_label"
    | "requester_status_label"
    | "next_action_owner"
    | "next_action_due_at"
    | "status_reason"
    | "resolution_code"
    | "resolution_summary"
    | "requester_resolution_summary"
    | "evidence_required"
    | "evidence_ref"
  >;
}) {
  const presentation = getTicketStatusPresentation({
    status: ticket.status,
    statusLabel: ticket.status_label,
    requesterStatusLabel: ticket.requester_status_label,
    nextActionOwner: ticket.next_action_owner,
    statusReason: ticket.status_reason,
    evidenceRequired: ticket.evidence_required,
    evidenceRef: ticket.evidence_ref,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ход работы</CardTitle>
        <CardDescription>Внутреннее состояние, пользовательский статус и следующий ответственный.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1rem] border border-border bg-white px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Этап</p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <Badge tone={presentation.tone}>{presentation.stageLabel}</Badge>
              {presentation.waits ? <Badge tone="warning">Wait ledger</Badge> : null}
              {presentation.terminal ? <Badge tone="neutral">Terminal</Badge> : null}
            </div>
          </div>
          <div className="rounded-[1rem] border border-border bg-white px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Evidence gate</p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <Badge tone={presentation.evidenceTone}>{presentation.evidenceLabel}</Badge>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Внутренний статус</span>
          <Badge tone={presentation.tone}>{presentation.statusLabel}</Badge>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Статус для пользователя</span>
          <span className="font-medium text-slate-900">{presentation.requesterStatusLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Чей ход</span>
          <span className="font-medium text-slate-900">{presentation.ownerLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Что делать</span>
          <span className="max-w-[60%] text-right font-medium text-slate-900">{presentation.operatorActionLabel}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Следующий срок</span>
          <span className="font-medium text-slate-900">{formatDateTime(ticket.next_action_due_at)}</span>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Причина ожидания</p>
          <p className="mt-2 font-semibold text-slate-950">{presentation.statusReasonLabel}</p>
        </div>
        {ticket.resolution_code ||
          ticket.resolution_summary ||
          ticket.requester_resolution_summary ||
          ticket.evidence_required ||
          ticket.evidence_ref ? (
          <div className="rounded-[1.1rem] border border-border px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Решение и подтверждение</p>
            <dl className="mt-3 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Код решения</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.resolution_code || "Не указан"}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Для пользователя</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.requester_resolution_summary || ticket.resolution_summary || "Не заполнено"}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Доказательство</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.evidence_ref || presentation.evidenceLabel}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}