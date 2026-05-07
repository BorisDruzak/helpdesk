import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  BookOpen,
  Building2,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  Clock3,
  Cpu,
  FileCheck2,
  Fingerprint,
  Inbox,
  Lock,
  Mail,
  MapPin,
  MessageSquare,
  Monitor,
  MoreHorizontal,
  Moon,
  Network,
  Paperclip,
  Phone,
  Play,
  Printer,
  RefreshCcw,
  Search,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Star,
  Sun,
  Tags,
  type LucideIcon,
  UserRound,
  UsersRound,
  Wrench,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createSupportTicketPassportEvidence,
  fetchSupportQueue,
  fetchSupportTicketPassportEvidenceCandidates,
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
  linkSupportTicketPassportEvidence,
  postSupportOperationCancel,
  postSupportOperationRetry,
  postSupportTicketAssign,
  postSupportTicketMessage,
  postSupportTicketPlaybookRun,
  postSupportTicketPriority,
  postSupportTicketQueue,
  postSupportTicketReroute,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  postSupportTicketWorklog,
  type SupportQueueScope,
  type SupportTicketEvidenceCandidatePayload,
  type SupportTicketTimelineFilter,
} from "../../features/queues/api";
import {
  mapSupportTimelineEntries,
  mapSupportWorkspaceViewModel,
} from "../../features/queues/support-workspace-mappers";
import { operationActionReasonSentence } from "../../features/queues/support-workspace-labels";
import type {
  SupportWorkspacePassport,
  SupportWorkspaceClosurePlan,
  SupportWorkspaceOperationSummary,
  SupportWorkspaceQueue,
  SupportWorkspaceSlice,
  SupportWorkspaceTimer,
  SupportWorkspaceTimelineKind,
  SupportWorkspaceToolItem,
} from "../../features/queues/support-workspace-model";
import { useSession } from "../../features/auth/session-provider";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

type ComposerMode = "public" | "internal";
type SidebarTab = "context" | "sla" | "tools" | "knowledge" | "passport";
type TimelineFilter = "all" | SupportWorkspaceTimelineKind;
type SupportWorkspaceTheme = "dark" | "light";
type OperatorActionKind = "status" | "assign_self" | "queue" | "priority" | "reroute";

type OperatorActionDraft = {
  kind: OperatorActionKind;
  targetStatus: string;
  queueId: number | null;
  priority: "P0" | "P1" | "P2" | "P3";
  reason: string;
  comment: string;
};

type ClosurePlanBlocker = SupportWorkspaceClosurePlan["blockers"][number];

const CLOSURE_BLOCKER_VISIBLE_LIMIT = 4;
const SUPPORT_WORKSPACE_THEME_STORAGE_KEY = "support-workspace-theme";

function getInitialSupportWorkspaceTheme(): SupportWorkspaceTheme {
  if (typeof window === "undefined") {
    return "dark";
  }
  return window.localStorage.getItem(SUPPORT_WORKSPACE_THEME_STORAGE_KEY) === "light" ? "light" : "dark";
}

const sliceIcons: Record<SupportWorkspaceSlice["icon"], typeof Inbox> = {
  alert: AlertTriangle,
  inbox: Inbox,
  message: MessageSquare,
  spark: Sparkles,
  user: UserRound,
};

const queueIcons: Record<SupportWorkspaceQueue["icon"], typeof Inbox> = {
  layers: ClipboardList,
  monitor: Wrench,
  network: Network,
  printer: Printer,
  server: Server,
  shield: ShieldCheck,
};

const sidebarTabs: Array<{ value: SidebarTab; label: string }> = [
  { value: "context", label: "Контекст" },
  { value: "sla", label: "SLA" },
  { value: "tools", label: "Инструменты" },
  { value: "knowledge", label: "Знания" },
  { value: "passport", label: "Паспорт" },
];

const timelineTabs: Array<{ value: TimelineFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "message", label: "Сообщения" },
  { value: "internal", label: "Внутреннее" },
  { value: "diagnostics", label: "Диагностика" },
  { value: "history", label: "История" },
];

type WorkspaceErrorState = {
  title: string;
  body: string;
  actionLabel: string;
  action: "queue" | "retry";
  tone: "warning" | "danger";
};

function getErrorStatus(error: unknown): number | null {
  if (typeof error === "object" && error !== null && "status" in error) {
    const status = (error as { status?: unknown }).status;
    return typeof status === "number" ? status : null;
  }
  return null;
}

function classifyWorkspaceError(error: unknown): WorkspaceErrorState {
  const status = getErrorStatus(error);
  const message = error instanceof Error ? error.message : "Не удалось загрузить тикет";
  const normalized = message.toLowerCase();

  if (status === 404 || normalized.includes("404") || normalized.includes("not found") || normalized.includes("не найден")) {
    return {
      title: "Тикет не найден",
      body: "Он мог быть закрыт, удалён или недоступен в текущей очереди.",
      actionLabel: "Вернуться к очереди",
      action: "queue",
      tone: "warning",
    };
  }

  if (
    status === 403 ||
    normalized.includes("403") ||
    normalized.includes("forbidden") ||
    normalized.includes("permission") ||
    normalized.includes("недостаточно прав") ||
    normalized.includes("доступ запрещ")
  ) {
    return {
      title: "Недостаточно прав",
      body: "У вашей роли нет доступа к этому тикету или внутренним данным.",
      actionLabel: "Вернуться к очереди",
      action: "queue",
      tone: "danger",
    };
  }

  return {
    title: "Не удалось загрузить тикет",
    body: message,
    actionLabel: "Повторить",
    action: "retry",
    tone: "danger",
  };
}

function getTimelineEmptyState(filter: TimelineFilter): { title: string; body: string; actionLabel: string | null } {
  if (filter === "all") {
    return {
      title: "В таймлайне пока нет событий",
      body: "Новые сообщения, диагностика и системные изменения появятся здесь.",
      actionLabel: null,
    };
  }

  const label = timelineTabs.find((tab) => tab.value === filter)?.label ?? "выбранный фильтр";
  return {
    title: `Нет событий: ${label}`,
    body: "Смените фильтр или откройте все события таймлайна.",
    actionLabel: "Показать все события",
  };
}

const priorityActionOptions: Array<{ value: "P0" | "P1" | "P2" | "P3"; label: string; hint: string }> = [
  { value: "P0", label: "P0", hint: "Критичный инцидент" },
  { value: "P1", label: "P1", hint: "Высокий приоритет" },
  { value: "P2", label: "P2", hint: "Обычный приоритет" },
  { value: "P3", label: "P3", hint: "Низкий приоритет" },
];

const operatorActionLabels: Record<OperatorActionKind, { title: string; submit: string; description: string }> = {
  assign_self: {
    title: "Назначить на себя",
    submit: "Назначить",
    description: "Тикет будет назначен на текущего оператора. Укажите причину для истории действий.",
  },
  priority: {
    title: "Изменить приоритет",
    submit: "Изменить",
    description: "Выберите новый приоритет и укажите причину ручного изменения.",
  },
  queue: {
    title: "Сменить очередь",
    submit: "Переместить",
    description: "Выберите целевую очередь. Backend сохранит routing lock и пересчитает состояние очереди штатным сервисом.",
  },
  reroute: {
    title: "Пересчитать маршрут",
    submit: "Пересчитать",
    description: "Маршрут будет пересчитан текущими правилами routing. Причина попадёт в audit/timeline payload.",
  },
  status: {
    title: "Сменить статус",
    submit: "Применить статус",
    description: "Переход пройдёт через workflow, approval и closure guards. Для оператора сохранится причина.",
  },
};

function makeOperatorActionDraft(
  kind: OperatorActionKind,
  options: {
    currentPriority?: string | null;
    firstQueueId?: number | null;
    firstStatus?: string | null;
  },
): OperatorActionDraft {
  const normalizedPriority = priorityActionOptions.some((item) => item.value === options.currentPriority)
    ? (options.currentPriority as "P0" | "P1" | "P2" | "P3")
    : "P1";
  return {
    kind,
    targetStatus: options.firstStatus ?? "",
    queueId: options.firstQueueId ?? null,
    priority: normalizedPriority === "P0" ? "P1" : "P0",
    reason: "",
    comment: "",
  };
}

type ContextInfoRowProps = {
  icon: LucideIcon;
  label: string;
  value: number | string | null | undefined;
};

function ContextInfoRow({ icon: Icon, label, value }: ContextInfoRowProps) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return (
    <div className="flex items-start gap-2 rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
      <div className="min-w-0 flex-1">
        <dt className="text-xs text-slate-500">{label}</dt>
        <dd className="mt-0.5 break-words text-sm text-slate-200">{value}</dd>
      </div>
    </div>
  );
}

function toneClasses(tone: string) {
  switch (tone) {
    case "danger":
      return "border-red-400/50 bg-red-500/10 text-red-200";
    case "warning":
      return "border-amber-400/50 bg-amber-500/10 text-amber-100";
    case "success":
      return "border-emerald-400/40 bg-emerald-500/10 text-emerald-100";
    case "brand":
    case "info":
      return "border-blue-400/40 bg-blue-500/10 text-blue-100";
    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
}

function progressTone(status: string) {
  if (status === "breached") {
    return "bg-red-400";
  }
  if (status === "at_risk") {
    return "bg-amber-400";
  }
  if (status === "paused" || status === "unknown") {
    return "bg-slate-500";
  }
  return "bg-emerald-400";
}

function timerStatusLabel(status: SupportWorkspaceTimer["status"]) {
  switch (status) {
    case "breached":
      return "Нарушен";
    case "at_risk":
      return "Риск";
    case "paused":
      return "Пауза";
    case "ok":
      return "В норме";
    default:
      return "Нет срока";
  }
}

function timerStatusRing(status: SupportWorkspaceTimer["status"]) {
  switch (status) {
    case "breached":
      return "ring-1 ring-red-400/40";
    case "at_risk":
      return "ring-1 ring-amber-400/35";
    case "paused":
      return "ring-1 ring-slate-400/25";
    case "ok":
      return "ring-1 ring-emerald-400/25";
    default:
      return "";
  }
}

function formatDueLabel(dueAt: string | null) {
  if (!dueAt) {
    return "Срок не задан";
  }
  const date = new Date(dueAt);
  if (Number.isNaN(date.getTime())) {
    return "Срок не задан";
  }
  return `Срок: ${date.toLocaleString("ru-RU", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  })}`;
}

function passportStatusLabel(passport: SupportWorkspacePassport) {
  if (passport.total > 0 && passport.done >= passport.total) {
    return "Готов";
  }
  if (passport.done === 0) {
    return "Не готов";
  }
  return "В работе";
}

function passportStatusTone(passport: SupportWorkspacePassport) {
  if (passport.total > 0 && passport.done >= passport.total) {
    return "success";
  }
  if (passport.done === 0) {
    return "warning";
  }
  return "info";
}

function passportProgress(passport: SupportWorkspacePassport) {
  if (!passport.total) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((passport.done / passport.total) * 100)));
}

function closureBlockerSeverityRank(blocker: ClosurePlanBlocker) {
  if (blocker.severity === "blocking") {
    return 0;
  }
  if (blocker.severity === "warning") {
    return 1;
  }
  return 2;
}

function closureBlockerActionRank(blocker: ClosurePlanBlocker) {
  switch (blocker.actionKind) {
    case "attach_evidence":
      return 0;
    case "add_worklog":
      return 1;
    case "check_approval":
      return 2;
    case "edit_resolution":
      return 3;
    case "open_passport":
      return 4;
    default:
      return 5;
  }
}

function orderClosureBlockers(blockers: ClosurePlanBlocker[]) {
  return blockers
    .map((blocker, index) => ({ blocker, index }))
    .sort((left, right) => {
      const severityDelta = closureBlockerSeverityRank(left.blocker) - closureBlockerSeverityRank(right.blocker);
      if (severityDelta !== 0) {
        return severityDelta;
      }
      const actionDelta = closureBlockerActionRank(left.blocker) - closureBlockerActionRank(right.blocker);
      if (actionDelta !== 0) {
        return actionDelta;
      }
      return left.index - right.index;
    })
    .map((entry) => entry.blocker);
}

function closureFocusGuide(blocker: ClosurePlanBlocker) {
  switch (blocker.actionKind) {
    case "attach_evidence":
      return {
        section: "Evidence",
        targetAction: "Приложить evidence",
        hint: "Приложите подтверждение или выберите подходящий evidence-кандидат перед закрытием.",
        passportItemKey: "verified_and_closed",
      };
    case "add_worklog":
      return {
        section: "Worklog",
        targetAction: "Зафиксировать worklog",
        hint: "Добавьте запись о выполненной работе, чтобы следующий оператор видел контекст.",
        passportItemKey: "verified_and_closed",
      };
    case "edit_resolution":
      return {
        section: "Решение",
        targetAction: "Заполнить решение",
        hint: "Заполните код решения и итог для заявителя перед переводом тикета в решение.",
        passportItemKey: "solution_applied",
      };
    case "check_approval":
      return {
        section: "Согласование",
        targetAction: "Проверить согласование",
        hint: "Проверьте решение согласующего и зафиксируйте его в истории тикета.",
        passportItemKey: "verified_and_closed",
      };
    default:
      return {
        section: "Паспорт",
        targetAction: blocker.actionLabel,
        hint: "Проверьте требование в паспорте решения перед закрытием тикета.",
        passportItemKey: null,
      };
  }
}

function toolIcon(item: SupportWorkspaceToolItem) {
  if (item.id.includes("dns")) {
    return Network;
  }
  if (item.id.includes("playbook") || item.id.includes("diagnose")) {
    return Sparkles;
  }
  return Wrench;
}

function operationResultTextClass(operation: { statusTone: string }) {
  if (operation.statusTone === "success") {
    return "text-emerald-200";
  }
  if (operation.statusTone === "danger") {
    return "text-red-200";
  }
  if (operation.statusTone === "warning") {
    return "text-amber-200";
  }
  return "text-slate-200";
}

function diagnosticStepStatusLabel(status: string) {
  switch (status) {
    case "ok":
    case "success":
    case "succeeded":
      return "OK";
    case "error":
    case "failed":
      return "Ошибка";
    case "partial":
      return "Частично";
    case "skipped":
      return "Пропущено";
    default:
      return status || "Неизвестно";
  }
}

function diagnosticStepTextClass(status: string) {
  if (status === "ok" || status === "success" || status === "succeeded") {
    return "text-emerald-200";
  }
  if (status === "error" || status === "failed") {
    return "text-red-200";
  }
  return "text-amber-200";
}

function OperationSummaryCard({
  isCanceling = false,
  isRetrying = false,
  onCancel,
  onRetry,
  operation,
}: {
  isCanceling?: boolean;
  isRetrying?: boolean;
  onCancel?: (operationId: string) => void;
  onRetry?: (operationId: string) => void;
  operation: SupportWorkspaceOperationSummary;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{operation.title}</p>
          <p className="mt-1 text-xs text-slate-500">
            Старт: {operation.queuedOrStartedLabel}
            {operation.finishedLabel ? ` · Завершение: ${operation.finishedLabel}` : ""}
          </p>
        </div>
        <span className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(operation.statusTone)}`}>
          {operation.statusLabel}
        </span>
      </div>
      {operation.summary ? <p className="mt-2 break-all text-xs leading-5 text-slate-400">{operation.summary}</p> : null}
      {operation.metaLabels.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {operation.metaLabels.slice(0, 5).map((label) => (
            <span className="max-w-full break-all rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-slate-400" key={`${operation.id}:${label}`}>
              {label}
            </span>
          ))}
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {operation.detailsUrl ? (
          <a
            className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-semibold text-slate-200 hover:text-white"
            href={operation.detailsUrl}
            rel="noreferrer"
            target="_blank"
            title="Открыть технические детали операции в API"
          >
            Детали операции
          </a>
        ) : null}
        {operation.canCancel ? (
          <button
            className="rounded-md border border-red-300/25 bg-red-500/10 px-2 py-1 text-[11px] font-semibold text-red-100 hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isCanceling || !onCancel}
            onClick={() => onCancel?.(operation.id)}
            title="Отправить запрос на отмену running/queued операции"
            type="button"
          >
            {isCanceling ? "Отменяем..." : "Отменить операцию"}
          </button>
        ) : null}
        {!operation.canCancel && operation.active ? (
          <span
            className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] font-semibold text-slate-400"
            title={operationActionReasonSentence(operation.cancelDisabledReason)}
          >
            Отмена недоступна
          </span>
        ) : null}
        {operation.canRetry ? (
          <button
            className="rounded-md border border-amber-300/25 bg-amber-500/10 px-2 py-1 text-[11px] font-semibold text-amber-100 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isRetrying || !onRetry}
            onClick={() => onRetry?.(operation.id)}
            title="Повторить операцию через policy-aware retry"
            type="button"
          >
            Повторить
          </button>
        ) : operation.retryable ? (
          <span
            className="rounded-md border border-amber-300/20 bg-amber-500/10 px-2 py-1 text-[11px] font-semibold text-amber-100"
            title={operationActionReasonSentence(operation.retryDisabledReason)}
          >
            Повтор недоступен
          </span>
        ) : null}
      </div>
    </div>
  );
}

function SupportWorkspaceTopbar({
  theme,
  onToggleTheme,
  notificationCount,
  onRefresh,
  refreshing,
  search,
  setSearch,
  userLogin,
  userRole,
}: {
  theme: SupportWorkspaceTheme;
  onToggleTheme: () => void;
  notificationCount: number;
  onRefresh: () => void;
  refreshing: boolean;
  search: string;
  setSearch: (value: string) => void;
  userLogin: string;
  userRole: string;
}) {
  const isLightTheme = theme === "light";
  return (
    <header className={`flex h-16 shrink-0 items-center gap-4 border-b px-4 backdrop-blur-xl ${isLightTheme ? "border-slate-200 bg-white/95 text-slate-950" : "border-white/10 bg-[#081321]/95 text-slate-100"}`}>
      <Link className="flex min-w-[220px] items-center gap-3" to="/app/tickets">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-950/40">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="text-base font-semibold">Service Desk</span>
        <span className="sr-only">Тикеты</span>
      </Link>

      <label className="flex h-10 min-w-0 max-w-[520px] flex-1 items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-400">
        <Search className="h-4 w-4 shrink-0" />
        <input
          className="min-w-0 flex-1 bg-transparent text-slate-100 outline-none placeholder:text-slate-500"
          onChange={(event) => setSearch(event.currentTarget.value)}
          placeholder="Поиск по тикетам, пользователям, устройствам..."
          type="search"
          value={search}
        />
      </label>

      <div className="ml-auto flex items-center gap-2">
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500"
          title="Создать новую заявку от имени пользователя"
          to="/app/help"
        >
          Создать
          <ChevronDown className="h-4 w-4" />
        </Link>
        <button
          aria-label="Обновить"
          className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition hover:text-white"
          disabled={refreshing}
          onClick={onRefresh}
          title="Обновить очередь и выбранный тикет"
          type="button"
        >
          <RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </button>
        <button
          aria-label={isLightTheme ? "Тёмная тема" : "Светлая тема"}
          className={`flex h-10 w-10 items-center justify-center rounded-xl border transition ${isLightTheme ? "border-slate-200 bg-slate-100 text-slate-700 hover:text-slate-950" : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"}`}
          onClick={onToggleTheme}
          title={isLightTheme ? "Переключить на тёмную тему" : "Переключить на светлую тему"}
          type="button"
        >
          {isLightTheme ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
        <button
          aria-label="Уведомления"
          className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300"
          title="Уведомления по тикетам и SLA"
          type="button"
        >
          <Bell className="h-4 w-4" />
          {notificationCount > 0 ? (
            <span className="absolute -right-1 -top-1 rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
              {notificationCount > 99 ? "99+" : notificationCount}
            </span>
          ) : null}
        </button>
        <button
          aria-label="Сообщения"
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300"
          title="Сообщения и комментарии"
          type="button"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
        <button
          aria-label="Помощь"
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300"
          title="Справка по рабочему месту оператора"
          type="button"
        >
          <CircleHelp className="h-4 w-4" />
        </button>
        <div className="hidden items-center gap-3 pl-2 md:flex">
          <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-slate-700">
            <UserRound className="h-5 w-5 text-slate-200" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">{userLogin}</p>
            <p className="text-xs text-slate-400">{userRole}</p>
          </div>
        </div>
      </div>
    </header>
  );
}

export function TicketListPage() {
  const navigate = useNavigate();
  const params = useParams<{ ticketId?: string }>();
  const queryClient = useQueryClient();
  const { session } = useSession();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [smartView, setSmartView] = useState("my_action");
  const [activeQueueId, setActiveQueueId] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(params.ticketId ?? null);
  const [search, setSearch] = useState("");
  const [composerMode, setComposerMode] = useState<ComposerMode>("public");
  const [composerText, setComposerText] = useState("");
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>("all");
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("context");
  const [moreOpen, setMoreOpen] = useState(false);
  const [operatorActionDraft, setOperatorActionDraft] = useState<OperatorActionDraft | null>(null);
  const [closureFocus, setClosureFocus] = useState<ClosurePlanBlocker | null>(null);
  const [closureBlockersExpanded, setClosureBlockersExpanded] = useState(false);
  const [manualEvidenceTitle, setManualEvidenceTitle] = useState("");
  const [manualEvidenceSummary, setManualEvidenceSummary] = useState("");
  const [worklogMinutes, setWorklogMinutes] = useState("15");
  const [worklogNote, setWorklogNote] = useState("");
  const [workspaceTheme, setWorkspaceTheme] = useState<SupportWorkspaceTheme>(() => getInitialSupportWorkspaceTheme());
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    setSelectedTicketId(params.ticketId ?? null);
  }, [params.ticketId]);

  const queueQuery = useQuery({
    queryKey: ["tickets-workspace-queue", scope, smartView, deferredSearch],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter: "all",
        smartView,
        query: deferredSearch,
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS,
  });

  useEffect(() => {
    const queue = queueQuery.data;
    if (!queue || selectedTicketId) {
      return;
    }
    if (queue.summary.selected_ticket_id) {
      startTransition(() => {
        navigate(`/app/tickets/${queue.summary.selected_ticket_id}`, { replace: true });
      });
    }
  }, [navigate, queueQuery.data, selectedTicketId]);

  const workspaceQuery = useQuery({
    queryKey: ["tickets-workspace", selectedTicketId],
    queryFn: () => fetchSupportTicketWorkspace(selectedTicketId!),
    enabled: Boolean(selectedTicketId),
    retry: false,
  });

  const timelineApiFilter: SupportTicketTimelineFilter =
    timelineFilter === "message" ? "messages" : timelineFilter;

  const timelineQuery = useQuery({
    queryKey: ["tickets-workspace-timeline", selectedTicketId, timelineApiFilter],
    queryFn: () => fetchSupportTicketTimeline(selectedTicketId!, timelineApiFilter),
    enabled: Boolean(selectedTicketId) && timelineFilter !== "all",
    retry: false,
  });

  const evidenceCandidatesQuery = useQuery({
    queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId],
    queryFn: () => fetchSupportTicketPassportEvidenceCandidates(selectedTicketId!),
    enabled: Boolean(selectedTicketId) && sidebarTab === "passport" && closureFocus?.actionKind === "attach_evidence",
    retry: false,
  });

  const viewModel = useMemo(
    () =>
      mapSupportWorkspaceViewModel({
        activeQueueId,
        activeSmartView: smartView,
        detail: workspaceQuery.data?.detail,
        knowledge: workspaceQuery.data?.knowledge,
        passport: workspaceQuery.data?.passport,
        passportReadiness: workspaceQuery.data?.passport_readiness,
        closurePlan: workspaceQuery.data?.closure_plan,
        playbooks: workspaceQuery.data?.playbooks,
        queue: queueQuery.data,
        selectedTicketId,
        slaOla: workspaceQuery.data?.sla_ola,
        tools: workspaceQuery.data?.tools,
      }),
    [activeQueueId, queueQuery.data, selectedTicketId, smartView, workspaceQuery.data],
  );

  const visibleTickets = activeQueueId
    ? viewModel.left.tickets.filter((ticket) => ticket.queueLabel === activeQueueId)
    : viewModel.left.tickets;

  const aggregateTimeline = viewModel.selectedTicket?.timeline ?? [];
  const endpointTimeline = timelineQuery.data ? mapSupportTimelineEntries(timelineQuery.data.items) : null;
  const visibleTimeline =
    timelineFilter === "all"
      ? aggregateTimeline
      : endpointTimeline ?? aggregateTimeline.filter((item) => item.kind === timelineFilter);
  const workspaceErrorState = workspaceQuery.isError ? classifyWorkspaceError(workspaceQuery.error) : null;
  const timelineEmptyState = visibleTimeline.length === 0 ? getTimelineEmptyState(timelineFilter) : null;
  const firstRunnableTool = viewModel.right.tools.find((item) => item.enabled);
  const firstRunnablePlaybook = viewModel.right.playbooks.find((item) => item.enabled);
  const visibleAutomationItems =
    viewModel.right.playbooks.length && viewModel.right.tools.length
      ? [...viewModel.right.playbooks.slice(0, 4), ...viewModel.right.tools.slice(0, 4)]
      : [...viewModel.right.playbooks, ...viewModel.right.tools].slice(0, 8);
  const activeOperations = viewModel.right.operations.filter((operation) => operation.active);
  const statusActionOptions = workspaceQuery.data?.detail.actions.status_options ?? [];
  const queueActionOptions = (queueQuery.data?.summary.queue_counts ?? []).filter((queue) => queue.id !== null);
  const firstQueueActionId = queueActionOptions[0]?.id ?? null;
  const firstStatusActionValue = statusActionOptions[0]?.value ?? null;

  const messageMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicketId) {
        return null;
      }
      return postSupportTicketMessage(selectedTicketId, composerText.trim(), composerMode);
    },
    onSuccess: async () => {
      setComposerText("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
      ]);
    },
  });

  const toolRunMutation = useMutation({
    mutationFn: async () => {
      const tool = workspaceQuery.data?.tools.tools.find((item) => item.tool_name === firstRunnableTool?.id);
      if (!selectedTicketId || !tool) {
        return null;
      }
      const preset = tool.presets[0];
      return postSupportTicketToolRun(selectedTicketId, {
        toolName: tool.tool_name,
        presetId: preset?.preset_id ?? null,
        params: preset?.params ?? {},
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
      ]);
    },
  });

  const playbookRunMutation = useMutation({
    mutationFn: async () => {
      const playbook = workspaceQuery.data?.playbooks.playbooks.find((item) => String(item.playbook_version_id) === firstRunnablePlaybook?.id);
      if (!selectedTicketId || !playbook) {
        return null;
      }
      return postSupportTicketPlaybookRun(selectedTicketId, { playbookVersionId: playbook.playbook_version_id });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
      ]);
    },
  });

  const operatorActionMutation = useMutation({
    mutationFn: async (draft: OperatorActionDraft) => {
      if (!selectedTicketId) {
        return null;
      }
      const reason = draft.reason.trim();
      const comment = draft.comment.trim();
      if (draft.kind === "status") {
        return postSupportTicketStatus(selectedTicketId, draft.targetStatus, {
          reason,
          internalComment: comment || undefined,
        });
      }
      if (draft.kind === "assign_self") {
        return postSupportTicketAssign(selectedTicketId, {
          assigneeId: session?.user_login ?? undefined,
          reason,
          comment: comment || undefined,
        });
      }
      if (draft.kind === "queue") {
        if (!draft.queueId) {
          return null;
        }
        return postSupportTicketQueue(selectedTicketId, {
          queueId: draft.queueId,
          reason,
        });
      }
      if (draft.kind === "priority") {
        return postSupportTicketPriority(selectedTicketId, {
          priority: draft.priority,
          reason,
        });
      }
      return postSupportTicketReroute(selectedTicketId, { reason });
    },
    onSuccess: async () => {
      setMoreOpen(false);
      setOperatorActionDraft(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
      ]);
    },
  });

  const evidenceLinkMutation = useMutation({
    mutationFn: async (candidate: SupportTicketEvidenceCandidatePayload) => {
      if (!selectedTicketId) {
        return null;
      }
      return linkSupportTicketPassportEvidence(selectedTicketId, {
        source_kind: candidate.source_kind,
        source_id: candidate.source_id,
        required_fact: candidate.required_fact,
        visibility: candidate.visibility || "internal",
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId] }),
      ]);
    },
  });

  const manualEvidenceMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicketId) {
        return null;
      }
      const title = manualEvidenceTitle.trim();
      if (!title) {
        return null;
      }
      return createSupportTicketPassportEvidence(selectedTicketId, {
        evidence_type: "manual_note",
        required_fact: closureFocus?.factKey || "evidence",
        section_key: closureFocus?.factKey || "evidence",
        title,
        summary: manualEvidenceSummary.trim() || null,
        visibility: "internal",
        verification_status: "accepted",
        export_visibility: "internal",
      });
    },
    onSuccess: async () => {
      setManualEvidenceTitle("");
      setManualEvidenceSummary("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId] }),
      ]);
    },
  });

  const worklogMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicketId) {
        return null;
      }
      const spentMinutes = Number.parseInt(worklogMinutes, 10);
      if (!Number.isFinite(spentMinutes) || spentMinutes <= 0) {
        throw new Error("Укажите время worklog больше 0 минут.");
      }
      return postSupportTicketWorklog(selectedTicketId, {
        spentMinutes,
        note: worklogNote.trim() || null,
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId] }),
      ]);
    },
  });

  const operationCancelMutation = useMutation({
    mutationFn: async (operationId: string) =>
      postSupportOperationCancel(operationId, {
        reason: "operator_requested_from_support_workspace",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
      ]);
    },
  });

  const operationRetryMutation = useMutation({
    mutationFn: async (operationId: string) =>
      postSupportOperationRetry(operationId, {
        reason: "operator_requested_from_support_workspace",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
      ]);
    },
  });

  function openTicket(ticketId: string) {
    startTransition(() => {
      navigate(`/app/tickets/${ticketId}`);
    });
  }

  function refreshAll() {
    void Promise.all([
      queueQuery.refetch(),
      workspaceQuery.refetch(),
    ]);
  }

  function toggleWorkspaceTheme() {
    setWorkspaceTheme((current) => {
      const nextTheme = current === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        window.localStorage.setItem(SUPPORT_WORKSPACE_THEME_STORAGE_KEY, nextTheme);
      }
      return nextTheme;
    });
  }

  const selectedTicket = viewModel.selectedTicket;
  const orderedClosureBlockers = useMemo(
    () => orderClosureBlockers(selectedTicket?.closurePlan.blockers ?? []),
    [selectedTicket?.closurePlan.blockers],
  );
  const hiddenClosureBlockerCount = Math.max(0, orderedClosureBlockers.length - CLOSURE_BLOCKER_VISIBLE_LIMIT);
  const visibleClosureBlockers = closureBlockersExpanded
    ? orderedClosureBlockers
    : orderedClosureBlockers.slice(0, CLOSURE_BLOCKER_VISIBLE_LIMIT);
  const closureGuide = closureFocus ? closureFocusGuide(closureFocus) : null;
  const internalNoteAllowed = selectedTicket?.canSendInternalNote ?? false;
  const actionError =
    messageMutation.error ||
    operatorActionMutation.error ||
    toolRunMutation.error ||
    playbookRunMutation.error ||
    evidenceLinkMutation.error ||
    manualEvidenceMutation.error ||
    worklogMutation.error ||
    operationCancelMutation.error ||
    operationRetryMutation.error;
  const operatorActionMeta = operatorActionDraft ? operatorActionLabels[operatorActionDraft.kind] : null;
  const operatorReasonReady = (operatorActionDraft?.reason.trim().length ?? 0) >= 3;
  const operatorTargetReady =
    !operatorActionDraft ||
    operatorActionDraft.kind === "assign_self" ||
    operatorActionDraft.kind === "reroute" ||
    (operatorActionDraft.kind === "status" && Boolean(operatorActionDraft.targetStatus)) ||
    (operatorActionDraft.kind === "queue" && Boolean(operatorActionDraft.queueId)) ||
    (operatorActionDraft.kind === "priority" && Boolean(operatorActionDraft.priority));
  const operatorSubmitDisabled = !operatorActionDraft || !operatorReasonReady || !operatorTargetReady || operatorActionMutation.isPending;

  function openOperatorAction(kind: OperatorActionKind) {
    setMoreOpen(false);
    setOperatorActionDraft(
      makeOperatorActionDraft(kind, {
        currentPriority: selectedTicket?.priority,
        firstQueueId: firstQueueActionId,
        firstStatus: firstStatusActionValue,
      }),
    );
  }

  function openClosureBlocker(blocker: ClosurePlanBlocker) {
    setClosureFocus(blocker);
    setManualEvidenceTitle(blocker.label);
    setManualEvidenceSummary(blocker.detail ?? "");
    setWorklogNote(blocker.detail ?? "");
    setWorklogMinutes("15");
    setSidebarTab("passport");
  }

  useEffect(() => {
    if (composerMode === "internal" && selectedTicket && !selectedTicket.canSendInternalNote) {
      setComposerMode("public");
    }
  }, [composerMode, selectedTicket]);

  useEffect(() => {
    setClosureFocus(null);
    setClosureBlockersExpanded(false);
    setManualEvidenceTitle("");
    setManualEvidenceSummary("");
    setWorklogNote("");
    setWorklogMinutes("15");
  }, [selectedTicket?.id]);

  const isLightTheme = workspaceTheme === "light";

  return (
    <section
      className={`support-workspace flex h-screen min-h-screen flex-col overflow-hidden ${isLightTheme ? "bg-slate-100 text-slate-950" : "bg-[#07111f] text-slate-100"}`}
      data-testid="support-workspace-root"
      data-theme={workspaceTheme}
    >
      <h1 className="sr-only">Тикеты</h1>
      <SupportWorkspaceTopbar
        theme={workspaceTheme}
        onToggleTheme={toggleWorkspaceTheme}
        notificationCount={workspaceQuery.data?.detail.snapshot.notification_unread ?? 0}
        onRefresh={refreshAll}
        refreshing={queueQuery.isFetching || workspaceQuery.isFetching}
        search={search}
        setSearch={setSearch}
        userLogin={session?.user_login ?? "operator"}
        userRole={session?.actor_role === "admin" ? "Администратор" : "Оператор L1"}
      />

      <div className="grid min-h-0 flex-1 grid-cols-[320px_minmax(520px,1fr)_390px] overflow-hidden">
        <aside className="flex min-h-0 flex-col border-r border-white/10 bg-[#0b1624]">
          <div className="border-b border-white/10 px-4 py-4">
            <div className="grid grid-cols-2 gap-2 rounded-xl bg-white/[0.04] p-1">
              {(["all", "mine"] as const).map((value) => (
                <button
                  className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                    scope === value ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                  key={value}
                  onClick={() => setScope(value)}
                  type="button"
                >
                  {value === "all" ? "Все" : "Мои"}
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
            <div className="mb-4">
              <div className="mb-2 flex items-center justify-between px-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <span>Рабочие срезы</span>
                <Wrench className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                {viewModel.left.slices.map((slice) => {
                  const Icon = sliceIcons[slice.icon];
                  return (
                    <button
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                        slice.active ? "bg-blue-600/25 text-white ring-1 ring-blue-500/40" : "text-slate-300 hover:bg-white/[0.04]"
                      }`}
                      key={slice.id}
                      onClick={() => setSmartView(slice.id)}
                      type="button"
                    >
                      <Icon className="h-4 w-4 shrink-0 text-slate-400" />
                      <span className="min-w-0 flex-1 truncate">{slice.label}</span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs font-semibold text-slate-200">{slice.count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-2 flex items-center justify-between px-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <span>Очереди</span>
                <span className="text-base leading-none text-slate-400">+</span>
              </div>
              <div className="space-y-1">
                {viewModel.left.queues.map((queue) => {
                  const Icon = queueIcons[queue.icon];
                  return (
                    <button
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                        queue.active ? "bg-blue-600/25 text-white ring-1 ring-blue-500/40" : "text-slate-300 hover:bg-white/[0.04]"
                      }`}
                      key={queue.id}
                      onClick={() => setActiveQueueId(queue.active ? null : queue.id)}
                      type="button"
                    >
                      <Icon className="h-4 w-4 shrink-0 text-slate-400" />
                      <span className="min-w-0 flex-1 truncate">{queue.label}</span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs font-semibold text-slate-200">{queue.count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mb-2 flex items-center justify-between px-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              <span>Тикеты в очереди</span>
              <span>{visibleTickets.length}</span>
            </div>

            {queueQuery.isLoading ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-6 text-center text-sm text-slate-400">
                Загружаем очередь...
              </div>
            ) : null}

            {queueQuery.isError ? (
              <div className="rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-4 text-sm text-red-100">
                {queueQuery.error instanceof Error ? queueQuery.error.message : "Не удалось загрузить очередь"}
              </div>
            ) : null}

            {!queueQuery.isLoading && visibleTickets.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-6 text-center text-sm text-slate-400">
                По текущим фильтрам тикеты не найдены.
              </div>
            ) : null}

            <div className="space-y-2">
              {visibleTickets.map((ticket) => (
                <button
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    ticket.active
                      ? "border-blue-500 bg-blue-600/15 shadow-lg shadow-blue-950/20"
                      : "border-white/10 bg-[#0d1828] hover:border-white/20 hover:bg-[#111f33]"
                  }`}
                  key={ticket.id}
                  onClick={() => openTicket(ticket.id)}
                  type="button"
                >
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-blue-200">{ticket.code}</p>
                      <p className="mt-0.5 truncate text-sm font-semibold text-white">{ticket.subject}</p>
                    </div>
                    {ticket.unread ? <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-red-400" /> : null}
                  </div>
                  <p className="truncate text-xs text-slate-400">{ticket.requester}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-bold ${toneClasses(ticket.priorityTone)}`}>{ticket.priority}</span>
                    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${toneClasses(ticket.statusTone)}`}>
                      {ticket.statusLabel}
                    </span>
                    <span className={`ml-auto text-xs font-semibold ${ticket.slaRisk ? "text-red-300" : "text-amber-200"}`}>
                      {ticket.nextDueLabel}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 flex-col border-r border-white/10 bg-[#07111f]">
          {!selectedTicketId ? (
            <div className="flex flex-1 items-center justify-center px-8 text-center">
              <div>
                <Inbox className="mx-auto h-10 w-10 text-slate-500" />
                <h2 className="mt-4 text-xl font-semibold text-white">Выберите тикет из очереди</h2>
                <p className="mt-2 max-w-md text-sm text-slate-400">Центральная рабочая область появится после выбора обращения.</p>
              </div>
            </div>
          ) : null}

          {selectedTicketId && workspaceQuery.isLoading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">Загружаем тикет...</div>
          ) : null}

          {selectedTicketId && workspaceErrorState ? (
            <div
              className={`m-6 rounded-2xl border px-5 py-5 text-sm ${
                workspaceErrorState.tone === "warning"
                  ? "border-amber-400/30 bg-amber-500/10 text-amber-50"
                  : "border-red-400/30 bg-red-500/10 text-red-50"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
                    workspaceErrorState.tone === "warning"
                      ? "border-amber-300/30 bg-amber-400/10 text-amber-200"
                      : "border-red-300/30 bg-red-400/10 text-red-200"
                  }`}
                >
                  <AlertTriangle className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-semibold text-white">{workspaceErrorState.title}</h2>
                  <p className="mt-1 leading-6 text-slate-300">{workspaceErrorState.body}</p>
                  <button
                    className="mt-4 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-sm font-semibold text-white transition hover:border-blue-400/40 hover:bg-blue-500/20"
                    onClick={() => {
                      if (workspaceErrorState.action === "queue") {
                        navigate("/app/tickets");
                        return;
                      }
                      void workspaceQuery.refetch();
                    }}
                    type="button"
                  >
                    {workspaceErrorState.actionLabel}
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          {selectedTicket ? (
            <>
              <div className="border-b border-white/10 bg-[#0b1624]/70 px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3 text-sm text-slate-400">
                      <Link className="hover:text-white" to="/app/tickets">Очередь</Link>
                      <span>/</span>
                      <span>{selectedTicket.code}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <h2 className="truncate text-2xl font-semibold tracking-tight text-white">
                        {selectedTicket.code} {selectedTicket.subject}
                      </h2>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                      <span className={`rounded-md border px-2 py-1 font-bold ${toneClasses(selectedTicket.priorityTone)}`}>{selectedTicket.priority}</span>
                      <span>Очередь: {selectedTicket.queueLabel}</span>
                      <span>Исполнитель: {selectedTicket.assigneeLabel}</span>
                      <span className={`rounded-md border px-2 py-1 font-semibold ${toneClasses(selectedTicket.statusTone)}`}>{selectedTicket.statusLabel}</span>
                      <span>SLA: {selectedTicket.nextAction.remainingLabel}</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300" type="button">
                      <Star className="h-4 w-4" />
                    </button>
                    <button className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300" type="button">
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <section className={`mt-5 grid grid-cols-[auto_minmax(0,1fr)_260px] items-center gap-5 rounded-xl border p-4 ${toneClasses(selectedTicket.nextAction.tone)}`}>
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10">
                    <Play className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">Следующее действие</p>
                    <p className="mt-1 text-base font-semibold text-white">{selectedTicket.nextAction.label}</p>
                    <p className="mt-1 truncate text-sm text-slate-300">{selectedTicket.nextAction.hint}</p>
                  </div>
                  <div className="border-l border-white/10 pl-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Осталось времени</p>
                    <p className="mt-1 text-2xl font-semibold text-white">{selectedTicket.nextAction.remainingLabel}</p>
                    <p className="mt-1 text-xs text-slate-400">до контрольного срока</p>
                  </div>
                </section>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500"
                    onClick={() => setComposerMode("public")}
                    type="button"
                  >
                    <Send className="h-4 w-4" />
                    Ответить
                  </button>
                  <button
                    className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!internalNoteAllowed}
                    onClick={() => setComposerMode("internal")}
                    type="button"
                  >
                    <Lock className="h-4 w-4" />
                    Внутренняя заметка
                  </button>
                  <button
                    className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 hover:text-white disabled:opacity-50"
                    disabled={toolRunMutation.isPending || !firstRunnableTool}
                    onClick={() => toolRunMutation.mutate()}
                    type="button"
                  >
                    <Wrench className="h-4 w-4" />
                    Запустить диагностику
                  </button>
                  <div className="ml-auto flex items-center gap-2">
                    <div className="relative">
                      <button
                        aria-expanded={moreOpen}
                        className="h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 hover:text-white disabled:opacity-50"
                        disabled={operatorActionMutation.isPending}
                        onClick={() => setMoreOpen((open) => !open)}
                        type="button"
                      >
                        Ещё
                      </button>
                      {moreOpen ? (
                        <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-xl border border-white/10 bg-[#101d30] p-1 shadow-2xl shadow-black/40">
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!session?.user_login}
                            onClick={() => openOperatorAction("assign_self")}
                            type="button"
                          >
                            Назначить на себя
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={statusActionOptions.length === 0}
                            onClick={() => openOperatorAction("status")}
                            type="button"
                          >
                            Сменить статус
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={queueActionOptions.length === 0}
                            onClick={() => openOperatorAction("queue")}
                            type="button"
                          >
                            Сменить очередь
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10"
                            onClick={() => openOperatorAction("priority")}
                            type="button"
                          >
                            Изменить приоритет
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10"
                            onClick={() => openOperatorAction("reroute")}
                            type="button"
                          >
                            Пересчитать маршрут
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
                {operatorActionDraft && operatorActionMeta ? (
                  <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm" role="presentation">
                    <section
                      aria-labelledby="operator-action-title"
                      aria-modal="true"
                      className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101d30] p-5 text-slate-100 shadow-2xl shadow-black/50"
                      role="dialog"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h2 className="text-lg font-semibold" id="operator-action-title">{operatorActionMeta.title}</h2>
                          <p className="mt-1 text-sm leading-6 text-slate-400">{operatorActionMeta.description}</p>
                        </div>
                        <button
                          aria-label="Закрыть действие"
                          className="rounded-lg border border-white/10 px-2 py-1 text-sm text-slate-300 hover:text-white"
                          onClick={() => setOperatorActionDraft(null)}
                          type="button"
                        >
                          ×
                        </button>
                      </div>

                      <div className="mt-5 space-y-4">
                        {operatorActionDraft.kind === "status" ? (
                          <label className="block text-sm font-medium text-slate-300">
                            Новый статус
                            <select
                              className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none"
                              onChange={(event) => {
                                const targetStatus = event.currentTarget.value;
                                setOperatorActionDraft((draft) => draft ? { ...draft, targetStatus } : draft);
                              }}
                              value={operatorActionDraft.targetStatus}
                            >
                              {statusActionOptions.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                              ))}
                            </select>
                          </label>
                        ) : null}

                        {operatorActionDraft.kind === "queue" ? (
                          <label className="block text-sm font-medium text-slate-300">
                            Целевая очередь
                            <select
                              className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none"
                              onChange={(event) => {
                                const queueId = Number(event.currentTarget.value) || null;
                                setOperatorActionDraft((draft) => draft ? { ...draft, queueId } : draft);
                              }}
                              value={operatorActionDraft.queueId ?? ""}
                            >
                              {queueActionOptions.map((queue) => (
                                <option key={queue.id} value={queue.id ?? ""}>
                                  {queue.name || queue.code || `Очередь ${queue.id}`} · {queue.count}
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : null}

                        {operatorActionDraft.kind === "priority" ? (
                          <fieldset className="space-y-2">
                            <legend className="text-sm font-medium text-slate-300">Новый приоритет</legend>
                            <div className="grid grid-cols-4 gap-2">
                              {priorityActionOptions.map((option) => (
                                <button
                                  className={`rounded-xl border px-3 py-3 text-left transition ${
                                    operatorActionDraft.priority === option.value
                                      ? "border-blue-400 bg-blue-600/25 text-white"
                                      : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
                                  }`}
                                  key={option.value}
                                  onClick={() =>
                                    setOperatorActionDraft((draft) => draft ? { ...draft, priority: option.value } : draft)
                                  }
                                  type="button"
                                >
                                  <span className="block text-sm font-bold">{option.label}</span>
                                  <span className="mt-1 block text-[11px] leading-4 text-slate-400">{option.hint}</span>
                                </button>
                              ))}
                            </div>
                          </fieldset>
                        ) : null}

                        {operatorActionDraft.kind === "assign_self" ? (
                          <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-300">
                            Исполнитель: <span className="font-semibold text-slate-100">{session?.user_login ?? "текущий оператор"}</span>
                          </div>
                        ) : null}

                        <label className="block text-sm font-medium text-slate-300">
                          Причина
                          <input
                            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const reason = event.currentTarget.value;
                              setOperatorActionDraft((draft) => draft ? { ...draft, reason } : draft);
                            }}
                            placeholder="Например: ручная корректировка по диагностике"
                            value={operatorActionDraft.reason}
                          />
                        </label>

                        <label className="block text-sm font-medium text-slate-300">
                          Комментарий для внутренней истории
                          <textarea
                            className="mt-2 min-h-24 w-full resize-none rounded-xl border border-white/10 bg-[#0d1828] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const comment = event.currentTarget.value;
                              setOperatorActionDraft((draft) => draft ? { ...draft, comment } : draft);
                            }}
                            placeholder="Необязательно. Добавьте контекст для следующего оператора."
                            value={operatorActionDraft.comment}
                          />
                        </label>

                        {!operatorReasonReady ? (
                          <p className="text-xs text-amber-200">Укажите причину минимум из 3 символов, чтобы действие попало в историю осмысленно.</p>
                        ) : null}
                      </div>

                      <div className="mt-5 flex justify-end gap-2">
                        <button
                          className="h-10 rounded-xl border border-white/10 px-4 text-sm font-semibold text-slate-300 hover:text-white"
                          onClick={() => setOperatorActionDraft(null)}
                          type="button"
                        >
                          Отмена
                        </button>
                        <button
                          className="h-10 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={operatorSubmitDisabled}
                          onClick={() => operatorActionDraft && operatorActionMutation.mutate(operatorActionDraft)}
                          type="button"
                        >
                          {operatorActionMutation.isPending ? "Выполняем..." : operatorActionMeta.submit}
                        </button>
                      </div>
                    </section>
                  </div>
                ) : null}
                {actionError ? (
                  <p className="mt-3 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                    {actionError instanceof Error ? actionError.message : "Действие не выполнено"}
                  </p>
                ) : null}

                {selectedTicket.closurePlan.missingCount > 0 ? (
                  <section
                    className={`mt-4 rounded-xl p-4 ${
                      isLightTheme
                        ? "border border-amber-300 bg-amber-50 text-slate-950 shadow-sm"
                        : "border border-amber-400/25 bg-amber-500/10"
                    }`}
                    data-testid="closure-plan-panel"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className={`h-4 w-4 ${isLightTheme ? "text-amber-700" : "text-amber-200"}`} />
                          <p
                            className={`font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}
                            data-testid="closure-plan-title"
                          >
                            Перед закрытием
                          </p>
                        </div>
                        <p
                          className={`mt-1 text-sm leading-6 ${isLightTheme ? "text-amber-900" : "text-amber-100/90"}`}
                          data-testid="closure-plan-summary"
                        >
                          Осталось требований: {selectedTicket.closurePlan.missingCount}/{selectedTicket.closurePlan.total || selectedTicket.closurePlan.missingCount}.
                          {selectedTicket.closurePlan.evidenceCandidateCount
                            ? ` Доступно кандидатов evidence: ${selectedTicket.closurePlan.evidenceCandidateCount}.`
                            : " Evidence-кандидаты не найдены."}
                        </p>
                      </div>
                      <button
                        className={`shrink-0 rounded-xl px-3 py-2 text-sm font-semibold ${
                          isLightTheme
                            ? "border border-amber-300 bg-white/80 text-amber-900 hover:bg-white"
                            : "border border-amber-300/30 bg-white/[0.06] text-amber-50 hover:bg-white/[0.1]"
                        }`}
                        onClick={() => setSidebarTab("passport")}
                        type="button"
                      >
                        <FileCheck2 className="mr-2 inline h-4 w-4" />
                        Открыть паспорт
                      </button>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2">
                      {visibleClosureBlockers.map((blocker) => (
                        <div
                          className={`rounded-lg px-3 py-2 ${
                            isLightTheme ? "border border-amber-200 bg-white/80" : "border border-white/10 bg-white/[0.04]"
                          }`}
                          data-testid="closure-blocker-card"
                          key={blocker.key}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className={`min-w-0 break-words text-sm font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>
                              {blocker.label}
                            </p>
                            <button
                              className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                                isLightTheme
                                  ? "border border-amber-200 bg-amber-50 text-amber-900 hover:border-amber-300 hover:bg-amber-100"
                                  : "border border-white/10 bg-white/[0.05] text-amber-100 hover:border-amber-200/50 hover:bg-white/[0.1]"
                              }`}
                              onClick={() => openClosureBlocker(blocker)}
                              type="button"
                            >
                              {blocker.actionLabel}
                            </button>
                          </div>
                          {blocker.detail ? (
                            <p className={`mt-1 break-words text-xs leading-5 ${isLightTheme ? "text-amber-900/80" : "text-amber-100/75"}`}>
                              {blocker.detail}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    {hiddenClosureBlockerCount > 0 ? (
                      <button
                        className={`mt-3 rounded-lg px-3 py-2 text-xs font-semibold ${
                          isLightTheme
                            ? "border border-amber-300 bg-white/80 text-amber-900 hover:bg-white"
                            : "border border-amber-300/25 bg-white/[0.04] text-amber-100 hover:border-amber-200/50 hover:bg-white/[0.08]"
                        }`}
                        onClick={() => setClosureBlockersExpanded((expanded) => !expanded)}
                        type="button"
                      >
                        {closureBlockersExpanded ? "Скрыть" : `Показать ещё ${hiddenClosureBlockerCount}`}
                      </button>
                    ) : null}
                  </section>
                ) : null}
              </div>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex items-center gap-5 border-b border-white/10 px-5">
                  {timelineTabs.map((tab) => (
                    <button
                      className={`border-b-2 px-1 py-4 text-sm font-semibold transition ${
                        timelineFilter === tab.value ? "border-blue-500 text-blue-200" : "border-transparent text-slate-400 hover:text-white"
                      }`}
                      key={tab.value}
                      onClick={() => setTimelineFilter(tab.value)}
                      type="button"
                    >
                      {tab.label}
                    </button>
                  ))}
                  <button className="ml-auto rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-300" type="button">
                    Фильтр
                  </button>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                  {timelineEmptyState ? (
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-10 text-center text-sm text-slate-400">
                      <Inbox className="mx-auto h-9 w-9 text-slate-500" />
                      <p className="mt-4 text-base font-semibold text-white">{timelineEmptyState.title}</p>
                      <p className="mx-auto mt-2 max-w-md leading-6">{timelineEmptyState.body}</p>
                      {timelineEmptyState.actionLabel ? (
                        <button
                          className="mt-4 rounded-xl border border-white/10 bg-white/[0.05] px-3 py-2 font-semibold text-slate-100 transition hover:border-blue-400/40 hover:bg-blue-500/20"
                          onClick={() => setTimelineFilter("all")}
                          type="button"
                        >
                          {timelineEmptyState.actionLabel}
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="space-y-4">
                    {visibleTimeline.map((item) => (
                      <article className="grid grid-cols-[36px_minmax(0,1fr)_110px] gap-4" key={item.id}>
                        <div className={`flex h-9 w-9 items-center justify-center rounded-full border ${toneClasses(item.tone)}`}>
                          {item.kind === "diagnostics" ? <Wrench className="h-4 w-4" /> : item.kind === "internal" ? <Lock className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
                        </div>
                        <div className="min-w-0 rounded-xl border border-white/10 bg-[#0d1828] px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2 text-sm">
                            <span className="font-semibold text-white">{item.actor}</span>
                            <span className="text-slate-500">·</span>
                            <span className="text-slate-400">{item.title}</span>
                            {item.visibility === "internal" ? <Lock className="h-3.5 w-3.5 text-amber-300" /> : null}
                          </div>
                          <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-200">{item.body}</p>
                          {item.operation ? (
                            <div className="mt-3 rounded-lg border border-white/10 bg-[#111f33] p-3 text-sm">
                              <div className="grid gap-3 md:grid-cols-3">
                                <div>
                                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Операция</p>
                                  <p className="mt-1 font-semibold text-white">{item.operation.name}</p>
                                </div>
                                <div>
                                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Статус</p>
                                  <span className={`mt-1 inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(item.operation.statusTone)}`}>
                                    {item.operation.statusLabel}
                                  </span>
                                </div>
                                <div>
                                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Итог</p>
                                  <p className={`mt-1 break-all font-semibold ${operationResultTextClass(item.operation)}`}>
                                    {item.operation.summary ?? item.operation.preview ?? "Нет результата"}
                                  </p>
                                </div>
                              </div>
                              {item.operation.preview && item.operation.summary && item.operation.preview !== item.operation.summary ? (
                                <p className="mt-3 break-all rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs leading-5 text-slate-400">
                                  {item.operation.preview}
                                </p>
                              ) : null}
                              {item.operation.metaLabels.length ? (
                                <div className="mt-3 flex flex-wrap gap-1.5">
                                  {item.operation.metaLabels.slice(0, 6).map((label) => (
                                    <span className="max-w-full break-all rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-slate-400" key={`${item.id}:${label}`}>
                                      {label}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              {item.operation.steps?.length ? (
                                <div className="mt-3 grid gap-2 border-t border-white/10 pt-3 md:grid-cols-3">
                                  {item.operation.steps.map((step) => (
                                    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2" key={`${item.id}:${step.name}:${step.status}`}>
                                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{step.name}</p>
                                      <p className={`mt-1 font-semibold ${diagnosticStepTextClass(step.status)}`}>
                                        {diagnosticStepStatusLabel(step.status)}
                                      </p>
                                      <p className="mt-1 break-words text-xs leading-5 text-slate-400">{step.value}</p>
                                      {step.details ? <p className="mt-1 break-words text-xs leading-5 text-slate-500">{step.details}</p> : null}
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {item.attachments.length ? (
                            <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                              <Paperclip className="h-4 w-4" />
                              {item.attachments.length} влож.
                            </div>
                          ) : null}
                        </div>
                        <time className="pt-2 text-right text-xs text-slate-500">{item.timestampLabel}</time>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="border-t border-white/10 bg-[#0b1624] p-4">
                  <div className="rounded-xl border border-white/10 bg-[#0d1828]">
                    <div className="flex items-center gap-4 border-b border-white/10 px-4">
                      {(["public", "internal"] as const).map((mode) => (
                        <button
                          className={`border-b-2 py-3 text-sm font-semibold ${
                            composerMode === mode ? "border-blue-500 text-blue-200" : "border-transparent text-slate-400"
                          }`}
                          disabled={mode === "internal" && !internalNoteAllowed}
                          key={mode}
                          onClick={() => setComposerMode(mode)}
                          type="button"
                        >
                          {mode === "public" ? "Публичный ответ" : "Внутренняя заметка"}
                          {mode === "internal" ? <Lock className="ml-2 inline h-3.5 w-3.5" /> : null}
                        </button>
                      ))}
                    </div>
                    <textarea
                      className="h-24 w-full resize-none bg-transparent px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
                      onChange={(event) => setComposerText(event.currentTarget.value)}
                      placeholder={composerMode === "public" ? "Напишите сообщение пользователю..." : "Напишите внутреннюю заметку для команды..."}
                      value={composerText}
                    />
                    <div className="flex items-center gap-2 px-4 pb-4">
                      <button className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-slate-400" type="button">
                        <Paperclip className="h-4 w-4" />
                      </button>
                      <button className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-300" type="button">
                        Шаблоны
                      </button>
                      <button
                        className="ml-auto inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white disabled:opacity-50"
                        disabled={!composerText.trim() || messageMutation.isPending || (composerMode === "internal" && !internalNoteAllowed)}
                        onClick={() => messageMutation.mutate()}
                        type="button"
                      >
                        Отправить
                        <Send className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </main>

        <aside className="flex min-h-0 flex-col bg-[#0b1624]">
          <div className="border-b border-white/10 p-3">
            <div className="grid grid-cols-[1.05fr_0.55fr_1.35fr_0.8fr_0.85fr] gap-1 rounded-xl bg-white/[0.04] p-1">
              {sidebarTabs.map((tab) => (
                <button
                  className={`rounded-lg px-2 py-2 text-xs font-semibold transition ${
                    sidebarTab === tab.value ? "bg-[#13233a] text-white shadow" : "text-slate-400 hover:text-white"
                  }`}
                  key={tab.value}
                  onClick={() => setSidebarTab(tab.value)}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {!selectedTicket ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
                Контекст появится после выбора тикета.
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "context" && viewModel.right.context ? (
              <div className="space-y-3">
                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Заявитель</p>
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-700">
                      <UserRound className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-white">{viewModel.right.context.requester.name}</p>
                      <p className="text-sm text-slate-400">{viewModel.right.context.requester.department}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <span className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300">
                      {viewModel.right.context.requester.sourceLabel}
                    </span>
                  </div>
                  <dl className="mt-4 grid gap-2">
                    <ContextInfoRow icon={Phone} label="Телефон" value={viewModel.right.context.requester.phone} />
                    <ContextInfoRow icon={Mail} label="Email" value={viewModel.right.context.requester.email} />
                    <ContextInfoRow icon={MapPin} label="Локация" value={viewModel.right.context.requester.location} />
                  </dl>
                </section>

                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Устройство</p>
                    <span className={viewModel.right.context.device.online ? "text-xs font-semibold text-emerald-300" : "text-xs font-semibold text-red-300"}>
                      {viewModel.right.context.device.onlineLabel}
                    </span>
                  </div>
                  <p className="mt-3 font-semibold text-white">{viewModel.right.context.device.hostname}</p>
                  <p className="mt-1 text-sm text-slate-400">{viewModel.right.context.device.os}</p>
                  <dl className="mt-4 grid gap-2">
                    <ContextInfoRow icon={Cpu} label="Тип актива" value={viewModel.right.context.device.assetTypeLabel} />
                    <ContextInfoRow icon={Fingerprint} label="Asset ID" value={viewModel.right.context.device.assetId} />
                    <ContextInfoRow icon={Monitor} label="Device ID" value={viewModel.right.context.device.id} />
                    <ContextInfoRow icon={Clock3} label="Последний вход" value={viewModel.right.context.device.lastSeenLabel} />
                  </dl>
                </section>

                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Категория / услуга</p>
                  <dl className="mt-3 grid gap-2">
                    <ContextInfoRow icon={Tags} label="Тип" value={viewModel.right.context.classification.ticketType} />
                    <ContextInfoRow icon={ClipboardList} label="Категория" value={viewModel.right.context.classification.category} />
                    <ContextInfoRow icon={Building2} label="Сервис" value={viewModel.right.context.classification.service} />
                    <ContextInfoRow icon={UsersRound} label="Владелец услуги" value={viewModel.right.context.classification.serviceOwner} />
                    <ContextInfoRow icon={Fingerprint} label="Источник услуги" value={viewModel.right.context.classification.serviceSourceLabel} />
                    <ContextInfoRow icon={BookOpen} label="Источник" value={viewModel.right.context.classification.source} />
                    <ContextInfoRow icon={MessageSquare} label="Похожие тикеты" value={viewModel.right.context.classification.similarTicketsCount} />
                  </dl>
                </section>
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "sla" ? (
              <div className="space-y-3">
                {selectedTicket.timers.length ? selectedTicket.timers.map((timer) => (
                  <section className={`rounded-xl border border-white/10 bg-[#111f33] p-4 ${timerStatusRing(timer.status)}`} key={timer.key}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-white">{timer.label}</p>
                        <p className="mt-1 text-xs text-slate-500">{formatDueLabel(timer.dueAt)}</p>
                      </div>
                      <span className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(timerStatusToTone(timer.status))}`}>
                        {timerStatusLabel(timer.status)}
                      </span>
                    </div>
                    <div className="mt-4 flex items-end justify-between gap-3">
                      <div>
                        <p className="text-2xl font-semibold tracking-tight text-white">{timer.remainingLabel}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {timer.status === "paused" ? "Отсчёт приостановлен" : timer.status === "unknown" ? "Контрольный срок неизвестен" : "До контрольного срока"}
                        </p>
                      </div>
                      <span className="text-xs font-semibold text-slate-500">{timer.progress}%</span>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        aria-label={`${timer.label}: ${timerStatusLabel(timer.status)}`}
                        className={`h-full rounded-full ${progressTone(timer.status)}`}
                        style={{ width: `${timer.status === "unknown" ? 100 : Math.max(4, timer.progress)}%` }}
                      />
                    </div>
                  </section>
                )) : (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="font-semibold text-white">SLA / OLA</p>
                    <p className="mt-2 text-sm text-slate-400">Контрольные сроки для этого тикета не заданы.</p>
                  </section>
                )}
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "tools" ? (
              <div className="space-y-3">
                {viewModel.right.operations.length ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-white">{activeOperations.length ? "Операции выполняются" : "Последние операции"}</p>
                      <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs font-semibold text-slate-300">
                        {activeOperations.length ? `${activeOperations.length} активн.` : `${viewModel.right.operations.length} записей`}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2">
                      {viewModel.right.operations.slice(0, 4).map((operation) => (
                        <OperationSummaryCard
                          isCanceling={operationCancelMutation.isPending}
                          isRetrying={operationRetryMutation.isPending}
                          key={operation.id}
                          onCancel={(operationId) => operationCancelMutation.mutate(operationId)}
                          onRetry={(operationId) => operationRetryMutation.mutate(operationId)}
                          operation={operation}
                        />
                      ))}
                    </div>
                  </section>
                ) : null}
                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-white">Инструменты / Playbook</p>
                    <button
                      className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                      disabled={playbookRunMutation.isPending || !firstRunnablePlaybook}
                      onClick={() => playbookRunMutation.mutate()}
                      type="button"
                    >
                      Запустить
                    </button>
                  </div>
                  <div className="mt-4 grid gap-2">
                    {visibleAutomationItems.map((item) => {
                      const Icon = toolIcon(item);
                      return (
                        <div
                          className={`rounded-xl border p-3 ${item.enabled ? "border-white/10 bg-white/[0.03]" : "border-white/5 bg-white/[0.02] opacity-55"}`}
                          key={`${item.id}:${item.title}`}
                          title={item.disabledReason ?? `${item.kind === "playbook" ? "Playbook" : "Инструмент"}: ${item.title}`}
                        >
                          <div className="flex items-start gap-3">
                            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/15 text-blue-200">
                              <Icon className="h-4 w-4" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-white" title={item.title}>
                                  {item.title}
                                </p>
                                <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-semibold text-slate-400">
                                  {item.kind === "playbook" ? "Playbook" : "Инструмент"}
                                </span>
                              </div>
                              <p className="truncate text-xs text-slate-400" title={item.subtitle}>
                                {item.subtitle}
                              </p>
                            </div>
                          </div>
                          {item.metaLabels.length ? (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {item.metaLabels.slice(0, 4).map((label) => (
                                <span
                                  className="max-w-full break-all rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-slate-400"
                                  key={`${item.id}:${label}`}
                                  title={label}
                                >
                                  {label}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {!item.enabled && item.disabledReason ? (
                            <p
                              className="mt-2 break-all rounded-lg border border-amber-400/20 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-100"
                              title={item.disabledReason}
                            >
                              {item.disabledReason}
                            </p>
                          ) : null}
                        </div>
                      );
                    })}
                    {!viewModel.right.playbooks.length && !viewModel.right.tools.length ? (
                      <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-6 text-sm text-slate-400">
                        Доступные инструменты не найдены или устройство offline.
                      </p>
                    ) : null}
                  </div>
                </section>
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "knowledge" ? (
              <div className="space-y-3">
                {viewModel.right.knowledge.aiSummary ? (
                  <section className="rounded-xl border border-violet-400/20 bg-violet-500/10 p-4">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-violet-300" />
                      <p className="font-semibold text-white">AI-рекомендация / Бета</p>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{viewModel.right.knowledge.aiSummary.text}</p>
                    {viewModel.right.knowledge.aiSummary.sources.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {viewModel.right.knowledge.aiSummary.sources.map((source) => (
                          <span className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs text-slate-300" key={source}>
                            {source}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1">
                        Провайдер: {viewModel.right.knowledge.diagnostics.providerStatusLabel}
                      </span>
                      <span
                        className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1"
                        title={`Технический ID: ${viewModel.right.knowledge.diagnostics.provider}`}
                      >
                        ID: {viewModel.right.knowledge.diagnostics.provider}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1">
                        Каталог: {viewModel.right.knowledge.diagnostics.catalogEntryCount}
                      </span>
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1">
                        Внешняя БЗ: {viewModel.right.knowledge.diagnostics.externalProviderStatusLabel}
                      </span>
                      {viewModel.right.knowledge.diagnostics.fallbackReasonLabel ? (
                        <span className="rounded-full border border-amber-300/20 bg-amber-500/10 px-2.5 py-1 text-amber-100">
                          Fallback: {viewModel.right.knowledge.diagnostics.fallbackReasonLabel}
                        </span>
                      ) : null}
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1">
                        Доверие: {viewModel.right.knowledge.aiSummary.confidence}
                      </span>
                    </div>
                    {viewModel.right.knowledge.diagnostics.querySignals.length ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {viewModel.right.knowledge.diagnostics.querySignals.slice(0, 6).map((signal) => (
                          <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] text-slate-400" key={signal}>
                            {signal}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {viewModel.right.knowledge.diagnostics.queryTokens.length ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {viewModel.right.knowledge.diagnostics.queryTokens.slice(0, 6).map((token) => (
                          <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-slate-500" key={`token:${token}`}>
                            token:{token}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ) : null}

                {(viewModel.right.knowledge.articles.length || viewModel.right.knowledge.similarTickets.length) ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-blue-300" />
                      <p className="font-semibold text-white">Связанные знания</p>
                    </div>
                    <div className="mt-4 space-y-2">
                      {viewModel.right.knowledge.articles.map((article) => (
                        <Link
                          className="block rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 transition hover:border-blue-400/40 hover:text-white"
                          key={article.id}
                          to={article.url}
                        >
                          <span className="block font-medium">{article.title}</span>
                          <span className="mt-1 block text-xs text-slate-500">{article.id}</span>
                        </Link>
                      ))}
                      {viewModel.right.knowledge.similarTickets.map((ticket) => (
                        <Link
                          className="block rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 transition hover:border-blue-400/40 hover:text-white"
                          key={ticket.id}
                          to={`/app/tickets/${ticket.id}`}
                        >
                          <span className="block font-medium">{ticket.subject}</span>
                          <span className="mt-1 block text-xs text-slate-500">
                            {ticket.code}
                            {ticket.summary ? ` · ${ticket.summary}` : ""}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </section>
                ) : (
              <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-violet-300" />
                  <p className="font-semibold text-white">AI-рекомендация / Бета</p>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  AI-рекомендация появится только при наличии связанных источников. Действия не запускаются без подтверждения оператора.
                </p>
                <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-400">
                  <BookOpen className="mr-2 inline h-4 w-4" />
                  Похожие тикеты и статьи не найдены.
                </div>
              </section>
                )}
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "passport" ? (
              <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Паспорт решения</p>
                    <p className="mt-1 font-semibold text-white">
                      Готовность {viewModel.right.passport.done}/{viewModel.right.passport.total}
                    </p>
                  </div>
                  <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(passportStatusTone(viewModel.right.passport))}`}>
                    {passportStatusLabel(viewModel.right.passport)}
                  </span>
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-emerald-400" style={{ width: `${passportProgress(viewModel.right.passport)}%` }} />
                </div>
                {closureFocus ? (
                  <div className="mt-4 rounded-xl border border-amber-400/25 bg-amber-500/10 px-4 py-3" data-testid="closure-focus-card">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-100/80">Фокус паспорта</p>
                        <p className="mt-1 break-words text-sm font-semibold text-white">{closureFocus.label}</p>
                        {closureGuide ? <p className="mt-1 text-xs font-semibold text-amber-100">Секция: {closureGuide.section}</p> : null}
                      </div>
                      <span className="shrink-0 rounded-md border border-amber-300/25 bg-white/[0.06] px-2 py-1 text-[11px] font-semibold text-amber-50">
                        {closureFocus.actionLabel}
                      </span>
                    </div>
                    {closureFocus.detail ? <p className="mt-2 break-words text-xs leading-5 text-amber-100/80">{closureFocus.detail}</p> : null}
                    {closureGuide ? (
                      <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-100/70">Следующий шаг</p>
                        <p className="mt-1 text-xs leading-5 text-amber-50">{closureGuide.hint}</p>
                      </div>
                    ) : null}
                    {closureGuide?.targetAction ? (
                      <div className="mt-2 rounded-lg border border-amber-300/20 bg-amber-300/10 px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-100/70">Целевое действие</p>
                        <p className="mt-1 text-xs font-semibold text-amber-50">{closureGuide.targetAction}</p>
                      </div>
                    ) : null}
                    {closureFocus.candidateCount > 0 ? (
                      <p className="mt-2 text-xs text-amber-100/70">Evidence candidates: {closureFocus.candidateCount}</p>
                    ) : null}
                    {closureFocus.actionKind === "attach_evidence" ? (
                      <div className="mt-3 space-y-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-3" data-testid="workspace-evidence-actions">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-100/70">Кандидаты evidence</p>
                            <p className="mt-1 text-xs leading-5 text-amber-50">
                              Используются реальные источники паспорта: операции, worklog, чат, согласования и observer trace.
                            </p>
                          </div>
                          <button
                            className="shrink-0 rounded-md border border-amber-300/25 bg-white/[0.05] px-2 py-1 text-[11px] font-semibold text-amber-50 hover:bg-white/[0.1]"
                            onClick={() => evidenceCandidatesQuery.refetch()}
                            type="button"
                          >
                            Обновить
                          </button>
                        </div>
                        {evidenceCandidatesQuery.isLoading ? (
                          <p className="text-xs text-slate-400">Загружаем кандидатов...</p>
                        ) : evidenceCandidatesQuery.data?.candidates.length ? (
                          <div className="space-y-2">
                            {evidenceCandidatesQuery.data.candidates.slice(0, 4).map((candidate) => (
                              <div className="rounded-lg border border-white/10 bg-black/10 px-3 py-2" key={candidate.candidate_id}>
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="break-words text-sm font-semibold text-white">{candidate.title}</p>
                                    {candidate.summary ? (
                                      <p className="mt-1 break-words text-xs leading-5 text-slate-300">{candidate.summary}</p>
                                    ) : null}
                                    <p className="mt-1 text-[11px] text-slate-500">
                                      {candidate.source_kind} · {candidate.source_ref} · {candidate.required_fact}
                                    </p>
                                  </div>
                                  <button
                                    className="shrink-0 rounded-md border border-blue-300/30 bg-blue-500/15 px-2 py-1 text-[11px] font-semibold text-blue-100 hover:bg-blue-500/25 disabled:cursor-not-allowed disabled:opacity-50"
                                    disabled={Boolean(candidate.existing_evidence_id) || evidenceLinkMutation.isPending}
                                    onClick={() => evidenceLinkMutation.mutate(candidate)}
                                    type="button"
                                  >
                                    {candidate.existing_evidence_id ? "Привязано" : "Привязать evidence"}
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="rounded-md border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-50">
                            Кандидаты не найдены. Добавьте ручное evidence, если проверка выполнена вне автоматических источников.
                          </p>
                        )}
                        <form
                          className="grid gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            manualEvidenceMutation.mutate();
                          }}
                        >
                          <label className="text-xs font-semibold text-amber-100">
                            Название evidence
                            <input
                              className="mt-1 h-9 w-full rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none placeholder:text-slate-500"
                              onChange={(event) => setManualEvidenceTitle(event.target.value)}
                              value={manualEvidenceTitle}
                            />
                          </label>
                          <label className="text-xs font-semibold text-amber-100">
                            Краткое описание
                            <textarea
                              className="mt-1 min-h-[72px] w-full resize-none rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
                              onChange={(event) => setManualEvidenceSummary(event.target.value)}
                              value={manualEvidenceSummary}
                            />
                          </label>
                          <button
                            className="justify-self-start rounded-md border border-amber-300/25 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-amber-50 hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!manualEvidenceTitle.trim() || manualEvidenceMutation.isPending}
                            type="submit"
                          >
                            {manualEvidenceMutation.isPending ? "Добавляем..." : "Добавить evidence"}
                          </button>
                        </form>
                      </div>
                    ) : null}
                    {closureFocus.actionKind === "add_worklog" ? (
                      <form
                        className="mt-3 space-y-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-3"
                        data-testid="workspace-worklog-actions"
                        onSubmit={(event) => {
                          event.preventDefault();
                          worklogMutation.mutate();
                        }}
                      >
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-100/70">Новый worklog</p>
                          <p className="mt-1 text-xs leading-5 text-amber-50">
                            Запись попадёт в доменный worklog тикета и станет evidence-кандидатом для паспорта.
                          </p>
                        </div>
                        <label className="block text-xs font-semibold text-amber-100">
                          Минуты
                          <input
                            className="mt-1 h-9 w-full rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                            min={1}
                            onChange={(event) => setWorklogMinutes(event.target.value)}
                            type="number"
                            value={worklogMinutes}
                          />
                        </label>
                        <label className="block text-xs font-semibold text-amber-100">
                          Что сделано
                          <textarea
                            className="mt-1 min-h-[86px] w-full resize-none rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
                            onChange={(event) => setWorklogNote(event.target.value)}
                            value={worklogNote}
                          />
                        </label>
                        <button
                          className="rounded-md border border-blue-300/30 bg-blue-500/15 px-3 py-2 text-xs font-semibold text-blue-100 hover:bg-blue-500/25 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={worklogMutation.isPending}
                          type="submit"
                        >
                          {worklogMutation.isPending ? "Записываем..." : "Записать worklog"}
                        </button>
                      </form>
                    ) : null}
                  </div>
                ) : null}
                <div className="mt-4 space-y-2">
                  {viewModel.right.passport.items.map((item) => {
                    const focused = closureGuide?.passportItemKey === item.key;
                    return (
                      <div
                        className={`flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm ${
                          focused ? "border border-amber-300/25 bg-amber-400/10" : ""
                        }`}
                        data-testid={focused ? "closure-focused-passport-item" : undefined}
                        key={item.key}
                      >
                        {item.done ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <Clock3 className="h-4 w-4 text-slate-500" />}
                        <span className={item.done ? "text-slate-200" : focused ? "text-amber-50" : "text-slate-500"}>{item.label}</span>
                      </div>
                    );
                  })}
                </div>
                <Link
                  className="mt-5 inline-flex h-10 w-full items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-sm font-semibold text-slate-200 hover:text-white"
                  to={`/app/tickets/${selectedTicket.id}/passport/print`}
                >
                  <FileCheck2 className="mr-2 h-4 w-4" />
                  Открыть паспорт
                </Link>
              </section>
            ) : null}
          </div>
        </aside>
      </div>
    </section>
  );
}

function timerStatusToTone(status: string) {
  if (status === "breached") {
    return "danger";
  }
  if (status === "at_risk") {
    return "warning";
  }
  if (status === "ok") {
    return "success";
  }
  return "neutral";
}
