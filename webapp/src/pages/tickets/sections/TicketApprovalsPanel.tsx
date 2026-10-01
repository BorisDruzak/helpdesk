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
  cn,
} from "../../../shared/ui/cn";
import {
  formatDateTime,
} from '../detail-formatting';
export function TicketApprovalsPanel({
  action,
  summary,
}: {
  action?: SupportTicketDetailPayload["actions"]["approval"] | null;
  summary?: SupportTicketDetailPayload["ticket"]["approval_summary"] | null;
}) {
  if (!summary || !summary.required) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Согласования</CardTitle>
          <CardDescription>Для этого шаблона согласование не требуется.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const pendingItems = summary.items.filter((item) => ["requested", "pending", "waiting"].includes(item.status));
  const currentItems = summary.items.filter((item) => item.current);
  const actionOwner = summary.current_action_owner === "approver" ? "Ожидает согласующего" : "Нужен контроль support";
  const statusTone = summary.rejected_count || summary.timed_out_count ? "warning" : pendingItems.length ? "info" : "success";

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Согласования</CardTitle>
            <CardDescription>Текущий владелец действия, сроки и результат по активной политике.</CardDescription>
          </div>
          <Badge tone={statusTone}>{actionOwner}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-[0.9rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Режим</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{summary.approval_mode}</p>
          </div>
          <div className="rounded-[0.9rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Источник</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{summary.approver_source ?? "policy"}</p>
          </div>
          <div className="rounded-[0.9rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Переходы</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {summary.approved_transition ?? "approved"} / {summary.rejected_transition ?? "rejected"}
            </p>
          </div>
        </div>

        {summary.require_comment_on_reject || action?.reject_requires_comment ? (
          <p className="rounded-[0.9rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            При отказе нужен комментарий. Без причины сервер заблокирует reject transition.
          </p>
        ) : null}

        <div className="space-y-2">
          {summary.items.map((item) => (
            <div
              className={cn(
                "rounded-[0.95rem] border px-4 py-3",
                item.current ? "border-brand-200 bg-brand-50" : "border-border bg-white",
              )}
              key={item.id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{item.approver_id ?? item.approval_type}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {item.approval_type} · запрошено {formatDateTime(item.requested_at)}
                  </p>
                </div>
                <Badge tone={item.current ? "info" : item.status === "approved" ? "success" : "neutral"}>
                  {item.current ? "Текущий" : item.status}
                </Badge>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-3">
                <span>Срок: {formatDateTime(item.due_at)}</span>
                <span>Напоминание: {formatDateTime(item.reminder_at)}</span>
                <span>Эскалация: {formatDateTime(item.escalation_at)}</span>
              </div>
              {item.reminded_at || item.escalated_at || item.timed_out_at ? (
                <p className="mt-2 text-xs text-amber-700">
                  События: напоминание {formatDateTime(item.reminded_at)} · эскалация {formatDateTime(item.escalated_at)}
                  {item.timed_out_at ? ` · timeout ${formatDateTime(item.timed_out_at)}` : ""}
                </p>
              ) : null}
            </div>
          ))}
        </div>

        {currentItems.length === 0 && pendingItems.length === 0 ? (
          <p className="rounded-[0.9rem] border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Активных согласований нет.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}