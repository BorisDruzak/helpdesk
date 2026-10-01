import {
  Clock3,
  FileText,
  History,
} from "lucide-react";
import {
  Badge,
} from "../../../components/ui/badge";
import {
  getTicketStatusTone,
} from "../../../features/tickets/status-presentation";
import {
  formatDateTime,
  getRoleLabel,
  getOperationTitle,
  customerHistorySummary,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketHistoryTab({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { activeTab, detail, historyItems, latestOperations, customerHistoryEvents, contextPreviewEvents } = controller;
  return (detail && activeTab === "history" ? (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-brand-700" />
          <p className="text-sm font-semibold text-slate-900">История клиента</p>
        </div>
        {customerHistoryEvents.length ? (
          customerHistoryEvents.map((event, index) => (
            <div
              key={`${event.event_id ?? event.source}-${event.occurred_at ?? index}`}
              className="rounded-[1.1rem] border border-border bg-white px-4 py-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-950">{event.title}</p>
                  <p className="mt-1 text-sm text-slate-600">{customerHistorySummary(event)}</p>
                </div>
                <Badge tone="neutral">{event.source}</Badge>
              </div>
              <p className="mt-3 text-xs text-slate-400">{formatDateTime(event.occurred_at)}</p>
            </div>
          ))
        ) : (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
            История клиента пока не передана.
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-brand-700" />
          <p className="text-sm font-semibold text-slate-900">Контекст для ассистента - preview</p>
        </div>
        {contextPreviewEvents.length ? (
          <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
            <div className="space-y-3">
              {contextPreviewEvents.map((event, index) => (
                <div
                  key={`${event.source}-${event.occurred_at ?? index}`}
                  className="border-b border-border pb-3 last:border-0 last:pb-0"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-950">{event.title}</p>
                    <span className="text-xs text-slate-400">{formatDateTime(event.occurred_at)}</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{customerHistorySummary(event)}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
            Preview контекста пока не передан.
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-brand-700" />
          <p className="text-sm font-semibold text-slate-900">Последние операции</p>
        </div>
        {latestOperations.length ? (
          latestOperations.map((operation) => (
            <div
              key={operation.operation_id}
              className="rounded-[1.1rem] border border-border bg-white px-4 py-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-950">{getOperationTitle(operation)}</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {operation.result_summary ?? operation.error_message ?? "Без краткого результата"}
                  </p>
                </div>
                <Badge tone={getTicketStatusTone(operation.status)}>{operation.status}</Badge>
              </div>
              <p className="mt-3 text-xs text-slate-400">
                queued {formatDateTime(operation.queued_at)} • finished {formatDateTime(operation.finished_at)}
              </p>
            </div>
          ))
        ) : (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
            Свежих операций по тикету пока нет.
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-brand-700" />
          <p className="text-sm font-semibold text-slate-900">Системные события</p>
        </div>
        {historyItems.length ? (
          historyItems.map((entry) => (
            <div
              key={`${entry.event_id ?? entry.ts ?? entry.text}`}
              className="rounded-[1.1rem] border border-border bg-white px-4 py-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-slate-950">{getRoleLabel(entry)}</p>
                <span className="text-sm text-slate-400">{formatDateTime(entry.ts)}</span>
              </div>
              <p className="mt-2 text-sm text-slate-600">{entry.text}</p>
              {entry.result_summary ? (
                <p className="mt-2 text-sm text-slate-500">{entry.result_summary}</p>
              ) : null}
            </div>
          ))
        ) : (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
            Отдельных событий истории пока нет.
          </div>
        )}
      </div>
    </div>
  ) : null);
}