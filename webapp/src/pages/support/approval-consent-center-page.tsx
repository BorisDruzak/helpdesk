import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, RefreshCcw, ShieldCheck } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { fetchApprovalConsentCenter } from "../../features/approval-consent-center/api";
import type {
  ApprovalConsentItem,
  ApprovalConsentRisk,
  ApprovalConsentScope,
  ApprovalConsentSection,
  ApprovalConsentSeverity,
  FetchApprovalConsentCenterParams,
} from "../../features/approval-consent-center/types";

const scopeOptions: Array<{ value: ApprovalConsentScope; label: string }> = [
  { value: "my", label: "Мои" },
  { value: "team", label: "Команда" },
  { value: "all", label: "Все доступные" },
];

const statusOptions = [
  { value: "pending", label: "Ожидает" },
  { value: "all", label: "Все статусы" },
  { value: "approved", label: "Согласовано" },
  { value: "rejected", label: "Отклонено" },
  { value: "expired", label: "Истекло" },
];

const kindOptions = [
  { value: "", label: "Все типы" },
  { value: "pending_approval", label: "Согласования" },
  { value: "pending_consent", label: "Запросы согласия" },
  { value: "ticket_approval", label: "Тикеты" },
  { value: "change_approval", label: "Изменения" },
  { value: "risky_tool_consent", label: "Рискованные команды" },
  { value: "remote_assist_consent", label: "Удалённая помощь" },
  { value: "closure_approval", label: "Закрытие" },
  { value: "policy_override", label: "Переопределения политик" },
];

const riskOptions: Array<{ value: "" | Exclude<ApprovalConsentRisk, "unknown">; label: string }> = [
  { value: "", label: "Любой риск" },
  { value: "critical", label: "Критичный" },
  { value: "high", label: "Высокий" },
  { value: "medium", label: "Средний" },
  { value: "low", label: "Низкий" },
];

const statusLabels: Record<ApprovalConsentItem["status"], string> = {
  pending: "Ожидает",
  approved: "Согласовано",
  rejected: "Отклонено",
  expired: "Истекло",
  canceled: "Отменено",
  unknown: "Неизвестно",
};

const riskLabels: Record<ApprovalConsentRisk, string> = {
  critical: "Критичный",
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
  unknown: "Неизвестно",
};

const sectionCopy: Partial<Record<ApprovalConsentSection["key"], { title: string; description: string }>> = {
  waiting_me: {
    title: "Ждёт меня",
    description: "Согласования, где текущий оператор указан исполнителем или согласующим.",
  },
  waiting_user: {
    title: "Ждёт пользователя",
    description: "Запросы согласия, которые должен подтвердить пользователь.",
  },
  overdue: {
    title: "Просрочено",
    description: "Срок согласования или запроса согласия уже истёк.",
  },
  high_risk: {
    title: "Высокий риск",
    description: "Согласования и запросы согласия с высоким или критичным риском.",
  },
  ticket_approvals: {
    title: "Тикеты",
    description: "Согласования в процессе обработки тикетов.",
  },
  change_approvals: {
    title: "Изменения",
    description: "Согласования изменений.",
  },
  risky_tool_consents: {
    title: "Рискованные команды",
    description: "Операции, ожидающие согласия перед запуском.",
  },
  remote_assist_consents: {
    title: "Удалённая помощь",
    description: "Сессии удалённой помощи, ожидающие согласия пользователя.",
  },
  closure_approvals: {
    title: "Закрытие",
    description: "Блокеры закрытия тикета, похожие на согласование.",
  },
  policy_overrides: {
    title: "Переопределения политик",
    description: "Ожидающие запросы на переопределение политик, если источник существует.",
  },
};

const severityClasses: Record<ApprovalConsentSeverity, string> = {
  critical: "border-red-300 bg-red-50 text-red-950",
  warning: "border-amber-300 bg-amber-50 text-amber-950",
  info: "border-sky-300 bg-sky-50 text-sky-950",
};

const riskClasses: Record<ApprovalConsentRisk, string> = {
  critical: "border-red-200 bg-red-50 text-red-900",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  medium: "border-amber-200 bg-amber-50 text-amber-900",
  low: "border-emerald-200 bg-emerald-50 text-emerald-900",
  unknown: "border-slate-200 bg-slate-50 text-slate-700",
};

function formatDateTime(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function Badge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${className || "border-slate-200 bg-white text-slate-700"}`}>
      <span className="truncate">{children}</span>
    </span>
  );
}

function KpiCard({ count, label, severity }: { count: number; label: string; severity: ApprovalConsentSeverity }) {
  return (
    <div className={`rounded-lg border px-4 py-3 ${severityClasses[severity]}`}>
      <div className="text-xs font-semibold uppercase tracking-[0.12em]">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{count}</div>
    </div>
  );
}

function kindLabel(kind: ApprovalConsentItem["kind"]) {
  switch (kind) {
    case "ticket_approval":
      return "Тикет";
    case "change_approval":
      return "Изменение";
    case "risky_tool_consent":
      return "Рискованная команда";
    case "remote_assist_consent":
      return "Удалённая помощь";
    case "closure_approval":
      return "Закрытие";
    case "policy_override":
      return "Переопределение политики";
  }
}

function blockingBadges(item: ApprovalConsentItem) {
  const badges = [];
  if (item.blocking.blocks_ticket_progress) {
    badges.push("Блокирует тикет");
  }
  if (item.blocking.blocks_sla) {
    badges.push("Блокирует SLA");
  }
  if (item.blocking.blocks_operation) {
    badges.push("Блокирует операцию");
  }
  if (item.blocking.blocks_remote_assist) {
    badges.push("Ждёт пользователя");
  }
  if (item.blocking.blocks_change) {
    badges.push("Блокирует изменение");
  }
  if (item.blocking.blocks_closure) {
    badges.push("Блокирует закрытие");
  }
  return badges;
}

function ItemCard({ item }: { item: ApprovalConsentItem }) {
  const dueAt = formatDateTime(item.due_at);
  const primaryAction = item.actions.find((action) => action.href && action.enabled);
  return (
    <article className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Badge>{kindLabel(item.kind)}</Badge>
            <Badge className={riskClasses[item.risk]}>{riskLabels[item.risk]}</Badge>
            <Badge>{statusLabels[item.status]}</Badge>
            {dueAt ? <Badge>Срок: {dueAt}</Badge> : null}
          </div>
          <h2 className="mt-2 break-words text-base font-semibold text-slate-950">{item.title || "Без названия"}</h2>
        </div>
        {primaryAction?.href ? (
          <Link
            to={primaryAction.href}
            className="inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-brand-700 px-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-800"
          >
            {primaryAction.label}
          </Link>
        ) : null}
      </div>
      <p className="mt-3 break-words text-sm leading-6 text-slate-700">{item.reason}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {item.ticket_number ? <Badge>Тикет: {item.ticket_number}</Badge> : null}
        {item.change_number ? <Badge>Изменение: {item.change_number}</Badge> : null}
        {item.context.queue ? <Badge>Очередь: {item.context.queue}</Badge> : null}
        {item.context.assignee ? <Badge>Исполнитель: {item.context.assignee}</Badge> : null}
        {item.requester_name ? <Badge>Инициатор: {item.requester_name}</Badge> : null}
        {item.approver ? <Badge>Согласующий: {item.approver}</Badge> : null}
        {item.approver_group ? <Badge>Группа: {item.approver_group}</Badge> : null}
        {item.context.tool_name ? <Badge>Инструмент: {item.context.tool_name}</Badge> : null}
        {item.device_id ? <Badge>device_id: {item.device_id}</Badge> : null}
        {item.context.service_code ? <Badge>Услуга: {item.context.service_code}</Badge> : null}
      </div>
      {blockingBadges(item).length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {blockingBadges(item).map((label) => (
            <Badge key={label} className="border-red-100 bg-red-50 text-red-900">
              {label}
            </Badge>
          ))}
        </div>
      ) : null}
      {item.actions.some((action) => !action.enabled && action.disabled_reason) ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          {item.actions
            .filter((action) => !action.enabled && action.disabled_reason)
            .map((action) => `${action.label}: ${action.disabled_reason}`)
            .join("; ")}
        </div>
      ) : null}
    </article>
  );
}

function SectionCard({ section }: { section: ApprovalConsentSection }) {
  const copy = sectionCopy[section.key] ?? { title: section.title, description: section.description };
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-sm font-semibold text-slate-950">{copy.title}</h3>
          <p className="mt-1 break-words text-xs leading-5 text-slate-600">{copy.description}</p>
        </div>
        <Badge className={severityClasses[section.severity]}>{section.count}</Badge>
      </div>
    </section>
  );
}

function EmptyState() {
  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 px-6 py-8 text-emerald-950">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-1 h-6 w-6 shrink-0" />
        <div>
          <h2 className="text-xl font-semibold">Нет ожидающих согласований</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6">Ожидающие согласования, запросы согласия и переопределения политик не найдены.</p>
        </div>
      </div>
    </section>
  );
}

export function ApprovalConsentCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [scope, setScope] = useState<ApprovalConsentScope>((searchParams.get("scope") as ApprovalConsentScope) || "team");
  const [status, setStatus] = useState(searchParams.get("status") || "pending");
  const [kind, setKind] = useState(searchParams.get("kind") || "");
  const [risk, setRisk] = useState(searchParams.get("risk") || "");

  const params = useMemo<FetchApprovalConsentCenterParams>(
    () => ({
      scope,
      status: status as FetchApprovalConsentCenterParams["status"],
      kind: kind || undefined,
      risk: risk ? (risk as FetchApprovalConsentCenterParams["risk"]) : undefined,
      limit: 50,
    }),
    [kind, risk, scope, status],
  );

  const query = useQuery({
    queryKey: ["approval-consent-center", params],
    queryFn: () => fetchApprovalConsentCenter(params),
  });

  function updateQuery(next: Partial<{ scope: ApprovalConsentScope; status: string; kind: string; risk: string }>) {
    const merged = { scope, status, kind, risk, ...next };
    setScope(merged.scope);
    setStatus(merged.status);
    setKind(merged.kind);
    setRisk(merged.risk);
    const nextParams = new URLSearchParams();
    if (merged.scope !== "team") nextParams.set("scope", merged.scope);
    if (merged.status !== "pending") nextParams.set("status", merged.status);
    if (merged.kind) nextParams.set("kind", merged.kind);
    if (merged.risk) nextParams.set("risk", merged.risk);
    setSearchParams(nextParams, { replace: true });
  }

  const data = query.data;

  return (
    <main className="min-h-screen bg-app px-4 py-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="surface-panel px-5 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">Поддержка</p>
              <h1 className="mt-2 break-words font-display text-3xl font-semibold tracking-tight text-slate-950">
                Центр согласований и согласий
              </h1>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                Все ожидающие согласования, запросы согласия, рискованные действия, закрытия и переопределения политик в одном месте.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
            >
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </button>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <label className="text-xs font-semibold text-slate-600">
              Охват
              <select
                aria-label="Охват"
                value={scope}
                onChange={(event) => updateQuery({ scope: event.target.value as ApprovalConsentScope })}
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
              >
                {scopeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Статус
              <select
                aria-label="Статус"
                value={status}
                onChange={(event) => updateQuery({ status: event.target.value })}
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Тип
              <select
                aria-label="Тип"
                value={kind}
                onChange={(event) => updateQuery({ kind: event.target.value })}
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
              >
                {kindOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Риск
              <select
                aria-label="Риск"
                value={risk}
                onChange={(event) => updateQuery({ risk: event.target.value })}
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
              >
                {riskOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {data?.generated_at ? (
            <p className="mt-3 text-xs text-slate-500">Обновлено: {formatDateTime(data.generated_at) ?? data.generated_at}</p>
          ) : null}
        </header>

        {query.isError ? (
          <section className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-950">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
              <div>
                <h2 className="font-semibold">Не удалось загрузить согласования</h2>
                <p className="mt-1 text-sm">Проверьте доступ и повторите запрос.</p>
              </div>
            </div>
          </section>
        ) : null}

        {query.isLoading ? (
          <section className="rounded-xl border border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500">
            Загружаем согласования и consent-запросы...
          </section>
        ) : null}

        {data ? (
          <>
            <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              <KpiCard count={data.summary.pending_count} label="Всего ожидает" severity="warning" />
              <KpiCard count={data.summary.overdue_count} label="Просрочено" severity={data.summary.overdue_count ? "critical" : "info"} />
              <KpiCard count={data.summary.high_risk_count} label="Высокий риск" severity={data.summary.high_risk_count ? "critical" : "info"} />
              <KpiCard count={data.summary.waiting_approver_count} label="Ждёт меня" severity="warning" />
              <KpiCard count={data.summary.waiting_user_count} label="Ждёт пользователя" severity="warning" />
              <KpiCard count={data.summary.blocking_sla_count} label="Блокирует SLA" severity={data.summary.blocking_sla_count ? "critical" : "info"} />
            </section>

            <section className="grid gap-3 lg:grid-cols-5">
              {data.sections.map((section) => (
                <SectionCard key={section.key} section={section} />
              ))}
            </section>

            {data.items.length ? (
              <section className="grid gap-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-brand-700" />
                  <h2 className="text-xl font-semibold text-slate-950">Список ожиданий</h2>
                </div>
                {data.items.map((item) => (
                  <ItemCard key={item.id} item={item} />
                ))}
              </section>
            ) : (
              <EmptyState />
            )}
          </>
        ) : null}

        <footer className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <Clock3 className="h-4 w-4" />
          Первый срез работает только для просмотра: действия подтверждения и отклонения показываются только если сервер отдаёт безопасное типизированное действие.
        </footer>
      </div>
    </main>
  );
}
