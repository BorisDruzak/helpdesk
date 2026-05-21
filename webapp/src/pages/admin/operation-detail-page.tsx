import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { fetchOperationDetail, type OperationDetail } from "../../features/operations/operation-detail-api";

type Tone = "danger" | "info" | "neutral" | "success" | "warning";

function toneForStatus(status: string | null | undefined): Tone {
  const normalized = String(status ?? "").toLowerCase();
  if (["succeeded", "success", "ok"].includes(normalized)) return "success";
  if (["queued", "sent", "accepted", "running", "waiting_consent"].includes(normalized)) return "warning";
  if (["failed", "timed_out", "error"].includes(normalized)) return "danger";
  return "neutral";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "нет данных";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "нет данных";
  return String(value);
}

function FieldRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-border/70 py-2 text-sm last:border-b-0 sm:grid-cols-[180px_minmax(0,1fr)]">
      <span className="text-slate-500">{label}</span>
      <span className="min-w-0 break-words font-medium text-slate-900">{value}</span>
    </div>
  );
}

function SafeLink({ href, children }: { href?: string | null; children: string }) {
  if (!href) {
    return null;
  }
  return (
    <Link className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900" to={href}>
      {children}
      <ArrowUpRight className="h-3.5 w-3.5" />
    </Link>
  );
}

function OperationFields({ operation }: { operation: OperationDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Read-only детали</CardTitle>
        <CardDescription>Состояние операции, контекст тикета, устройства и observer trace без управляющих действий.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldRow label="operation_id" value={operation.operation_id} />
        <FieldRow label="Статус" value={<Badge tone={toneForStatus(operation.status)}>{valueText(operation.status)}</Badge>} />
        <FieldRow label="Тип" value={valueText(operation.kind)} />
        <FieldRow label="Инструмент" value={valueText(operation.tool_name)} />
        <FieldRow label="actor_role" value={valueText(operation.actor_role)} />
        <FieldRow label="ticket_id" value={valueText(operation.ticket_id)} />
        <FieldRow label="device_id" value={valueText(operation.device_id)} />
        <FieldRow label="trace_id" value={valueText(operation.trace_id)} />
        <FieldRow label="queued_at" value={formatDateTime(operation.queued_at)} />
        <FieldRow label="sent_at" value={formatDateTime(operation.sent_at)} />
        <FieldRow label="accepted_at" value={formatDateTime(operation.accepted_at)} />
        <FieldRow label="started_at" value={formatDateTime(operation.started_at)} />
        <FieldRow label="finished_at" value={formatDateTime(operation.finished_at)} />
        <FieldRow label="deadline_at" value={formatDateTime(operation.deadline_at)} />
        <FieldRow label="retry" value={`${operation.retry_count ?? 0}/${operation.max_retries ?? 0}`} />
        <FieldRow label="retry_of" value={valueText(operation.retry_of_operation_id)} />
        <FieldRow label="error_code" value={valueText(operation.error_code)} />
        <FieldRow label="error_message" value={valueText(operation.error_message)} />
        <FieldRow label="result_summary" value={valueText(operation.result_summary)} />
      </CardContent>
    </Card>
  );
}

export function AdminOperationDetailPage() {
  const { operationId = "" } = useParams();
  const query = useQuery({
    queryKey: ["operation-detail", operationId],
    queryFn: () => fetchOperationDetail(operationId),
    enabled: Boolean(operationId),
  });

  return (
    <div className="space-y-6">
      <PageHeading
        actions={
          <Button onClick={() => query.refetch()} type="button" variant="outline">
            <RefreshCcw className="h-4 w-4" />
            Обновить
          </Button>
        }
        description="Read-only карточка операции для диагностики: статус, tool, ticket/device context, trace и безопасные ссылки."
        eyebrow="Tech Panel"
        title={`Операция ${operationId}`}
      />

      {query.isLoading ? <Card><CardContent className="p-5 text-sm text-slate-500">Загружаем операцию...</CardContent></Card> : null}
      {query.error ? (
        <Card>
          <CardContent className="p-5 text-sm text-rose-700">{query.error instanceof Error ? query.error.message : "Не удалось загрузить операцию."}</CardContent>
        </Card>
      ) : null}
      {query.data ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <OperationFields operation={query.data.operation} />
          <Card>
            <CardHeader>
              <CardTitle>Контекст</CardTitle>
              <CardDescription>Только переходы к связанным read-only рабочим областям.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <SafeLink href={query.data.links.ticket}>Открыть тикет</SafeLink>
              <SafeLink href={query.data.links.device_operations}>Device Operations</SafeLink>
              <SafeLink href={query.data.links.observer}>Observer</SafeLink>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
