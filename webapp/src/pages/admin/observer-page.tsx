import { useQuery } from "@tanstack/react-query";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { fetchObserverIntegrity, type ObserverIntegrityEvent } from "../../features/tech/observer-workbench-api";
import { ObserverQuickPanel } from "../../features/tech/observer-quick-panel";

function toneForSeverity(value: string | null | undefined): "danger" | "info" | "neutral" | "success" | "warning" {
  if (value === "critical" || value === "error") return "danger";
  if (value === "warning") return "warning";
  if (value === "info") return "info";
  return "neutral";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "нет данных";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function IntegrityEventRow({ event }: { event: ObserverIntegrityEvent }) {
  return (
    <div className="rounded-lg border border-border px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-slate-950">{event.event_type}</p>
          <p className="mt-1 text-xs text-slate-500">{event.source} · {formatDateTime(event.last_seen_at)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={toneForSeverity(event.severity)} withDot>{event.severity}</Badge>
          <Badge tone={event.status === "suppressed" ? "warning" : "neutral"}>{event.status}</Badge>
        </div>
      </div>
      <p className="mt-2 text-sm text-slate-600">{event.actual ?? event.expected}</p>
      <p className="mt-1 text-xs text-slate-500">
        {[event.device_id, event.ticket_id, event.operation_id, event.device_outbox_id ? `outbox ${event.device_outbox_id}` : null].filter(Boolean).join(" · ")}
      </p>
      {event.suppression_reason ? <p className="mt-2 text-xs font-medium text-amber-700">{event.suppression_reason}</p> : null}
    </div>
  );
}


export function AdminObserverPage() {
  const integrityQuery = useQuery({
    queryKey: ["observer-integrity", "active"],
    queryFn: () => fetchObserverIntegrity({ status: "active", limit: 50 }),
    retry: false,
  });
  const integrity = integrityQuery.data;
  const active = integrity?.summary.active_by_severity ?? {};

  return (
    <section className="space-y-6">
      <PageHeading
        description="Observer-вкладка теперь показывает реальные hot traces, деградации, dangerous flows и drilldown в том же интерфейсе, без моковых карточек."
        eyebrow="Observability"
        title="Observer"
      />

      <Card>
        <CardHeader>
          <CardTitle>Operational Integrity Observer</CardTitle>
          <CardDescription>OBS1 runtime invariants, dedupe and known-contamination suppression.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone="danger">critical {active.critical ?? 0}</Badge>
            <Badge tone="danger">error {active.error ?? 0}</Badge>
            <Badge tone="warning">warning {active.warning ?? 0}</Badge>
            <Badge tone="info">suppressed {integrity?.summary.suppressed_total ?? 0}</Badge>
          </div>
          {integrityQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем OBS1 integrity events...</p> : null}
          {integrityQuery.isError ? (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              {integrityQuery.error instanceof Error ? integrityQuery.error.message : "Не удалось загрузить OBS1 integrity events."}
            </p>
          ) : null}
          {integrity?.items.length ? (
            <div className="space-y-3">
              {integrity.items.map((event) => <IntegrityEventRow event={event} key={event.event_id} />)}
            </div>
          ) : !integrityQuery.isLoading ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-slate-500">Active OBS1 integrity events are not present.</p>
          ) : null}
        </CardContent>
      </Card>

      <ObserverQuickPanel deviceId={null} deviceLabel="всему контуру администрирования" />
    </section>
  );
}
