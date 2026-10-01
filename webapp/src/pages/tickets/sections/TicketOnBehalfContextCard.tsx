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
  TicketDiagnosticTarget,
  formatDiagnosticTarget,
  asRecord,
  textValue,
  compactParts,
  personContextLabel,
  onBehalfReason,
} from '../detail-formatting';
export function TicketOnBehalfContextCard({
  diagnosticTarget = null,
  ticket,
}: {
  diagnosticTarget?: TicketDiagnosticTarget | null;
  ticket: Pick<
    SupportTicketDetailPayload["ticket"],
    "device_id" | "requester_account_context" | "requester_account_warning" | "ticket_context"
  >;
}) {
  const ticketContext = asRecord(ticket.ticket_context);
  const accountContext = asRecord(ticket.requester_account_context);
  const creator = asRecord(ticketContext?.creator);
  const affected = asRecord(ticketContext?.affected);
  const targetDevice = asRecord(ticketContext?.target_device);
  const createdOnBehalf = ticketContext?.created_on_behalf === true || diagnosticTarget?.created_on_behalf === true;
  const accountWarning = textValue(ticket.requester_account_warning) ?? textValue(accountContext?.warning);

  if (!createdOnBehalf && !accountWarning) {
    return null;
  }

  const targetDeviceId = textValue(targetDevice?.device_id) ?? diagnosticTarget?.target_device_id ?? ticket.device_id ?? null;
  const affectedDisplay = personContextLabel(affected, diagnosticTarget?.affected_person_id ?? null);
  const diagnosticTargetSummary = targetDeviceId && affectedDisplay !== "не указан"
    ? `${targetDeviceId} · ${diagnosticTarget?.affected_display_name ?? textValue(affected?.display_name) ?? diagnosticTarget?.affected_person_id ?? textValue(affected?.person_id) ?? affectedDisplay}`
    : formatDiagnosticTarget(diagnosticTarget, targetDeviceId);
  const diagnosticSource = diagnosticTarget?.source ?? textValue(ticketContext?.diagnostic_target_source);
  const agentStatus = diagnosticTarget?.agent_status ?? textValue(targetDevice?.agent_status);
  const diagnosticStatus = compactParts([diagnosticSource, agentStatus]) || "нет данных";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Контекст обращения от имени</CardTitle>
        <CardDescription>
          Кто создал обращение, для кого оно заведено и на какой агент направлять диагностику.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-200/80 px-4 py-3">
          <span className="text-slate-500">Создал</span>
          <span className="max-w-[62%] text-right font-medium text-slate-900">{personContextLabel(creator, diagnosticTarget?.creator_person_id ?? null)}</span>
        </div>
        <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-200/80 px-4 py-3">
          <span className="text-slate-500">Затронутый пользователь</span>
          <span className="max-w-[62%] text-right font-medium text-slate-900">{affectedDisplay}</span>
        </div>
        <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-200/80 px-4 py-3">
          <span className="text-slate-500">Целевое устройство</span>
          <span className="max-w-[62%] break-all text-right font-medium text-slate-900">{targetDeviceId ?? "не указано"}</span>
        </div>
        <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-200/80 px-4 py-3">
          <span className="text-slate-500">Причина</span>
          <span className="max-w-[62%] text-right font-medium text-slate-900">{onBehalfReason(ticket)}</span>
        </div>
        <div className="rounded-lg bg-surface-subtle px-4 py-3">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Диагностическая цель</p>
          <p className="mt-2 break-words font-semibold text-slate-950">{diagnosticTargetSummary}</p>
          <p className="mt-1 text-xs text-slate-500">{diagnosticStatus}</p>
        </div>
        {accountWarning ? <Badge tone="warning">{accountWarning}</Badge> : null}
      </CardContent>
    </Card>
  );
}