import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent, type ReactNode, type MouseEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock3,
  Columns3,
  FileCheck2,
  Inbox,
  ListChecks,
  MessageSquare,
  RefreshCcw,
  Search,
  ShieldAlert,
  Stethoscope,
  UserPlus,
  Wrench,
  XCircle,
} from "lucide-react";
import "./command-center.css";
import { getNextActionOwnerLabel } from "../../features/tickets/status-presentation";
import { Link } from "react-router-dom";

import { fetchSupportWorkspaceSummary, type SupportWorkspaceSummaryPayload } from "../../features/queues/api";
import {
  fetchOperatorCommandCenter,
  type CommandCenterItem,
  type CommandCenterScope,
  type CommandCenterSection,
  type CommandCenterSeverity,
  type OperatorCommandCenterPayload,
} from "../../features/operator-command-center/api";
import {
  buildSupportActionTasks,
  filterSupportActionTasks,
  groupSupportActionTasksForKanban,
  type KanbanActionColumn,
  type SupportActionTask,
  type SupportActionTaskFilter,
  type SupportActionTaskType,
} from "../../features/operator-command-center/task-projection";

type ViewMode = "inbox" | "kanban";

type ActionFilterId =
  | "all"
  | "my_work"
  | "team_queue"
  | "new_unassigned"
  | "sla_ola"
  | "sla_risk"
  | "ola_risk"
  | "unread_user_messages"
  | "operator_action"
  | "pending_approval"
  | "pending_consent"
  | "failed_operation"
  | "agent_offline_active"
  | "diagnostics_recommended"
  | "closure_blocked"
  | "similar_tickets_spike";

const scopeOptions: Array<{ value: CommandCenterScope; label: string }> = [
  { value: "my", label: "Мои" },
  { value: "team", label: "Команда" },
  { value: "all", label: "Все доступные" },
];

const limitOptions = [6, 8, 12, 20, 25];

const severityClasses: Record<CommandCenterSeverity, string> = {
  critical: "border-red-300 bg-red-50 text-red-950",
  warning: "border-amber-300 bg-amber-50 text-amber-950",
  info: "border-sky-300 bg-sky-50 text-sky-950",
};

const severityDotClasses: Record<CommandCenterSeverity, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
};

const rowSeverityClasses: Record<CommandCenterSeverity, string> = {
  critical: "border-l-red-500",
  warning: "border-l-amber-500",
  info: "border-l-sky-500",
};

const mojibakeMarkers = [
  "???",
  "\uFFFD",
  "\u00D0",
  "\u00D1",
  "Рњ",
  "Рќ",
  "Рџ",
  "РЎ",
  "Рђ",
  "Р",
  "Р‘",
  "СЃ",
  "С‚",
  "СЊ",
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

function formatTimerState(item: CommandCenterItem) {
  const timer = item.sla?.state && item.sla.state !== "unknown" ? item.sla : item.ola;
  if (!timer?.due_at) {
    return item.next_action_due_at ? `Действие до ${formatDateTime(item.next_action_due_at)}` : null;
  }
  const label = item.sla?.state && item.sla.state !== "unknown" ? "SLA" : "OLA";
  const state = timer.state === "breached" ? "просрочен" : timer.state === "risk" ? "риск" : "до";
  return `${label}: ${state} ${formatDateTime(timer.due_at)}`;
}

function countBySection(data: OperatorCommandCenterPayload | undefined, key: CommandCenterSection["key"]) {
  return data?.sections.find((section) => section.key === key)?.count ?? 0;
}

function taskTypeLabel(type: SupportActionTaskType) {
  const labels: Record<SupportActionTaskType, string> = {
    triage_unassigned: "Новое обращение",
    reply_user: "Ответ пользователю",
    sla_rescue: "Контроль SLA",
    ola_rescue: "Контроль внутренних сроков",
    operator_next_action: "Действие оператора",
    approval_followup: "Согласование",
    consent_waiting: "Согласие пользователя",
    operation_failed: "Ошибка операции",
    diagnostics_needed: "Диагностика",
    agent_offline: "Устройство не на связи",
    closure_blocker: "Блокер закрытия",
    similar_spike: "Похожие обращения",
  };
  return labels[type];
}

function filterForId(id: ActionFilterId): SupportActionTaskFilter {
  switch (id) {
    case "my_work":
      return {
        sectionKeys: [
          "unread_user_messages",
          "sla_risk",
          "ola_risk",
          "operator_action",
          "failed_operation",
          "closure_blocked",
        ],
      };
    case "team_queue":
      return {};
    case "new_unassigned":
      return { sectionKeys: ["new_unassigned"] };
    case "sla_ola":
      return { sectionKeys: ["sla_risk", "ola_risk"] };
    case "sla_risk":
      return { sectionKeys: ["sla_risk"] };
    case "ola_risk":
      return { sectionKeys: ["ola_risk"] };
    case "unread_user_messages":
      return { sectionKeys: ["unread_user_messages"] };
    case "operator_action":
      return { sectionKeys: ["operator_action"] };
    case "pending_approval":
      return { sectionKeys: ["pending_approval"] };
    case "pending_consent":
      return { sectionKeys: ["pending_consent"] };
    case "failed_operation":
      return { sectionKeys: ["failed_operation"] };
    case "agent_offline_active":
      return { sectionKeys: ["agent_offline_active"] };
    case "diagnostics_recommended":
      return { sectionKeys: ["diagnostics_recommended"] };
    case "closure_blocked":
      return { sectionKeys: ["closure_blocked"] };
    case "similar_tickets_spike":
      return { sectionKeys: ["similar_tickets_spike"] };
    case "all":
    default:
      return {};
  }
}

function statusBadgeClass(active: boolean) {
  return active
    ? "border-brand-600 bg-brand-700 text-white shadow-sm"
    : "border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:text-brand-800";
}

function StatusBadge({ children }: { children: ReactNode }) {
  return (
    <span className="support-action-badge inline-flex max-w-full items-center rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-600">
      <span className="truncate">{children}</span>
    </span>
  );
}

function hasSection(task: SupportActionTask, key: CommandCenterSection["key"]) {
  return task.sectionKeys.includes(key);
}

function sourceItem(
  task: SupportActionTask,
  predicate: (item: CommandCenterItem) => boolean,
): CommandCenterItem | null {
  return task.sourceItems.find(predicate) ?? null;
}

function taskUnreadUserMessages(task: SupportActionTask) {
  return task.sourceItems.reduce((total, item) => Math.max(total, item.unread_user_messages ?? 0), 0);
}

function taskReasons(task: SupportActionTask) {
  const reasons = task.sourceItems
    .map((item) => item.reason?.trim())
    .filter((reason): reason is string => Boolean(reason));
  return [...new Set(reasons)];
}

function HeaderControls({
  data,
  scope,
  queue,
  queryDraft,
  limitPerSection,
  summary,
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
  summary?: SupportWorkspaceSummaryPayload;
  onScopeChange: (scope: CommandCenterScope) => void;
  onQueueChange: (queue: string) => void;
  onQueryDraftChange: (query: string) => void;
  onSearchSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClearSearch: () => void;
  onLimitPerSectionChange: (limit: number) => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const queues = summary?.queues ?? [];

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex min-w-[150px] flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
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
      <label className="flex min-w-[210px] flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
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
        className="flex min-w-[280px] flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500"
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
        Источник
        <select
          className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-900 shadow-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          value={limitPerSection}
          onChange={(event) => onLimitPerSectionChange(Number(event.target.value))}
        >
          {limitOptions.map((value) => (
            <option key={value} value={value}>
              лимит секций: {value}
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
      <span className="text-xs text-slate-500">Обновлено: {data ? formatDateTime(data.generated_at) : "загрузка"}</span>
    </div>
  );
}

function TopTaskFilters({
  data,
  totalTasks,
  activeFilter,
  onFilterChange,
}: {
  data?: OperatorCommandCenterPayload;
  totalTasks: number;
  activeFilter: ActionFilterId;
  onFilterChange: (filter: ActionFilterId) => void;
}) {
  const filters: Array<{ id: ActionFilterId; label: string; count: number; severity: CommandCenterSeverity }> = [
    { id: "all", label: "Все действия", count: totalTasks, severity: "info" },
    { id: "new_unassigned", label: "Новые без владельца", count: countBySection(data, "new_unassigned"), severity: "warning" },
    { id: "sla_risk", label: "Риск SLA", count: countBySection(data, "sla_risk"), severity: "critical" },
    { id: "ola_risk", label: "Риск внутренних сроков", count: countBySection(data, "ola_risk"), severity: "critical" },
    { id: "unread_user_messages", label: "Сообщения пользователей", count: countBySection(data, "unread_user_messages"), severity: "warning" },
    { id: "operator_action", label: "Действия оператора", count: countBySection(data, "operator_action"), severity: "warning" },
    { id: "pending_approval", label: "Согласования", count: countBySection(data, "pending_approval"), severity: "warning" },
    { id: "pending_consent", label: "Согласие пользователя", count: countBySection(data, "pending_consent"), severity: "warning" },
    { id: "failed_operation", label: "Ошибки операций", count: countBySection(data, "failed_operation"), severity: "critical" },
    { id: "agent_offline_active", label: "Устройство не на связи", count: countBySection(data, "agent_offline_active"), severity: "warning" },
    { id: "diagnostics_recommended", label: "Диагностика", count: countBySection(data, "diagnostics_recommended"), severity: "info" },
    { id: "closure_blocked", label: "Блокеры закрытия", count: countBySection(data, "closure_blocked"), severity: "warning" },
    { id: "similar_tickets_spike", label: "Похожие обращения", count: countBySection(data, "similar_tickets_spike"), severity: "warning" },
  ];

  return (
    <section className="support-action-filters" aria-label="Фильтры действий">
      {filters.filter(filter => ["all", "new_unassigned", "sla_risk", "unread_user_messages", "operator_action"].includes(filter.id) || filter.count > 0 || filter.id === activeFilter).map((filter) => {
        const active = activeFilter === filter.id;
        return (
          <button
            key={filter.id}
            type="button"
            className={`inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition ${statusBadgeClass(active)}`}
            aria-pressed={active}
            onClick={() => onFilterChange(filter.id)}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${severityDotClasses[filter.severity]}`} />
            <span>{filter.label}</span>
            <span className={active ? "text-white/80" : "text-slate-500"}>{filter.count}</span>
          </button>
        );
      })}
      <details className="support-action-filters__more"><summary>Другие фильтры</summary><div>{filters.filter(filter => !["all", "new_unassigned", "sla_risk", "unread_user_messages", "operator_action"].includes(filter.id) && filter.count === 0 && filter.id !== activeFilter).map(filter => <button key={filter.id} type="button" aria-pressed={false} onClick={() => onFilterChange(filter.id)}>{filter.label} · {filter.count}</button>)}</div></details>
    </section>
  );
}

function ActionCenterLeftPane({
  summary,
  summaryUnavailable = false,
  activeFilter,
  queue,
  onFilterChange,
  onQueueChange,
}: {
  summary?: SupportWorkspaceSummaryPayload;
  summaryUnavailable?: boolean;
  activeFilter: ActionFilterId;
  queue: string;
  onFilterChange: (filter: ActionFilterId) => void;
  onQueueChange: (queue: string) => void;
}) {
  const views: Array<{ id: ActionFilterId; label: string; detail: string; icon: ReactNode }> = [
    { id: "my_work", label: "Моя работа", detail: "ответы, SLA, операции", icon: <Inbox className="h-4 w-4" /> },
    { id: "team_queue", label: "Командная очередь", detail: "все доступные действия", icon: <ListChecks className="h-4 w-4" /> },
    { id: "new_unassigned", label: "Новые без владельца", detail: summaryUnavailable ? "Сводка недоступна" : `${summary?.views.unassigned ?? 0} в сводке`, icon: <UserPlus className="h-4 w-4" /> },
    { id: "sla_ola", label: "SLA/OLA", detail: summaryUnavailable ? "Сводка недоступна" : `${summary?.views.sla_risk ?? 0} с риском SLA`, icon: <Clock3 className="h-4 w-4" /> },
    { id: "unread_user_messages", label: "Ответы пользователей", detail: summaryUnavailable ? "Сводка недоступна" : `${summary?.views.requester_replied ?? 0} в сводке`, icon: <MessageSquare className="h-4 w-4" /> },
    { id: "failed_operation", label: "Операции", detail: "ошибки и повтор", icon: <Wrench className="h-4 w-4" /> },
    { id: "pending_approval", label: "Согласования и согласия", detail: "руководитель / пользователь", icon: <Bell className="h-4 w-4" /> },
    { id: "closure_blocked", label: "Закрытие", detail: "блокеры решения", icon: <FileCheck2 className="h-4 w-4" /> },
    { id: "similar_tickets_spike", label: "Похожие обращения", detail: "возможный инцидент", icon: <ShieldAlert className="h-4 w-4" /> },
  ];

  return (
    <aside className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-3 px-1">
        <h2 className="text-sm font-semibold text-slate-950">Рабочие виды</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">Фильтры для выбора следующего действия.</p>
      </div>
      <div className="grid gap-1">
        {views.map((view) => (
          <button
            key={view.id}
            type="button"
            className={`flex min-w-0 items-center gap-3 rounded-lg border px-3 py-2 text-left transition ${statusBadgeClass(activeFilter === view.id)}`}
            onClick={() => onFilterChange(view.id)}
          >
            <span className="shrink-0">{view.icon}</span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">{view.label}</span>
              <span className={activeFilter === view.id ? "block truncate text-xs text-white/75" : "block truncate text-xs text-slate-500"}>
                {view.detail}
              </span>
            </span>
          </button>
        ))}
      </div>
      <div className="mt-5 border-t border-slate-100 pt-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <h3 className="text-sm font-semibold text-slate-950">Очереди</h3>
          {queue ? (
            <button className="text-xs font-semibold text-brand-700" type="button" onClick={() => onQueueChange("")}>
              сброс
            </button>
          ) : null}
        </div>
        <div className="grid gap-1">
          {(summary?.queues ?? []).slice(0, 12).map((item) => {
            const value = item.code ?? item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition ${statusBadgeClass(queue === value)}`}
                onClick={() => onQueueChange(value)}
              >
                <span className="min-w-0 truncate font-medium">{item.name}</span>
                <span className={queue === value ? "text-white/80" : "text-slate-500"}>{item.count}</span>
              </button>
            );
          })}
          {summary && summary.queues.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 px-3 py-3 text-sm text-slate-500">Очереди не найдены.</div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

function quickActionsForTask(task: SupportActionTask) {
  const actions = [{ label: "Открыть", href: task.href }];
  if (!task.assignee || task.taskType === "triage_unassigned") {
    actions.push({ label: "Взять", href: task.href });
  }
  if (hasSection(task, "unread_user_messages")) {
    actions.push({ label: "Ответить", href: task.href });
  }
  if (hasSection(task, "failed_operation")) {
    actions.push({ label: "Операции", href: task.href });
  }
  if (hasSection(task, "diagnostics_recommended") || hasSection(task, "agent_offline_active")) {
    actions.push({ label: "Диагностика", href: task.href });
  }
  if (hasSection(task, "closure_blocked")) {
    actions.push({ label: "Закрытие", href: task.href });
  }
  if (hasSection(task, "similar_tickets_spike")) {
    actions.push({ label: "Похожие", href: task.href });
  }
  return actions;
}

function ActionTaskRow({
  task,
  selected,
  onSelect,
  onOpenTicket,
}: {
  task: SupportActionTask;
  selected: boolean;
  onSelect: (task: SupportActionTask) => void;
  onOpenTicket?: (id: string) => void;
}) {
  const title = displayText(task.title, "Без названия");
  const requester = displayText(task.requesterName, "Пользователь не указан");
  const timer = formatTimerState(task.primaryItem);
  const unreadMessages = taskUnreadUserMessages(task);
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onSelect(task);
    }
  };

  return (
    <article
      className={`support-action-row border-l-4 ${rowSeverityClasses[task.severity]} rounded-lg border border-slate-200 bg-white px-3 py-3 shadow-sm transition hover:border-brand-200 hover:bg-slate-50 ${
        selected ? "ring-2 ring-brand-500" : ""
      }`}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={() => onSelect(task)}
      onKeyDown={handleKeyDown}
    >
      <div className="support-action-row__body">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${severityDotClasses[task.severity]}`} aria-hidden="true" />
            <span className="text-sm font-semibold text-slate-950">{task.actionLabel}</span>
            <span className="text-xs font-semibold text-brand-700">{task.ticketNumber ?? task.ticketId}</span>
            {task.priority ? <StatusBadge>{task.priority}</StatusBadge> : null}
          </div>
          <h3 className="mt-1 truncate text-sm font-semibold text-slate-950">{title}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{presentationLabel(task.reason)}</p>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap gap-1.5">
            <StatusBadge>{presentationLabel(task.queue)}</StatusBadge>
            <StatusBadge>{task.assignee ? `Исполнитель: ${task.assignee}` : "Без исполнителя"}</StatusBadge>
            <StatusBadge>{requester}</StatusBadge>
            {timer ? <StatusBadge>{timer}</StatusBadge> : null}
            {unreadMessages ? <StatusBadge>Ответ пользователя: {unreadMessages}</StatusBadge> : null}


          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {task.reasonBadges.map((badge) => (
              <span key={badge} className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                {badge}
              </span>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 xl:justify-end" onClick={(event) => event.stopPropagation()}>
          {quickActionsForTask(task).map((action) => (
            <Link
              key={action.label}
              to={action.href}
              onClick={event => openTaskTicket(event, task, onOpenTicket)}
              className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-800"
            >
              {action.label}
            </Link>
          ))}
        </div>
      </div>
    </article>
  );
}

function ActionInbox({
  tasks,
  selectedTaskId,
  onSelectTask,
  onOpenTicket,
}: {
  tasks: SupportActionTask[];
  selectedTaskId: string | null;
  onSelectTask: (task: SupportActionTask) => void;
  onOpenTicket?: (id: string) => void;
}) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Список действий</h2>
          <p className="mt-1 text-sm text-slate-600">Плотный список задач: что сделать дальше и почему это важно.</p>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">{tasks.length} действий</span>
      </div>
      <div className="mt-4 grid gap-2">
        {tasks.length ? (
          tasks.map((task) => (
            <ActionTaskRow key={task.id} task={task} selected={selectedTaskId === task.id} onSelect={onSelectTask} onOpenTicket={onOpenTicket} />
          ))
        ) : (
          <EmptyTasksState />
        )}
      </div>
    </section>
  );
}

function NextActionSummary({ tasks }: { tasks: SupportActionTask[] }) {
  const firstTask = tasks[0] ?? null;
  const slaOlaCount = tasks.filter((task) => hasSection(task, "sla_risk") || hasSection(task, "ola_risk")).length;
  const replyCount = tasks.filter((task) => hasSection(task, "unread_user_messages")).length;
  const failedOperationCount = tasks.filter((task) => hasSection(task, "failed_operation")).length;
  const diagnosticsCount = tasks.filter((task) => hasSection(task, "diagnostics_recommended") || hasSection(task, "agent_offline_active")).length;

  if (!firstTask) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <ShieldAlert className="h-4 w-4 text-brand-700" />
        <span>Нет задач после фильтра</span>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-slate-700">
      <span className={`h-2.5 w-2.5 rounded-full ${severityDotClasses[firstTask.severity]}`} />
      <span className="font-semibold text-slate-950">Сначала:</span>
      <span className="max-w-[360px] truncate font-semibold text-brand-800">
        {firstTask.actionLabel} · {firstTask.ticketNumber ?? firstTask.ticketId}
      </span>
      {slaOlaCount ? <StatusBadge>SLA/OLA: {slaOlaCount}</StatusBadge> : null}
      {replyCount ? <StatusBadge>Ответы: {replyCount}</StatusBadge> : null}
      {failedOperationCount ? <StatusBadge>Операции: {failedOperationCount}</StatusBadge> : null}
      {diagnosticsCount ? <StatusBadge>Диагностика: {diagnosticsCount}</StatusBadge> : null}
    </div>
  );
}

function KanbanActionBoard({
  columns,
  selectedTaskId,
  onSelectTask,
  onOpenTicket,
}: {
  columns: KanbanActionColumn[];
  selectedTaskId: string | null;
  onSelectTask: (task: SupportActionTask) => void;
  onOpenTicket?: (id: string) => void;
}) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Доска</h2>
          <p className="mt-1 text-sm text-slate-600">Те же действия по этапам работы. Изменения выполняются в обращении.</p>
        </div>
        <Columns3 className="h-5 w-5 text-slate-400" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {columns.map((column) => (
          <div key={column.key} className="support-action-board-column min-h-[180px] rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-950">{column.title}</h3>
              <span className="text-xs font-semibold text-slate-500">{column.tasks.length}</span>
            </div>
            <div className="grid gap-2">
              {column.tasks.map((task) => (
                <button
                  key={task.id}
                  type="button"
                  className={`support-action-board-card rounded-lg border bg-white p-3 text-left shadow-sm transition hover:border-brand-300 ${
                    selectedTaskId === task.id ? "border-brand-500 ring-2 ring-brand-400" : "border-slate-200"
                  }`}
                  onClick={() => onSelectTask(task)}
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${severityDotClasses[task.severity]}`} />
                    <span className="truncate text-xs font-semibold text-brand-700">{task.ticketNumber ?? task.ticketId}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">{displayText(task.title, "Без названия")}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">{task.actionLabel}</p>
                </button>
              ))}
              {column.tasks.length === 0 ? <div className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-xs text-slate-500">Нет задач</div> : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function openTaskTicket(event: MouseEvent<HTMLAnchorElement>, task: SupportActionTask, onOpenTicket?: (id: string) => void) {
  if (onOpenTicket && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && task.href === `/app/tickets/${task.ticketId}`) {
    event.preventDefault(); onOpenTicket(task.ticketId);
  }
}

function presentationLabel(value?: string | null) {
  const labels: Record<string, string> = { waiting_on_internal_team: "Ожидает внутреннюю группу", waiting_on_vendor: "Ожидает внешнюю сторону", waiting_on_approval: "Ожидает согласование", accepted: "Принято", scheduled: "Запланировано", servicedesk_l1: "Служба поддержки", queued: "В очереди", new: "Новое", assigned: "Назначено", in_progress: "В работе", waiting_on_user: "Ожидает пользователя", waiting_on_support: "Ожидает поддержки", resolved: "Решено", closed: "Закрыто", canceled: "Отменено", breached: "Срок нарушен", risk: "Есть риск", ok: "В срок", unknown: "Неизвестно", support: "Поддержка", requester: "Пользователь", operator: "Оператор", user: "Пользователь", online: "На связи", offline: "Нет связи", connected: "Подключён", disconnected: "Не подключён", requester_denied: "Пользователь отказал", failed: "Ошибка" };
  return value ? labels[value] ?? value.replaceAll("_", " ") : "Не указано";
}

function TicketBriefingPanel({ task, onOpenTicket }: { task: SupportActionTask | null; onOpenTicket?: (id: string) => void }) {
  if (!task) return <aside className="support-action-brief" aria-label="Сводка действия"><p>Выберите действие, чтобы увидеть причину и открыть обращение.</p></aside>;
  const item = task.primaryItem;
  const reasons = taskReasons(task);
  const operation = sourceItem(task, source => Boolean(source.operation?.error_summary))?.operation;
  const agent = sourceItem(task, source => Boolean(source.agent?.connection_state))?.agent;
  const diagnostics = sourceItem(task, source => Boolean(source.diagnostics?.recommended))?.diagnostics;
  const closure = sourceItem(task, source => Boolean(source.closure?.blocked))?.closure;
  const similar = sourceItem(task, source => Boolean(source.similar_group))?.similar_group;
  return <aside className="support-action-brief" aria-label="Сводка действия">
    <div className="support-action-brief__title"><div><p>{taskTypeLabel(task.taskType)}</p><h2>{task.ticketNumber ?? "Обращение"}</h2></div><StatusBadge>{task.priority ?? "Без приоритета"}</StatusBadge></div>
    <h3>{displayText(task.title, "Без названия")}</h3>
    <div className="support-action-brief__badges"><StatusBadge>{presentationLabel(task.status)}</StatusBadge><StatusBadge>{task.assignee ?? "Без исполнителя"}</StatusBadge></div>
    <BriefingBlock title="Почему нужно действие"><ul>{(reasons.length ? reasons : [task.reason]).map(reason => <li key={reason}>{presentationLabel(reason)}</li>)}</ul></BriefingBlock>
    <dl className="support-action-brief__facts"><BriefingRow label="Инициатор" value={displayText(task.requesterName, "Не указан")} /><BriefingRow label="Следующий шаг" value={getNextActionOwnerLabel(item.next_action_owner)} />
      <BriefingRow label="SLA" value={item.sla?.due_at ? `${presentationLabel(item.sla.state)} · ${formatDateTime(item.sla.due_at)}` : "Нет данных"} />
      {item.ola?.due_at ? <BriefingRow label="Внутренний срок" value={`${presentationLabel(item.ola.state)} · ${formatDateTime(item.ola.due_at)}`} /> : null}</dl>
    <Link to={task.href} onClick={event => openTaskTicket(event, task, onOpenTicket)} className="simple-button simple-button--primary support-action-brief__open">Открыть обращение</Link>
    <details><summary>Подробности действия</summary><div className="support-action-brief__details">
      <BriefingRow label="Очередь" value={presentationLabel(task.queue)} />
      <BriefingRow label="Услуга" value={presentationLabel(task.offeringCode ?? task.serviceCode)} />
      {item.next_action_due_at ? <BriefingRow label="Действие до" value={formatDateTime(item.next_action_due_at)} /> : null}
      {operation?.error_summary ? <BriefingBlock title="Ошибка операции"><p>{presentationLabel(operation.error_summary)}</p></BriefingBlock> : null}
      {agent?.connection_state ? <BriefingBlock title="Связь с устройством"><p>{presentationLabel(agent.connection_state)} · {formatDateTime(agent.last_seen_at)}</p></BriefingBlock> : null}
      {diagnostics?.recommended ? <BriefingBlock title="Диагностика"><p>{presentationLabel(diagnostics.reason ?? diagnostics.profile_code)}</p></BriefingBlock> : null}
      {closure?.blocked ? <BriefingBlock title="Мешает закрытию"><p>{presentationLabel(closure.primary_blocker) || "Проверьте требования закрытия"}</p></BriefingBlock> : null}
      {similar ? <BriefingBlock title="Похожие обращения"><p>{similar.count} за {similar.window_hours} ч. {similar.reason}</p></BriefingBlock> : null}
    </div></details>
  </aside>;
}

function BriefingBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</h4>
      <div className="mt-1">{children}</div>
    </section>
  );
}

function BriefingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function EmptyTasksState() {
  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-6 text-emerald-950">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-1 h-5 w-5 shrink-0" />
        <div>
          <h2 className="text-lg font-semibold">Нет срочных действий</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6">По текущему фильтру нет задач. Можно расширить охват или открыть командную очередь.</p>
        </div>
      </div>
    </section>
  );
}

function ErrorState() {
  return (
    <section className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-950">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <h2 className="font-semibold">Не удалось загрузить Центр действий</h2>
          <p className="mt-1 text-sm">Проверьте подключение и повторите обновление.</p>
        </div>
      </div>
    </section>
  );
}

export function SupportCommandCenterPage({ embedded = false, search = "", queueCode = "", onOpenTicket }: { embedded?: boolean; search?: string; queueCode?: string; onOpenTicket?: (id: string) => void } = {}) {
  const [scope, setScope] = useState<CommandCenterScope>("team");
  const [queue, setQueue] = useState("");
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [limitPerSection, setLimitPerSection] = useState(embedded ? 25 : 8);
  const [activeFilter, setActiveFilter] = useState<ActionFilterId>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("inbox");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["support-workspace-summary", "command-center"],
    queryFn: () => fetchSupportWorkspaceSummary(1000),
    staleTime: 30_000,
    enabled: !embedded,
  });

  const effectiveQuery = embedded ? search.trim() : query;
  const effectiveQueue = embedded ? queueCode : queue;
  const commandCenterQuery = useQuery({
    queryKey: ["operator-command-center", scope, effectiveQueue, effectiveQuery, limitPerSection],
    queryFn: () =>
      fetchOperatorCommandCenter({
        scope,
        queue: effectiveQueue || undefined,
        query: effectiveQuery || undefined,
        limit_per_section: limitPerSection,
        window_hours: 24,
        sla_risk_minutes: 120,
        ola_risk_minutes: 60,
      }),
    refetchOnWindowFocus: false,
    retry: false,
  });

  const data = commandCenterQuery.data;
  const tasks = useMemo(() => buildSupportActionTasks(data?.sections ?? []), [data?.sections]);
  const activeTaskFilter = useMemo(() => filterForId(activeFilter), [activeFilter]);
  const filteredTasks = useMemo(() => filterSupportActionTasks(tasks, activeTaskFilter), [tasks, activeTaskFilter]);
  const kanbanColumns = useMemo(() => groupSupportActionTasksForKanban(filteredTasks), [filteredTasks]);
  const selectedTask = filteredTasks.find((task) => task.id === selectedTaskId) ?? null;

  useEffect(() => {
    if (selectedTaskId && !filteredTasks.some((task) => task.id === selectedTaskId)) {
      setSelectedTaskId(null);
    }
  }, [filteredTasks, selectedTaskId]);

  useEffect(() => {
    if (!selectedTaskId && filteredTasks.length > 0) {
      setSelectedTaskId(filteredTasks[0].id);
    }
  }, [filteredTasks, selectedTaskId]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(queryDraft.trim());
  };

  const handleClearSearch = () => {
    setQueryDraft("");
    setQuery("");
  };

  const refreshAll = () => {
    void commandCenterQuery.refetch();
    if (!embedded) void summaryQuery.refetch();
  };

  if (embedded) return <section className="simple-actions" aria-label="Действия очереди">
    <div className="simple-actions__controls">
      <label>Показывать<select aria-label="Охват действий" value={scope} onChange={event => setScope(event.target.value as CommandCenterScope)}>{scopeOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <div className="simple-tabs" aria-label="Режим действий"><button type="button" aria-pressed={viewMode === "inbox"} onClick={() => setViewMode("inbox")}>Список</button><button type="button" aria-pressed={viewMode === "kanban"} onClick={() => setViewMode("kanban")}>Доска</button></div>
      <button className="simple-button" type="button" disabled={commandCenterQuery.isFetching} onClick={refreshAll}><RefreshCcw size={14} aria-hidden />Обновить действия</button>
      <details><summary>Параметры списка</summary><label>На категорию<select aria-label="Действий на категорию" value={limitPerSection} onChange={event => setLimitPerSection(Number(event.target.value))}>{limitOptions.map(limit => <option key={limit} value={limit}>{limit}</option>)}</select></label></details>
    </div>
    {data?.metadata?.scope_fallback_reason ? <p role="status" className="simple-notice">Охват ограничен вашей ролью: показаны доступные действия команды.</p> : null}
    {commandCenterQuery.isError ? <p role="alert" className="simple-notice simple-risk">{data ? "Не удалось обновить действия. Показаны ранее загруженные данные." : "Не удалось загрузить действия. Попробуйте обновить список."}</p> : null}
    {data ? <><TopTaskFilters data={data} totalTasks={tasks.length} activeFilter={activeFilter} onFilterChange={setActiveFilter} />
      <p className="simple-actions__source">Сводка действий: {tasks.length}. В каждой категории — до {limitPerSection}; счётчики категорий могут включать одни и те же обращения. Обновлено: {formatDateTime(data.generated_at)}.</p></> : null}
    {!data && commandCenterQuery.isPending ? <p role="status" className="simple-empty">Загружаем действия…</p> : null}
    {data ? <div className="simple-actions__workspace"><div className="simple-actions__list"><NextActionSummary tasks={filteredTasks} />
      {viewMode === "inbox" ? <ActionInbox tasks={filteredTasks} selectedTaskId={selectedTaskId} onSelectTask={task => setSelectedTaskId(task.id)} onOpenTicket={onOpenTicket} /> : <KanbanActionBoard columns={kanbanColumns} selectedTaskId={selectedTaskId} onSelectTask={task => setSelectedTaskId(task.id)} onOpenTicket={onOpenTicket} />}
    </div><TicketBriefingPanel task={selectedTask} onOpenTicket={onOpenTicket} /></div> : null}
  </section>;

  return (
    <main className="min-h-screen bg-app px-4 py-5 text-slate-900 md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1760px] flex-col gap-5">
        <header className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Поддержка</p>
              <h1 className="mt-2 break-words text-3xl font-semibold tracking-tight text-slate-950">Центр действий</h1>
              <p className="mt-2 max-w-4xl break-words text-sm leading-6 text-slate-600">
                Рабочее место оператора: что сделать дальше, почему это важно, кому принадлежит задача и как открыть обращение.
              </p>
            </div>
            <HeaderControls
              data={data}
              scope={scope}
              queue={queue}
              queryDraft={queryDraft}
              limitPerSection={limitPerSection}
              summary={summaryQuery.data}
              onScopeChange={setScope}
              onQueueChange={setQueue}
              onQueryDraftChange={setQueryDraft}
              onSearchSubmit={handleSearchSubmit}
              onClearSearch={handleClearSearch}
              onLimitPerSectionChange={setLimitPerSection}
              onRefresh={refreshAll}
              refreshing={commandCenterQuery.isFetching || summaryQuery.isFetching}
            />
          </div>
          {data?.metadata?.scope_fallback_reason ? (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
              Запрошенный охват недоступен для текущей роли, показана доступная командная область.
            </div>
          ) : null}
        </header>

        {commandCenterQuery.isError ? <ErrorState /> : null}
        {summaryQuery.isError ? (
          <div role="alert" className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            Не удалось загрузить сводку рабочего пространства. Повторите попытку позже.
          </div>
        ) : null}

        {data ? <TopTaskFilters data={data} totalTasks={tasks.length} activeFilter={activeFilter} onFilterChange={setActiveFilter} /> : null}

        <section className="grid gap-4 xl:grid-cols-[280px_minmax(520px,1fr)_400px] 2xl:grid-cols-[300px_minmax(620px,1fr)_440px]">
          <ActionCenterLeftPane
            summary={summaryQuery.data}
            summaryUnavailable={summaryQuery.isLoadingError}
            activeFilter={activeFilter}
            queue={queue}
            onFilterChange={setActiveFilter}
            onQueueChange={setQueue}
          />
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              {commandCenterQuery.isLoadingError ? (
                <span className="text-sm text-slate-600">Данные Центра действий недоступны</span>
              ) : <NextActionSummary tasks={filteredTasks} />}
              <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1" aria-label="Режим просмотра">
                <button
                  type="button"
                  className={`inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm font-semibold ${viewMode === "inbox" ? "bg-white text-brand-800 shadow-sm" : "text-slate-600"}`}
                  onClick={() => setViewMode("inbox")}
                >
                  <ListChecks className="h-4 w-4" />
                  Список
                </button>
                <button
                  type="button"
                  className={`inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm font-semibold ${viewMode === "kanban" ? "bg-white text-brand-800 shadow-sm" : "text-slate-600"}`}
                  onClick={() => setViewMode("kanban")}
                >
                  <Columns3 className="h-4 w-4" />
                  Доска
                </button>
              </div>
            </div>
            {commandCenterQuery.isLoadingError ? null : viewMode === "inbox" ? (
              <ActionInbox tasks={filteredTasks} selectedTaskId={selectedTaskId} onSelectTask={(task) => setSelectedTaskId(task.id)} />
            ) : (
              <KanbanActionBoard columns={kanbanColumns} selectedTaskId={selectedTaskId} onSelectTask={(task) => setSelectedTaskId(task.id)} />
            )}
            {!data && commandCenterQuery.isLoading ? (
              <div className="rounded-xl border border-slate-200 bg-white px-5 py-8 text-sm text-slate-500">Загружаем Центр действий...</div>
            ) : null}
          </div>
          <TicketBriefingPanel task={selectedTask} onOpenTicket={onOpenTicket} />
        </section>

        <footer className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600">
          <Inbox className="h-4 w-4" />
          <span>Сложные действия и подтверждения выполняются в карточке обращения.</span>
          <span className="inline-flex items-center gap-1">
            <MessageSquare className="h-4 w-4" />
            Сообщения
          </span>
          <span className="inline-flex items-center gap-1">
            <Stethoscope className="h-4 w-4" />
            Диагностика
          </span>
          <span className="inline-flex items-center gap-1">
            <XCircle className="h-4 w-4" />
            Блокеры
          </span>
        </footer>
      </div>
    </main>
  );
}
