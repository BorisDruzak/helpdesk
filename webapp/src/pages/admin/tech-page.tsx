import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, RefreshCcw, Server, Terminal, Timer, Users } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { StatTile } from "../../components/ui/stat-tile";
import {
  fetchTechPanelSnapshot,
  type TechAlert,
  type TechAuditEvent,
  type TechLogEntry,
  type TechOverviewPayload,
  type TechStatus,
  type TechStuckOperation,
} from "../../features/tech/tech-panel-api";

type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function readString(record: Record<string, unknown> | null | undefined, keys: string[], fallback = "-"): string {
  if (!record) {
    return fallback;
  }
  for (const key of keys) {
    const value = record[key];
    if (value !== null && value !== undefined && String(value).trim()) {
      return String(value);
    }
  }
  return fallback;
}

function readNumber(record: Record<string, unknown> | null | undefined, keys: string[], fallback = 0): number {
  if (!record) {
    return fallback;
  }
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return fallback;
}

function toneForStatus(status: TechStatus | null | undefined): BadgeTone {
  const normalized = String(status ?? "").trim().toLowerCase();
  if (["ok", "online", "running", "success", "healthy"].includes(normalized)) {
    return "success";
  }
  if (["warning", "warn", "stale", "pending", "degraded"].includes(normalized)) {
    return "warning";
  }
  if (["error", "critical", "failed", "offline", "down"].includes(normalized)) {
    return "danger";
  }
  if (["info", "unknown"].includes(normalized)) {
    return "info";
  }
  return "neutral";
}

function statusLabel(status: TechStatus | null | undefined): string {
  return String(status ?? "unknown");
}

function OverviewTiles({ overview }: { overview: TechOverviewPayload }) {
  const agentHealth = overview.agent_health;
  const operationsHealth = overview.operations_health;
  const updateHealth = overview.update_health;
  const serviceHealth = overview.service_health;
  const postgresHealth = overview.postgres_health;
  const onlineAgents = readNumber(agentHealth, ["online", "online_count"]);
  const totalAgents = readNumber(agentHealth, ["total", "total_count"]);
  const stuckOperations = readNumber(operationsHealth, ["stuck_count", "stuck"]);
  const failedOperations = readNumber(operationsHealth, ["failed_recent_count", "failed_count", "failed"]);
  const pendingUpdates = readNumber(updateHealth, ["pending_updates", "pending_count", "pending"]);
  const failedUpdates = readNumber(updateHealth, ["failed_updates", "failed_count", "failed"]);
  const postgresStatus = readString(postgresHealth, ["status", "label"], "unknown");
  const apiStatus = readString(serviceHealth, ["api", "http", "server"], "unknown");

  return (
    <div className="grid gap-4 xl:grid-cols-4">
      <StatTile
        accent={<Server className="h-5 w-5 text-brand-600" />}
        helper={`API: ${apiStatus}`}
        label="PostgreSQL"
        value={postgresStatus}
      />
      <StatTile
        accent={<Activity className="h-5 w-5 text-emerald-600" />}
        helper={totalAgents ? `Всего агентов: ${totalAgents}` : "Сводка агентов"}
        label="Агенты online"
        value={String(onlineAgents)}
      />
      <StatTile
        accent={<Timer className="h-5 w-5 text-amber-600" />}
        helper={`Ошибок недавно: ${failedOperations}`}
        label="Зависшие операции"
        value={String(stuckOperations)}
      />
      <StatTile
        accent={<RefreshCcw className="h-5 w-5 text-blue-600" />}
        helper={`Ошибок обновления: ${failedUpdates}`}
        label="Ожидают обновления"
        value={String(pendingUpdates)}
      />
    </div>
  );
}

function EmptyState({ children }: { children: string }) {
  return <p className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-slate-500">{children}</p>;
}

function AlertsPanel({ alerts }: { alerts: TechAlert[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Сигналы
        </CardTitle>
        <CardDescription>Активные health-alerts из legacy техпанели.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {alerts.length ? (
          alerts.slice(0, 8).map((alert, index) => (
            <div className="rounded-lg border border-border bg-white px-4 py-3" key={String(alert.id ?? `${alert.title}-${index}`)}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-semibold text-slate-950">{alert.title ?? "Сигнал техпанели"}</p>
                <Badge tone={toneForStatus(alert.severity)} withDot>
                  {statusLabel(alert.severity)}
                </Badge>
              </div>
              {alert.description ? <p className="mt-2 text-sm leading-6 text-slate-600">{alert.description}</p> : null}
              <p className="mt-2 text-xs text-slate-400">{formatDateTime(alert.created_at)}</p>
            </div>
          ))
        ) : (
          <EmptyState>Активных сигналов нет.</EmptyState>
        )}
      </CardContent>
    </Card>
  );
}

function LogsPanel({ logs }: { logs: TechLogEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Terminal className="h-5 w-5 text-rose-500" />
          Проблемные логи
        </CardTitle>
        <CardDescription>Последние warning/error/critical записи серверного log-buffer.</CardDescription>
      </CardHeader>
      <CardContent>
        {logs.length ? (
          <div className="overflow-x-auto rounded-lg border border-border">
            <div className="grid min-w-[760px] grid-cols-[150px_90px_minmax(150px,0.8fr)_minmax(280px,1.6fr)] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
              <span>Время</span>
              <span>Level</span>
              <span>Logger</span>
              <span>Message</span>
            </div>
            {logs.slice(0, 12).map((log, index) => (
              <div
                className="grid min-w-[760px] grid-cols-[150px_90px_minmax(150px,0.8fr)_minmax(280px,1.6fr)] gap-3 border-t border-border px-4 py-3 text-sm"
                key={String(log.id ?? `${log.ts ?? log.created_at}-${index}`)}
              >
                <span className="text-xs text-slate-500">{formatDateTime(log.ts ?? log.created_at)}</span>
                <Badge tone={toneForStatus(log.level)}>{log.level ?? "log"}</Badge>
                <span className="truncate text-slate-600">{log.logger ?? "-"}</span>
                <span className="break-words font-medium text-slate-900">{log.message ?? "-"}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState>Проблемных записей в log-buffer нет.</EmptyState>
        )}
      </CardContent>
    </Card>
  );
}

function StuckOperationsPanel({ operations }: { operations: TechStuckOperation[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Зависшие операции</CardTitle>
        <CardDescription>Операции, превысившие пороги queued/sent/running из backend watchdog.</CardDescription>
      </CardHeader>
      <CardContent>
        {operations.length ? (
          <div className="overflow-x-auto rounded-lg border border-border">
            <div className="grid min-w-[760px] grid-cols-[minmax(180px,1fr)_minmax(160px,1fr)_100px_130px_150px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
              <span>Operation</span>
              <span>Device</span>
              <span>Status</span>
              <span>Kind</span>
              <span>Queued</span>
            </div>
            {operations.slice(0, 10).map((operation, index) => (
              <div
                className="grid min-w-[760px] grid-cols-[minmax(180px,1fr)_minmax(160px,1fr)_100px_130px_150px] gap-3 border-t border-border px-4 py-3 text-sm"
                key={String(operation.operation_id ?? index)}
              >
                <span className="truncate font-semibold text-slate-950">{operation.operation_id ?? "-"}</span>
                <span className="truncate text-slate-600">{operation.device_id ?? "-"}</span>
                <Badge tone={toneForStatus(operation.status)}>{operation.status ?? "-"}</Badge>
                <span className="text-slate-600">{operation.kind ?? "-"}</span>
                <span className="text-xs text-slate-500">{formatDateTime(operation.queued_at)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState>Зависших операций нет.</EmptyState>
        )}
      </CardContent>
    </Card>
  );
}

function AuditPanel({
  agentAuditEvents,
  userAuditEvents,
}: {
  agentAuditEvents: TechAuditEvent[];
  userAuditEvents: TechAuditEvent[];
}) {
  const events = [
    ...agentAuditEvents.slice(0, 5).map((event) => ({ ...event, source: "agent" })),
    ...userAuditEvents.slice(0, 5).map((event) => ({ ...event, source: "user" })),
  ].sort((left, right) => String(right.created_at ?? "").localeCompare(String(left.created_at ?? "")));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5 text-blue-600" />
          Audit feed
        </CardTitle>
        <CardDescription>Последние события agent runtime и UI user audit.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {events.length ? (
          events.slice(0, 8).map((event, index) => (
            <div className="rounded-lg border border-border px-4 py-3 text-sm" key={String(event.id ?? index)}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-semibold text-slate-950">
                  {event.title ?? event.event_type ?? event.action ?? "audit event"}
                </p>
                <Badge tone={event.source === "agent" ? "brand" : "info"}>{event.source}</Badge>
              </div>
              <p className="mt-2 text-slate-500">
                {event.device_id ?? event.entity_type ?? event.actor_role ?? "system"} · {formatDateTime(event.created_at)}
              </p>
            </div>
          ))
        ) : (
          <EmptyState>Audit feed пуст.</EmptyState>
        )}
      </CardContent>
    </Card>
  );
}

export function AdminTechPage() {
  const techQuery = useQuery({
    queryKey: ["admin-tech-panel"],
    queryFn: fetchTechPanelSnapshot,
    refetchInterval: 15_000,
    retry: false,
  });

  const snapshot = techQuery.data;

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Button
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => void techQuery.refetch()}
            size="sm"
            variant="outline"
          >
            Обновить
          </Button>
        }
        description="Перенесённая legacy техпанель: health, alerts, проблемные логи, stuck operations и audit feed сервера."
        eyebrow="Admin workspace"
        title="Техпанель сервера"
      />

      {techQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем техпанель...</p> : null}
      {techQuery.isError ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
          {techQuery.error instanceof Error ? techQuery.error.message : "Не удалось загрузить техпанель."}
        </p>
      ) : null}

      {snapshot ? (
        <>
          <OverviewTiles overview={snapshot.overview} />
          <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <AlertsPanel alerts={snapshot.alerts} />
            <LogsPanel logs={snapshot.logs} />
          </div>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <StuckOperationsPanel operations={snapshot.stuckOperations} />
            <AuditPanel agentAuditEvents={snapshot.agentAuditEvents} userAuditEvents={snapshot.userAuditEvents} />
          </div>
        </>
      ) : null}
    </section>
  );
}
