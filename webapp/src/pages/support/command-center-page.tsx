import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock3,
  Inbox,
  MessageSquare,
  RefreshCcw,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

import { fetchSupportWorkspaceSummary } from "../../features/queues/api";
import {
  fetchOperatorCommandCenter,
  type CommandCenterItem,
  type CommandCenterScope,
  type CommandCenterSection,
  type CommandCenterSeverity,
  type OperatorCommandCenterPayload,
} from "../../features/operator-command-center/api";
import { buildPrioritizedAttentionList } from "../../features/operator-command-center/prioritization";

const scopeOptions: Array<{ value: CommandCenterScope; label: string }> = [
  { value: "my", label: "Мои" },
  { value: "team", label: "Команда" },
  { value: "all", label: "Все доступные" },
];

const limitOptions = [6, 8, 12, 20, 25];

const severityClasses: Record<CommandCenterSeverity, string> = {
  critical: "border-red-300 bg-red-50 text-red-900",
  warning: "border-amber-300 bg-amber-50 text-amber-900",
  info: "border-sky-300 bg-sky-50 text-sky-900",
};

const severityDotClasses: Record<CommandCenterSeverity, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
};

const mojibakeMarkers = [
  "???",
  "\uFFFD",
  "\u00D0",
  "\u00D1",
  "\u0420\u045C",
  "\u0420\u045A",
  "\u0420\u0452",
  "\u0420\u0098",
  "\u0420\u040E",
  "\u0420\u045F",
  "\u0420\u045B",
  "\u0420\u2018",
  "\u0420\u201D",
  "\u0421\u0403",
  "\u0421\u201A",
  "\u0421\u040A",
  "\u0421\u040F",
];

function displayText(value: string | null | undefined, fallback: string) {
  const text = value?.trim() ?? "";
  if (!text || mojibakeMarkers.some((marker) => text.includes(marker))) {
    return fallback;
  }
  return text;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "нет срока";
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

function formatTimer(item: CommandCenterItem) {
  const timer = item.sla?.state && item.sla.state !== "unknown" ? item.sla : item.ola;
  if (!timer?.due_at) {
    return item.next_action_due_at ? `Действие до ${formatDateTime(item.next_action_due_at)}` : null;
  }
  const label = item.sla?.state && item.sla.state !== "unknown" ? "SLA" : "OLA";
  return `${label}: ${timer.state === "breached" ? "нарушен" : "до"} ${formatDateTime(timer.due_at)}`;
}

function StatusBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex max-w-full items-center rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-600">
      <span className="truncate">{children}</span>
    </span>
  );
}

function KpiCard({
  count,
  label,
  severity,
  target,
}: {
  count: number;
  label: string;
  severity: CommandCenterSeverity;
  target: string;
}) {
  return (
    <a
      href={`#${target}`}
      className={`min-w-0 rounded-lg border px-4 py-3 transition hover:-translate-y-0.5 hover:shadow-sm ${severityClasses[severity]}`}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${severityDotClasses[severity]}`} />
        <span className="truncate text-xs font-semibold uppercase tracking-[0.12em]">{label}</span>
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{count}</div>
    </a>
  );
}

function ItemCard({ item, compact = false }: { item: CommandCenterItem; compact?: boolean }) {
  const timer = formatTimer(item);
  const title = displayText(item.title, "Без названия");
  const requester = displayText(item.requester_name, "Пользователь не указан");
  return (
    <article className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Link to={item.href} className="min-w-0 text-sm font-semibold text-brand-700 hover:text-brand-900">
              <span className="break-words">{item.ticket_number ?? item.ticket_id}</span>
            </Link>
            <StatusBadge>{item.status}</StatusBadge>
            {item.priority ? <StatusBadge>{item.priority}</StatusBadge> : null}
          </div>
          <h3 className="mt-1 break-words text-base font-semibold text-slate-950">{title}</h3>
        </div>
        <Link
          to={item.href}
          className="inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-brand-700 px-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800"
        >
          Открыть тикет
        </Link>
      </div>

      <p className="mt-3 break-words text-sm leading-6 text-slate-700">{item.reason}</p>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
        {item.queue ? <StatusBadge>Очередь: {item.queue}</StatusBadge> : null}
        {item.assignee ? <StatusBadge>Исполнитель: {item.assignee}</StatusBadge> : <StatusBadge>Без исполнителя</StatusBadge>}
        {requester ? <StatusBadge>Инициатор: {requester}</StatusBadge> : null}
        {timer ? <StatusBadge>{timer}</StatusBadge> : null}
        {item.unread_user_messages ? <StatusBadge>Сообщений: {item.unread_user_messages}</StatusBadge> : null}
        {item.service_code ? <StatusBadge>Услуга: {item.service_code}</StatusBadge> : null}
      </div>

      {!compact && item.operation?.error_summary ? (
        <p className="mt-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-900">
          Ошибка операции: {item.operation.error_summary}
        </p>
      ) : null}
      {!compact && item.agent?.connection_state ? (
        <p className="mt-2 text-xs text-slate-500">
          Агент: {item.agent.connection_state}, последнее соединение {formatDateTime(item.agent.last_seen_at)}
        </p>
      ) : null}
      {!compact && item.closure?.blocked ? (
        <p className="mt-2 text-xs text-slate-500">
          Блокер закрытия: {item.closure.primary_blocker ?? "требуются дополнительные данные"}.
        </p>
      ) : null}
      {!compact && item.similar_group ? (
        <div className="mt-3 rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          <div className="font-semibold">Похожие тикеты: {item.similar_group.count}</div>
          <div className="mt-1 break-words text-xs">Примеры: {item.similar_group.sample_ticket_ids.join(", ")}</div>
          <Link to={item.href} className="mt-2 inline-flex text-sm font-semibold text-amber-900 hover:text-amber-950">
            Открыть похожие
          </Link>
        </div>
      ) : null}
    </article>
  );
}

function SectionCard({ section }: { section: CommandCenterSection }) {
  return (
    <section id={section.key} className="scroll-mt-20 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${severityDotClasses[section.severity]}`} />
            <h2 className="break-words text-lg font-semibold text-slate-950">{section.title}</h2>
          </div>
          <p className="mt-1 break-words text-sm leading-6 text-slate-600">{section.description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-2xl font-semibold tabular-nums text-slate-950">{section.count}</span>
          {section.action ? (
            <Link to={section.action.href} className="text-sm font-semibold text-brand-700 hover:text-brand-900">
              {section.action.label}
            </Link>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3">
        {section.items.length ? (
          section.items.map((item) => <ItemCard key={item.id} item={item} />)
        ) : (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
            Сейчас нет тикетов в этой секции.
          </div>
        )}
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
          <h2 className="text-xl font-semibold">Нет срочных действий</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6">
            Новые сообщения, SLA-риск, ошибки операций и блокеры закрытия не обнаружены.
          </p>
        </div>
      </div>
    </section>
  );
}

function HeaderControls({
  data,
  scope,
  queue,
  queryDraft,
  limitPerSection,
  onScopeChange,
  onQueueChange,
  onQueryDraftChange,
  onSearchSubmit,
  onClearSearch,
  onLimitPerSectionChange,
  onRefresh,
  refreshing,
}: {
  data?: OperatorCommandCenterPayload;
  scope: CommandCenterScope;
  queue: string;
  queryDraft: string;
  limitPerSection: number;
  onScopeChange: (scope: CommandCenterScope) => void;
  onQueueChange: (queue: string) => void;
  onQueryDraftChange: (query: string) => void;
  onSearchSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClearSearch: () => void;
  onLimitPerSectionChange: (limit: number) => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const queuesQuery = useQuery({
    queryKey: ["support-workspace-summary", "command-center"],
    queryFn: () => fetchSupportWorkspaceSummary(1000),
    staleTime: 30_000,
  });
  const queues = queuesQuery.data?.queues ?? [];

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex min-w-[160px] flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
        Охват
        <select
          className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-900 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          value={scope}
          onChange={(event) => onScopeChange(event.target.value as CommandCenterScope)}
        >
          {scopeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-w-[220px] flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
        Очередь
        <select
          className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-900 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          value={queue}
          onChange={(event) => onQueueChange(event.target.value)}
        >
          <option value="">Все очереди</option>
          {queues.map((item) => (
            <option key={item.id} value={item.code ?? item.id}>
              {item.name} ({item.count})
            </option>
          ))}
        </select>
      </label>
      <form
        className="flex min-w-[260px] flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500"
        onSubmit={onSearchSubmit}
      >
        Поиск
        <div className="flex min-w-0 gap-2">
          <input
            aria-label="Поиск"
            className="h-10 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-900 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
            value={queryDraft}
            placeholder="Тикет, инициатор, услуга, устройство"
            onChange={(event) => onQueryDraftChange(event.target.value)}
          />
          <button
            type="submit"
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold normal-case tracking-normal text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <Search className="h-4 w-4" />
            Найти
          </button>
          {queryDraft ? (
            <button
              type="button"
              className="inline-flex h-10 shrink-0 items-center rounded-md px-2 text-sm font-semibold normal-case tracking-normal text-slate-500 transition hover:text-slate-900"
              onClick={onClearSearch}
            >
              Сбросить
            </button>
          ) : null}
        </div>
      </form>
      <label className="flex min-w-[150px] flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
        Показывать
        <select
          className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-900 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          value={limitPerSection}
          onChange={(event) => onLimitPerSectionChange(Number(event.target.value))}
        >
          {limitOptions.map((value) => (
            <option key={value} value={value}>
              {value} в секции
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60"
        onClick={onRefresh}
        disabled={refreshing}
      >
        <RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        Обновить
      </button>
      <span className="text-xs text-slate-500">
        Обновлено: {data ? formatDateTime(data.generated_at) : "загрузка"}
      </span>
    </div>
  );
}

export function SupportCommandCenterPage() {
  const [scope, setScope] = useState<CommandCenterScope>("team");
  const [queue, setQueue] = useState("");
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [limitPerSection, setLimitPerSection] = useState(8);
  const commandCenterQuery = useQuery({
    queryKey: ["operator-command-center", scope, queue, query, limitPerSection],
    queryFn: () =>
      fetchOperatorCommandCenter({
        scope,
        queue: queue || undefined,
        query: query || undefined,
        limit_per_section: limitPerSection,
        window_hours: 24,
        sla_risk_minutes: 120,
        ola_risk_minutes: 60,
      }),
    refetchOnWindowFocus: false,
  });
  const data = commandCenterQuery.data;
  const prioritizedItems = useMemo(
    () => buildPrioritizedAttentionList(data?.sections ?? [], 10),
    [data?.sections],
  );
  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(queryDraft.trim());
  };
  const handleClearSearch = () => {
    setQueryDraft("");
    setQuery("");
  };

  return (
    <main className="min-h-screen bg-app px-4 py-5 text-slate-900 md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1760px] flex-col gap-5">
        <header className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Поддержка</p>
              <h1 className="mt-2 break-words text-3xl font-semibold tracking-tight text-slate-950">Рабочий центр</h1>
              <p className="mt-2 max-w-4xl break-words text-sm leading-6 text-slate-600">
                Что требует внимания сейчас: SLA, сообщения пользователей, согласования, операции и блокеры закрытия.
              </p>
            </div>
            <HeaderControls
              data={data}
              scope={scope}
              queue={queue}
              queryDraft={queryDraft}
              limitPerSection={limitPerSection}
              onScopeChange={setScope}
              onQueueChange={setQueue}
              onQueryDraftChange={setQueryDraft}
              onSearchSubmit={handleSearchSubmit}
              onClearSearch={handleClearSearch}
              onLimitPerSectionChange={setLimitPerSection}
              onRefresh={() => void commandCenterQuery.refetch()}
              refreshing={commandCenterQuery.isFetching}
            />
          </div>
          {data?.metadata?.scope_fallback_reason ? (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
              Запрошенный охват недоступен для текущей роли, показана доступная командная область.
            </div>
          ) : null}
        </header>

        {commandCenterQuery.isError ? (
          <section className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-950">
            <div className="flex gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
              <div>
                <h2 className="font-semibold">Не удалось загрузить рабочий центр</h2>
                <p className="mt-1 text-sm">Проверьте доступ к support API и повторите обновление.</p>
              </div>
            </div>
          </section>
        ) : null}

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <KpiCard count={data?.summary.critical_count ?? 0} label="Критично" severity="critical" target="attention-first" />
          <KpiCard count={data?.summary.warning_count ?? 0} label="Предупреждения" severity="warning" target="attention-first" />
          <KpiCard count={data?.summary.new_unassigned_count ?? 0} label="Новые без владельца" severity="warning" target="new_unassigned" />
          <KpiCard count={data?.summary.unread_user_messages_count ?? 0} label="Сообщения пользователей" severity="warning" target="unread_user_messages" />
          <KpiCard count={data?.summary.sla_risk_count ?? 0} label="SLA риск" severity="critical" target="sla_risk" />
          <KpiCard count={data?.summary.failed_operation_count ?? 0} label="Операции с ошибкой" severity="critical" target="failed_operation" />
          <KpiCard count={data?.summary.closure_blocked_count ?? 0} label="Блокеры закрытия" severity="warning" target="closure_blocked" />
        </section>

        {data && data.summary.total_attention_items === 0 ? <EmptyState /> : null}

        <section id="attention-first" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-slate-950">
                <ShieldAlert className="h-5 w-5 text-red-600" />
                <h2 className="text-xl font-semibold">Сначала обработать</h2>
              </div>
              <p className="mt-1 text-sm text-slate-600">Дедуплицированный список тикетов и всплесков по приоритету.</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Clock3 className="h-4 w-4" />
              SLA, OLA, операции, сообщения, согласия
            </div>
          </div>
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {prioritizedItems.length ? (
              prioritizedItems.map((item) => (
                <article key={`priority-${item.id}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap gap-2">
                    {item.reason_badges.map((badge) => (
                      <span key={badge} className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                        {badge}
                      </span>
                    ))}
                  </div>
                  <ItemCard item={item} compact />
                </article>
              ))
            ) : (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                Нет приоритетных действий по текущему фильтру.
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          {(data?.sections ?? []).map((section) => (
            <SectionCard key={section.key} section={section} />
          ))}
          {!data && commandCenterQuery.isLoading ? (
            <div className="rounded-xl border border-slate-200 bg-white px-5 py-8 text-sm text-slate-500">
              Загружаем секции рабочего центра...
            </div>
          ) : null}
        </section>

        <footer className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
          <Inbox className="h-4 w-4" />
          <span>Это рабочий центр действий, не отчетная панель. Для обработки открывайте тикет в guided workspace.</span>
          <span className="inline-flex items-center gap-1">
            <MessageSquare className="h-4 w-4" />
            Сообщения
          </span>
          <span className="inline-flex items-center gap-1">
            <Bell className="h-4 w-4" />
            Согласования
          </span>
          <span className="inline-flex items-center gap-1">
            <Sparkles className="h-4 w-4" />
            Диагностика
          </span>
        </footer>
      </div>
    </main>
  );
}
