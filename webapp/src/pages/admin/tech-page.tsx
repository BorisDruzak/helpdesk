import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Database,
  ExternalLink,
  FileWarning,
  LockKeyhole,
  Search,
  RefreshCcw,
  Server,
  ShieldCheck,
  Terminal,
  Timer,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { StatTile } from "../../components/ui/stat-tile";
import { Tabs } from "../../components/ui/tabs";
import {
  fetchTechPanelV2Snapshot,
  locateTechQuery,
  type TechAlert,
  type TechGateStatus,
  type TechInventorySchedulerDetails,
  type TechLocatorMatch,
  type TechLocatorPayload,
  type TechLogEntry,
  type TechPanelV2Snapshot,
  type TechProblemDevice,
  type TechReadinessGate,
  type TechReadinessStatus,
  type TechSmokeResult,
  type TechStuckOperation,
} from "../../features/tech/tech-panel-api";
import { cn } from "../../shared/ui/cn";

type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";
type TabKey = "overview" | "security" | "runtime" | "database" | "agents" | "operations" | "logs" | "release";

const tabs: Array<{ value: TabKey; label: string }> = [
  { value: "overview", label: "Обзор" },
  { value: "security", label: "Безопасность" },
  { value: "runtime", label: "Runtime" },
  { value: "database", label: "База данных" },
  { value: "agents", label: "Агенты" },
  { value: "operations", label: "Операции" },
  { value: "logs", label: "Логи и сигналы" },
  { value: "release", label: "Релиз и smoke" },
];

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "нет данных";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function valueText(value: unknown, fallback = "нет данных"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "да" : "нет";
  return String(value);
}

function toneForStatus(status: TechGateStatus | TechReadinessStatus | string | null | undefined): BadgeTone {
  const normalized = String(status ?? "").toLowerCase();
  if (["ready", "ok", "success", "passed", "running", "online"].includes(normalized)) return "success";
  if (["degraded", "warning", "unknown", "enabled_not_running", "stale"].includes(normalized)) return "warning";
  if (["blocked", "critical", "error", "failed", "down", "offline"].includes(normalized)) return "danger";
  return "neutral";
}

function statusWord(status: TechReadinessStatus): string {
  if (status === "ready") return "READY";
  if (status === "degraded") return "DEGRADED";
  return "BLOCKED";
}

function EmptyState({ children }: { children: string }) {
  return <p className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-slate-500">{children}</p>;
}

function SafeLink({ href, children }: { href?: string | null; children: ReactNode }) {
  if (!href) return <span className="text-sm text-slate-400">{children}</span>;
  return (
    <Link className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900" to={href}>
      {children}
      <ExternalLink className="h-3.5 w-3.5" />
    </Link>
  );
}

function ReadinessBanner({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const { readiness } = snapshot;
  const topBlockers = readiness.blockers.slice(0, 3);
  return (
    <div
      className={cn(
        "rounded-xl border px-5 py-5 shadow-soft",
        readiness.status === "blocked"
          ? "border-rose-200 bg-rose-50"
          : readiness.status === "degraded"
            ? "border-amber-200 bg-amber-50"
            : "border-emerald-200 bg-emerald-50",
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={toneForStatus(readiness.status)} withDot>
              {statusWord(readiness.status)}
            </Badge>
            <span className="text-sm font-medium text-slate-600">
              Блокеры: {readiness.blockers.length} · предупреждения: {readiness.warnings.length} · score:{" "}
              {valueText(readiness.score)}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            Снимок готовности сформирован {formatDateTime(snapshot.generated_at)}. Любой critical readiness blocker переводит стенд в
            BLOCKED.
          </p>
        </div>
        <div className="min-w-0 lg:max-w-xl">
          {topBlockers.length ? (
            <ul className="space-y-2">
              {topBlockers.map((gate) => (
                <li className="text-sm text-slate-800" key={gate.key}>
                  <span className="font-semibold">{gate.title}:</span> {gate.description}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Критических блокеров сейчас нет.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiStrip({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const lastSmoke = snapshot.smoke.last_business_smoke?.status ?? snapshot.smoke.status;
  const restore = snapshot.database.last_restore_drill?.status ?? "unknown";
  const integrity = snapshot.observer_integrity;
  const activeIntegrity = integrity?.active_total ?? 0;
  const criticalIntegrity = integrity?.active_by_severity?.critical ?? 0;
  return (
    <div className="grid gap-4 xl:grid-cols-4 2xl:grid-cols-9">
      <StatTile accent={<Database className="h-5 w-5 text-emerald-600" />} helper="PostgreSQL" label="База" value={snapshot.database.reachable ? "OK" : "DOWN"} />
      <StatTile accent={<ShieldCheck className="h-5 w-5 text-blue-600" />} helper="Auth/Security" label="Security" value={snapshot.security.auth_mode.status.toUpperCase()} />
      <StatTile accent={<LockKeyhole className="h-5 w-5 text-indigo-600" />} helper="HTTPS/WSS" label="Transport" value={snapshot.readiness.gates.find((gate) => gate.key === "https_wss_required")?.status.toUpperCase() ?? "UNKNOWN"} />
      <StatTile accent={<Users className="h-5 w-5 text-cyan-600" />} helper={`из ${snapshot.agents.total}`} label="Agents online" value={String(snapshot.agents.online)} />
      <StatTile accent={<Timer className="h-5 w-5 text-amber-600" />} helper="queued/sent/running" label="Stuck operations" value={String(snapshot.operations.queued_stuck + snapshot.operations.sent_stuck + snapshot.operations.running_stuck)} />
      <StatTile accent={<Activity className="h-5 w-5 text-lime-600" />} helper="Inventory scheduler" label="Inventory" value={valueText(snapshot.runtime.schedulers.inventory_scheduler).toUpperCase()} />
      <StatTile accent={<Server className="h-5 w-5 text-slate-600" />} helper="Last smoke" label="Smoke" value={valueText(lastSmoke).toUpperCase()} />
      <StatTile accent={<FileWarning className="h-5 w-5 text-rose-600" />} helper="Restore drill" label="Restore" value={valueText(restore).toUpperCase()} />
      <StatTile accent={<AlertTriangle className="h-5 w-5 text-rose-600" />} helper={`${criticalIntegrity} critical`} label="OBS1 events" value={String(activeIntegrity)} />
    </div>
  );
}

const locatorSignalLabels: Array<[keyof TechLocatorMatch["signals"], string]> = [
  ["agent_offline", "agent offline"],
  ["stale_agent", "stale agent"],
  ["failed_operation", "failed operation"],
  ["stuck_operation", "stuck operation"],
  ["waiting_consent", "waiting consent"],
  ["outbox_backlog", "outbox backlog"],
  ["observer_errors", "observer errors"],
  ["pending_approval", "pending approval"],
  ["pending_consent", "pending consent"],
  ["inventory_missing_or_stale", "stale inventory"],
  ["ticket_sla_risk", "SLA risk"],
];

function LocatorMatchCard({ match }: { match: TechLocatorMatch }) {
  const signals = locatorSignalLabels.filter(([key]) => Boolean(match.signals[key]));
  return (
    <div className="rounded-lg border border-border bg-white px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="info">{match.kind}</Badge>
            <Badge tone={toneForStatus(match.severity)} withDot>
              {match.severity}
            </Badge>
            {match.status ? <span className="text-xs font-semibold uppercase text-slate-500">{match.status}</span> : null}
          </div>
          <p className="mt-2 font-semibold text-slate-950">{match.title}</p>
          <p className="mt-1 text-sm leading-6 text-slate-600">{match.reason}</p>
          <p className="mt-1 text-xs text-slate-500">
            {[
              match.context.ticket_code,
              match.context.ticket_id,
              match.context.device_id,
              match.context.hostname,
              match.context.operation_id,
              match.context.trace_id,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </div>
      {signals.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.map(([key, label]) => (
            <Badge key={key} tone="warning">
              {label}
            </Badge>
          ))}
        </div>
      ) : null}
      {match.links.length ? (
        <div className="mt-4 flex flex-wrap gap-3">
          {match.links.map((link) => (
            <SafeLink href={link.href} key={`${link.kind}:${link.href}`}>
              {link.label}
            </SafeLink>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function QuickLocatorPanel() {
  const [query, setQuery] = useState("");
  const [payload, setPayload] = useState<TechLocatorPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    setError(null);
    setValidation(null);
    if (normalized.length < 2) {
      setPayload(null);
      setValidation("Введите минимум 2 символа: ticket, device_id, hostname, operation_id или trace_id.");
      return;
    }
    setIsLoading(true);
    try {
      const nextPayload = await locateTechQuery(normalized);
      setPayload(nextPayload);
    } catch (caught) {
      setPayload(null);
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить быструю локализацию проблемы.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Быстрая локализация проблемы</CardTitle>
        <CardDescription>Поиск по ticket, device_id, hostname, operation_id или trace_id с безопасными ссылками на контекст.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="flex flex-col gap-3 md:flex-row" onSubmit={handleSubmit}>
          <input
            className="h-11 flex-1 rounded-lg border border-border bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-brand-300 focus:ring-2 focus:ring-brand-100"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ticket, device_id, hostname, operation_id или trace_id"
            type="search"
            value={query}
          />
          <Button disabled={isLoading} leadingIcon={<Search className="h-4 w-4" />} type="submit">
            {isLoading ? "Ищем..." : "Найти"}
          </Button>
        </form>
        {validation ? <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{validation}</p> : null}
        {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</p> : null}
        {payload ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
              <Badge tone={toneForStatus(payload.summary.highest_severity)} withDot>
                {payload.summary.highest_severity}
              </Badge>
              <span>Совпадений: {payload.summary.match_count}</span>
              <span>{formatDateTime(payload.generated_at)}</span>
            </div>
            {payload.summary.primary_diagnosis && payload.matches.length ? <p className="text-sm leading-6 text-slate-700">{payload.summary.primary_diagnosis}</p> : null}
            {payload.matches.length ? (
              <div className="space-y-3">
                {payload.matches.map((match) => (
                  <LocatorMatchCard key={`${match.kind}:${match.id}`} match={match} />
                ))}
              </div>
            ) : (
              <EmptyState>По запросу ничего не найдено. Проверьте ticket code, hostname, device_id, operation_id или trace_id.</EmptyState>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function GateList({ gates }: { gates: TechReadinessGate[] }) {
  return (
    <div className="space-y-3">
      {gates.map((gate) => (
        <div className="rounded-lg border border-border bg-white px-4 py-3" key={gate.key}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-slate-950">{gate.title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{gate.description}</p>
              {gate.evidence ? <p className="mt-1 text-xs text-slate-500">Evidence: {gate.evidence}</p> : null}
            </div>
            <Badge tone={toneForStatus(gate.status)} withDot>
              {gate.status}
            </Badge>
          </div>
          {gate.action_href ? (
            <div className="mt-3">
              <SafeLink href={gate.action_href}>{gate.action_label ?? "Открыть контекст"}</SafeLink>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function OverviewTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const integrity = snapshot.observer_integrity;
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Readiness gates</CardTitle>
          <CardDescription>Critical blockers, warnings and unknown marker-based checks for pilot readiness.</CardDescription>
        </CardHeader>
        <CardContent>
          <GateList gates={snapshot.readiness.gates} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Operational Integrity Observer</CardTitle>
          <CardDescription>Active OBS1 runtime invariants and narrow historical suppression.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone={toneForStatus(integrity?.status)} withDot>
              {integrity?.status ?? "unknown"}
            </Badge>
            <Badge tone="danger">critical {integrity?.active_by_severity?.critical ?? 0}</Badge>
            <Badge tone="warning">error {integrity?.active_by_severity?.error ?? 0}</Badge>
            <Badge tone="info">suppressed {integrity?.suppressed_total ?? 0}</Badge>
          </div>
          {integrity?.top_active?.length ? (
            <div className="space-y-3">
              {integrity.top_active.slice(0, 3).map((event) => (
                <div className="rounded-lg border border-border px-4 py-3" key={event.event_id}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="font-semibold text-slate-950">{event.event_type}</p>
                    <Badge tone={toneForStatus(event.severity)} withDot>
                      {event.severity}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{event.actual ?? event.expected}</p>
                  <p className="mt-1 text-xs text-slate-500">{[event.device_id, event.operation_id].filter(Boolean).join(" · ")}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>Active OBS1 integrity events are not present.</EmptyState>
          )}
          <SafeLink href={snapshot.links.observer}>Open Observer workbench</SafeLink>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Контекст</CardTitle>
          <CardDescription>Безопасные ссылки в рабочие поверхности. Browser actions в этом cut не добавлены.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <SafeLink href={snapshot.links.observer}>Открыть Observer</SafeLink>
          <SafeLink href={snapshot.links.inventory}>Открыть inventory</SafeLink>
          <SafeLink href={snapshot.links.device_operations}>Открыть Device Operations</SafeLink>
          <SafeLink href={snapshot.links.agent_updates}>Открыть agent updates</SafeLink>
          <SafeLink href={snapshot.links.command_center}>Открыть command center</SafeLink>
          <SafeLink href={snapshot.links.approval_center}>Открыть approvals</SafeLink>
          <SafeLink href={snapshot.links.logs}>Открыть логи</SafeLink>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricRow({ label, value, status }: { label: string; value: unknown; status?: string | null }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-3 last:border-b-0">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <span className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        {valueText(value)}
        {status ? <Badge tone={toneForStatus(status)}>{status}</Badge> : null}
      </span>
    </div>
  );
}

function SecurityTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const { security } = snapshot;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Auth mode</CardTitle>
          <CardDescription>config fallback, DB users и dev-like деградации.</CardDescription>
        </CardHeader>
        <CardContent>
          <MetricRow label="DB users enabled" value={security.auth_mode.db_users_enabled} />
          <MetricRow label="config fallback" value={security.auth_mode.config_fallback_enabled} status={security.auth_mode.status} />
          <MetricRow label="in-memory fallback possible" value={security.auth_mode.in_memory_fallback_possible} />
          <p className="pt-3 text-sm text-slate-500">{security.auth_mode.notes.join("; ")}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Session cookie и token channels</CardTitle>
          <CardDescription>Cookie flags, query token и agent connection policy.</CardDescription>
        </CardHeader>
        <CardContent>
          <MetricRow label="cookie Secure" value={security.session_cookie.secure} status={security.session_cookie.status} />
          <MetricRow label="cookie HttpOnly" value={security.session_cookie.httponly} />
          <MetricRow label="cookie SameSite" value={security.session_cookie.samesite} />
          <MetricRow label="query token allowed" value={security.token_channels.query_token_allowed} status={security.token_channels.status} />
          <MetricRow label="query token attempts recent" value={`${security.token_channels.query_token_attempts_recent ?? 0} attempts`} />
          <MetricRow label="connection policy" value={security.agent_connection_policy.mode ?? "unknown"} status={security.agent_connection_policy.status} />
          <MetricRow label="failed logins recent" value={security.audit.failed_logins_recent} />
          <MetricRow label="locked users" value={security.audit.locked_users_count} />
          <MetricRow label="invalid agent tokens" value={security.audit.invalid_agent_tokens_recent} />
        </CardContent>
      </Card>
    </div>
  );
}

function RuntimeTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const inventory: TechInventorySchedulerDetails | null | undefined = snapshot.runtime.scheduler_details?.inventory_scheduler;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-3">
        {snapshot.runtime.services.map((service) => (
          <Card key={service.key}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-3">
                {service.title}
                <Badge tone={toneForStatus(service.status)} withDot>
                  {service.status}
                </Badge>
              </CardTitle>
              <CardDescription>{service.details ?? "runtime health signal"}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Inventory scheduler details</CardTitle>
          <CardDescription>Runtime signal for duplicate task detection and last scheduler activity.</CardDescription>
        </CardHeader>
        <CardContent>
          {inventory ? (
            <>
              <MetricRow label="enabled" value={inventory.enabled} />
              <MetricRow label="running" value={inventory.running} />
              <MetricRow label="active task count" value={inventory.active_task_count ?? 0} status={inventory.duplicate_task_detected ? "warning" : "ok"} />
              <MetricRow label="duplicate detected" value={inventory.duplicate_task_detected} status={inventory.duplicate_task_detected ? "warning" : "ok"} />
              <MetricRow label="last tick" value={formatDateTime(inventory.last_tick_at)} />
              <MetricRow label="last error" value={inventory.last_error} />
            </>
          ) : (
            <EmptyState>Нет runtime details для inventory scheduler.</EmptyState>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DatabaseTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const db = snapshot.database;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>PostgreSQL</CardTitle>
          <CardDescription>Reachability, persistence and pool status.</CardDescription>
        </CardHeader>
        <CardContent>
          <MetricRow label="persistence enabled" value={db.persistence_enabled} />
          <MetricRow label="reachable" value={db.reachable} status={db.reachable ? "ok" : "blocked"} />
          <MetricRow label="database" value={db.database} />
          <MetricRow label="latency ms" value={db.latency_ms} />
          <MetricRow label="pool status" value={db.pool_status} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>migrations, backup, restore drill</CardTitle>
          <CardDescription>Safe marker/status based checks; no restore or shell command from UI.</CardDescription>
        </CardHeader>
        <CardContent>
          <MetricRow label="migrations status" value={db.migrations_status} status={db.migrations_status} />
          <MetricRow label="alembic current" value={db.alembic_current} />
          <MetricRow label="alembic head" value={db.alembic_head} />
          <MetricRow label="backup" value={db.last_backup?.status ?? "unknown"} />
          <MetricRow label="restore drill" value={db.last_restore_drill?.status ?? "unknown"} />
        </CardContent>
      </Card>
    </div>
  );
}

function BaselineDeviceList({ devices }: { devices: TechProblemDevice[] }) {
  if (!devices.length) return <EmptyState>Агентов ниже baseline в snapshot нет.</EmptyState>;
  return (
    <div className="space-y-3">
      {devices.map((device) => (
        <div className="grid gap-3 rounded-lg border border-border px-4 py-3 text-sm md:grid-cols-[minmax(150px,1fr)_minmax(140px,0.8fr)_120px_minmax(150px,0.8fr)]" key={device.device_id}>
          <SafeLink href={device.href ?? `/app/admin/device-operations/${device.device_id}`}>{device.device_id}</SafeLink>
          <span className="text-slate-700">{device.hostname ?? "hostname unknown"}</span>
          <span className="font-semibold text-slate-950">{device.agent_version ?? "unknown"}</span>
          <span className="text-xs text-slate-500">{formatDateTime(device.last_seen_at)}</span>
        </div>
      ))}
    </div>
  );
}

function AgentsTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const agents = snapshot.agents;
  const baselineDevices = agents.baseline?.devices ?? agents.below_baseline_devices ?? [];
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile label="online" value={String(agents.online)} helper={`total ${agents.total}`} />
        <StatTile label="offline" value={String(agents.offline)} helper="agent ws disconnected" />
        <StatTile label="stale" value={String(agents.stale)} helper="last_seen threshold" />
        <StatTile label="below baseline" value={valueText(agents.below_baseline)} helper="PILOT_MIN_AGENT_VERSION" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Problem devices</CardTitle>
          <CardDescription>Devices requiring baseline, token or stale-state attention.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <MetricRow label="pending connection requests" value={agents.pending_connection_requests} />
          <MetricRow label="reprovision required" value={agents.reprovision_required} />
          <MetricRow label="update in progress" value={agents.update_in_progress} />
          <MetricRow label="update failed recent" value={agents.update_failed_recent} />
          {agents.problem_devices.length ? (
            agents.problem_devices.map((device) => (
              <div className="rounded-lg border border-border px-4 py-3" key={device.device_id}>
                <SafeLink href={device.href ?? `/app/admin/device-operations/${device.device_id}`}>{device.device_id}</SafeLink>
                <p className="mt-2 text-sm text-slate-600">
                  {device.hostname ?? "hostname unknown"} · {device.status ?? "warning"} · {(device.reasons ?? []).join(", ") || "requires attention"}
                </p>
              </div>
            ))
          ) : (
            <EmptyState>Проблемных устройств в snapshot нет.</EmptyState>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Agents below baseline</CardTitle>
          <CardDescription>
            PILOT_MIN_AGENT_VERSION={valueText(agents.baseline?.min_version, "not configured")} · below baseline:{" "}
            {valueText(agents.baseline?.below_baseline_count ?? agents.below_baseline)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BaselineDeviceList devices={baselineDevices} />
        </CardContent>
      </Card>
    </div>
  );
}

function OperationsTable({ items }: { items: TechStuckOperation[] }) {
  if (!items.length) return <EmptyState>Зависших операций в snapshot нет.</EmptyState>;
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className="grid min-w-[820px] grid-cols-[minmax(180px,1fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)_100px_130px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
        <span>Operation</span>
        <span>Device</span>
        <span>Ticket</span>
        <span>Status</span>
        <span>Queued</span>
      </div>
      {items.map((operation) => (
        <div className="grid min-w-[820px] grid-cols-[minmax(180px,1fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)_100px_130px] gap-3 border-t border-border px-4 py-3 text-sm" key={operation.operation_id}>
          <SafeLink href={`/app/admin/operations/${operation.operation_id}`}>{operation.operation_id}</SafeLink>
          <SafeLink href={operation.device_id ? `/app/admin/device-operations/${operation.device_id}` : null}>{operation.device_id ?? "нет device"}</SafeLink>
          <SafeLink href={operation.ticket_id ? `/app/tickets/${operation.ticket_id}` : null}>{operation.ticket_id ? String(operation.ticket_id) : "нет ticket"}</SafeLink>
          <Badge tone={toneForStatus(operation.status)}>{operation.status ?? "unknown"}</Badge>
          <span className="text-xs text-slate-500">{formatDateTime(operation.queued_at)}</span>
        </div>
      ))}
    </div>
  );
}

function OperationsTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  const ops = snapshot.operations;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile label="queued stuck" value={String(ops.queued_stuck)} helper="delivery timeout" />
        <StatTile label="sent stuck" value={String(ops.sent_stuck)} helper="accepted timeout" />
        <StatTile label="running stuck" value={String(ops.running_stuck)} helper="execution timeout" />
        <StatTile label="outbox backlog" value={valueText(ops.outbox_backlog)} helper={`recent nack ${valueText(ops.recent_nack_count)}`} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Stuck operations</CardTitle>
          <CardDescription>queued/sent/running операции с safe links в ticket/device context.</CardDescription>
        </CardHeader>
        <CardContent>
          <OperationsTable items={ops.items} />
        </CardContent>
      </Card>
    </div>
  );
}

function LogsTable({ logs }: { logs: TechLogEntry[] }) {
  if (!logs.length) return <EmptyState>Проблемных логов нет.</EmptyState>;
  return (
    <div className="space-y-3">
      {logs.map((log, index) => (
        <div className="rounded-lg border border-border px-4 py-3" key={String(log.id ?? index)}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Badge tone={toneForStatus(log.level)}>{log.level ?? "log"}</Badge>
            <span className="text-xs text-slate-500">{formatDateTime(log.created_at ?? log.ts)}</span>
          </div>
          <p className="mt-2 font-semibold text-slate-950">{valueText(log.message, "-")}</p>
          <p className="mt-1 text-sm text-slate-500">{valueText(log.logger ?? log.module, "server")}</p>
        </div>
      ))}
    </div>
  );
}

function LogsTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Alerts
          </CardTitle>
          <CardDescription>Signals grouped by severity; first cut is read-only.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {snapshot.alerts.length ? (
            snapshot.alerts.map((alert: TechAlert, index) => (
              <div className="rounded-lg border border-border px-4 py-3" key={String(alert.id ?? index)}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-semibold text-slate-950">{alert.title ?? "Сигнал техпанели"}</p>
                  <Badge tone={toneForStatus(alert.severity)} withDot>
                    {alert.severity ?? "info"}
                  </Badge>
                </div>
                {alert.description ? <p className="mt-2 text-sm text-slate-600">{alert.description}</p> : null}
              </div>
            ))
          ) : (
            <EmptyState>Активных alerts нет.</EmptyState>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-rose-500" />
            Problem logs
          </CardTitle>
          <CardDescription>warning/error/critical из server log-buffer.</CardDescription>
        </CardHeader>
        <CardContent>
          <LogsTable logs={snapshot.logs.problem_logs} />
        </CardContent>
      </Card>
    </div>
  );
}

function SmokeSteps({ result }: { result?: TechSmokeResult | null }) {
  if (!result?.steps?.length) return <EmptyState>Smoke steps не записаны в marker.</EmptyState>;
  return (
    <div className="space-y-2">
      {result.steps.map((step) => (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-3" key={step.key}>
          <span className="font-semibold text-slate-950">{step.key}</span>
          <Badge tone={toneForStatus(step.status)}>{step.status}</Badge>
        </div>
      ))}
    </div>
  );
}

function ReleaseTab({ snapshot }: { snapshot: TechPanelV2Snapshot }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Release</CardTitle>
          <CardDescription>Branch, commit, deploy gate and bundle metadata from marker file.</CardDescription>
        </CardHeader>
        <CardContent>
          <MetricRow label="branch" value={snapshot.release.branch} />
          <MetricRow label="commit" value={snapshot.release.commit} />
          <MetricRow label="deployed_at" value={formatDateTime(snapshot.release.deployed_at)} />
          <MetricRow label="gate" value={snapshot.release.gate ?? "unknown"} />
          <MetricRow label="dirty" value={snapshot.release.dirty} />
          <MetricRow label="webapp bundle commit" value={snapshot.release.webapp_bundle_commit} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>business smoke</CardTitle>
          <CardDescription>Last health/business smoke marker. Missing marker is visible as unknown.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <MetricRow label="overall smoke status" value={snapshot.smoke.status} status={snapshot.smoke.status} />
          <MetricRow label="business smoke" value={snapshot.smoke.last_business_smoke?.status ?? "unknown"} />
          <MetricRow label="finished" value={formatDateTime(snapshot.smoke.last_business_smoke?.finished_at)} />
          <SmokeSteps result={snapshot.smoke.last_business_smoke} />
        </CardContent>
      </Card>
    </div>
  );
}

function ActiveTab({ tab, snapshot }: { tab: TabKey; snapshot: TechPanelV2Snapshot }) {
  if (tab === "security") return <SecurityTab snapshot={snapshot} />;
  if (tab === "runtime") return <RuntimeTab snapshot={snapshot} />;
  if (tab === "database") return <DatabaseTab snapshot={snapshot} />;
  if (tab === "agents") return <AgentsTab snapshot={snapshot} />;
  if (tab === "operations") return <OperationsTab snapshot={snapshot} />;
  if (tab === "logs") return <LogsTab snapshot={snapshot} />;
  if (tab === "release") return <ReleaseTab snapshot={snapshot} />;
  return <OverviewTab snapshot={snapshot} />;
}

export function AdminTechPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const techQuery = useQuery({
    queryKey: ["admin-tech-panel-v2"],
    queryFn: fetchTechPanelV2Snapshot,
    refetchInterval: 15_000,
    retry: false,
  });
  const snapshot = techQuery.data;
  const tabItems = useMemo(() => tabs, []);

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {snapshot ? (
              <>
                <SafeLink href={snapshot.links.observer}>Открыть Observer</SafeLink>
                <SafeLink href={snapshot.links.device_operations}>Открыть Device Operations</SafeLink>
                <SafeLink href={snapshot.links.logs}>Открыть логи</SafeLink>
              </>
            ) : null}
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void techQuery.refetch()} size="sm" variant="outline">
              Обновить
            </Button>
          </div>
        }
        description="Готовность к пилоту, безопасность, runtime, PostgreSQL, агенты, операции, логи и smoke."
        eyebrow="Admin workspace"
        title="Техпанель стенда"
      />

      {techQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем снимок техпанели...</p> : null}
      {techQuery.isError ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
          {techQuery.error instanceof Error ? techQuery.error.message : "Не удалось загрузить снимок техпанели."}
        </p>
      ) : null}

      {snapshot ? (
        <>
          <ReadinessBanner snapshot={snapshot} />
          <QuickLocatorPanel />
          <KpiStrip snapshot={snapshot} />
          <Tabs items={tabItems} onValueChange={(value) => setActiveTab(value as TabKey)} value={activeTab} />
          <ActiveTab snapshot={snapshot} tab={activeTab} />
        </>
      ) : null}
    </section>
  );
}
