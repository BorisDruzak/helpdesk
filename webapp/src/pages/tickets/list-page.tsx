import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArchiveRestore,
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock3,
  Cpu,
  Eye,
  EyeOff,
  FileCheck2,
  Fingerprint,
  GripVertical,
  Inbox,
  Lock,
  LogOut,
  Mail,
  MapPin,
  MessageSquare,
  Monitor,
  Moon,
  Network,
  Paperclip,
  Phone,
  Play,
  RefreshCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Sun,
  Tags,
  type LucideIcon,
  UserRound,
  UsersRound,
  Wrench,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  attachSelectedDiagnosticEvidenceToPassport,
  buildDiagnosticBundle,
  evaluateDiagnosticFindings,
  getTicketDiagnosticsOverview,
  runDiagnosticProfile,
  type DiagnosticOverview,
  type DiagnosticStatus,
} from "../../features/diagnostics/api";
import { DiagnosticCenterPanel } from "../../features/diagnostics/diagnostic-center-panel";
import {
  createSupportTicketPassportEvidence,
  createSupportQueueSavedView,
  deleteSupportQueueSavedView,
  fetchSupportQueueSavedViews,
  fetchSupportQueue,
  fetchSupportTicketPassportEvidenceCandidates,
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
  linkSupportTicketPassportEvidence,
  postSupportOperationCancel,
  postSupportOperationRetry,
  postSupportTicketArchive,
  postSupportTicketAssign,
  postSupportTicketHide,
  postSupportTicketMessage,
  postSupportTicketPlaybookRun,
  postSupportTicketPriority,
  postSupportTicketQueue,
  postSupportTicketReroute,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  postSupportTicketUnarchive,
  postSupportTicketUnhide,
  postSupportTicketWorklog,
  postSupportQueueMassAction,
  postSupportWorkspaceCleanupNoise,
  updateSupportQueueSavedView,
  type SupportQueueMassActionRequest,
  type SupportQueueSavedViewUpsertRequest,
  type SupportQueueScope,
  type SupportTicketEvidenceCandidatePayload,
  type SupportTicketTimelineFilter,
  type SupportTicketWorkspacePayload,
} from "../../features/queues/api";
import {
  mapSupportTimelineEntries,
  mapSupportWorkspaceViewModel,
} from "../../features/queues/support-workspace-mappers";
import { operationActionReasonSentence } from "../../features/queues/support-workspace-labels";
import { getSharedWebRealtimeClient } from "../../shared/realtime/client";
import type {
  SupportWorkspacePassport,
  SupportWorkspaceClosurePlan,
  SupportWorkspaceOperationSummary,
  SupportWorkspaceObserverDiagnostic,
  SupportWorkspaceTimer,
  SupportWorkspaceTimelineKind,
  SupportWorkspaceToolItem,
} from "../../features/queues/support-workspace-model";
import { useSession } from "../../features/auth/session-provider";
import { fetchTicketProblemLinks } from "../../features/problems/api";
import { RemoteAssistPanel } from "../../features/remote-assist/remote-assist-panel";
import { ExpandedWorkspaceHeader } from "./components/expanded-workspace-header";
import { OperationsTable } from "./components/operations-table";
import { QueueExplorer } from "./components/queue-explorer";
import { TicketPreviewPanel } from "./components/ticket-preview-panel";
import {
  getInitialWorkspaceMode,
  getInitialWorkspaceRightTab,
  getInitialWorkspaceSelectedQueue,
  getInitialWorkspaceSelectedView,
  persistWorkspaceMode,
  persistWorkspaceRightTab,
  persistWorkspaceSelectedQueue,
  persistWorkspaceSelectedView,
  type WorkspaceMode,
  type WorkspaceRightTab,
} from "./workspace-types";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;
const SUPPORT_OPERATION_REFRESH_MS = 2_500;
const SUPPORT_SELECTED_TICKET_FALLBACK_REFRESH_MS = 15_000;
const LIVE_OPERATION_STATUSES = new Set(["accepted", "queued", "running", "sent", "in_progress", "waiting_consent"]);

type ComposerMode = "public" | "internal";
type SidebarTab = WorkspaceRightTab;
type TimelineFilter = "all" | SupportWorkspaceTimelineKind;
type SupportWorkspaceTheme = "dark" | "light";
type OperatorActionKind = "status" | "assign_self" | "queue" | "priority" | "reroute";
type AutomationCatalogFilter = "all" | "runnable" | "playbook" | "tool" | "disabled";
type WorkspaceResizePane = "left" | "right";
type ToolsWorkspaceTab = "diagnostics" | "quick" | "playbook" | "remote" | "operations" | "history";
type SlaWorkspaceTab = "overview" | "ola" | "escalations" | "history";
type PassportWorkspaceTab = "sections" | "evidence" | "operations" | "readiness";
type WorkspaceColumnSizes = { left: number; right: number };
type WorkspaceColumnsByMode = Partial<Record<WorkspaceMode, WorkspaceColumnSizes>>;
type WorkspaceGridPreset = { left: string; center: string; right: string };
type WorkspaceResizeState = {
  pane: WorkspaceResizePane;
  startX: number;
  startLeft: number;
  startRight: number;
};
type AutomationLaunchDraft =
  | { kind: "tool"; id: string }
  | { kind: "playbook"; id: string }
  | null;

type OperatorActionDraft = {
  kind: OperatorActionKind;
  targetStatus: string;
  queueId: number | null;
  priority: "P0" | "P1" | "P2" | "P3";
  reason: string;
  comment: string;
};

type ResolutionCloseDraft = {
  resolutionCode: string;
  requesterResolutionSummary: string;
  resolutionSummary: string;
  reason: string;
};

type ClosurePlanBlocker = SupportWorkspaceClosurePlan["blockers"][number];

const CLOSURE_BLOCKER_VISIBLE_LIMIT = 4;
const SUPPORT_WORKSPACE_THEME_STORAGE_KEY = "support-workspace-theme";
const SUPPORT_WORKSPACE_COLUMNS_STORAGE_KEY = "support-workspace-columns";
const DEFAULT_WORKSPACE_COLUMNS_BY_MODE: Record<WorkspaceMode, WorkspaceColumnSizes> = {
  ticket: { left: 300, right: 340 },
  queue: { left: 760, right: 72 },
  tools: { left: 300, right: 760 },
  sla: { left: 300, right: 760 },
  passport: { left: 300, right: 820 },
};
const WORKSPACE_COLUMN_LIMITS_BY_MODE: Record<
  WorkspaceMode,
  { leftMin: number; leftMax: number; rightMin: number; rightMax: number; centerMin: number }
> = {
  ticket: { leftMin: 260, leftMax: 420, rightMin: 300, rightMax: 460, centerMin: 560 },
  queue: { leftMin: 620, leftMax: 940, rightMin: 56, rightMax: 220, centerMin: 320 },
  tools: { leftMin: 260, leftMax: 360, rightMin: 560, rightMax: 980, centerMin: 360 },
  sla: { leftMin: 260, leftMax: 360, rightMin: 580, rightMax: 980, centerMin: 380 },
  passport: { leftMin: 260, leftMax: 360, rightMin: 620, rightMax: 1040, centerMin: 360 },
};

function getInitialSupportWorkspaceTheme(): SupportWorkspaceTheme {
  if (typeof window === "undefined") {
    return "dark";
  }
  return window.localStorage.getItem(SUPPORT_WORKSPACE_THEME_STORAGE_KEY) === "light" ? "light" : "dark";
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function normalizeWorkspaceColumnsForMode(mode: WorkspaceMode, sizes: WorkspaceColumnSizes, viewportWidth: number): WorkspaceColumnSizes {
  const limits = WORKSPACE_COLUMN_LIMITS_BY_MODE[mode];
  let left = clampNumber(sizes.left, limits.leftMin, limits.leftMax);
  let right = clampNumber(sizes.right, limits.rightMin, limits.rightMax);
  const maxSidebarsWidth = Math.max(
    limits.leftMin + limits.rightMin,
    viewportWidth - limits.centerMin,
  );
  if (left + right > maxSidebarsWidth) {
    const rightReduction = Math.min(right - limits.rightMin, left + right - maxSidebarsWidth);
    right -= rightReduction;
    const remainingOverflow = left + right - maxSidebarsWidth;
    if (remainingOverflow > 0) {
      left = clampNumber(left - remainingOverflow, limits.leftMin, limits.leftMax);
    }
  }
  return { left, right };
}

function normalizeWorkspaceColumnsByMode(columnsByMode: WorkspaceColumnsByMode, viewportWidth: number): WorkspaceColumnsByMode {
  return (Object.keys(DEFAULT_WORKSPACE_COLUMNS_BY_MODE) as WorkspaceMode[]).reduce<WorkspaceColumnsByMode>((accumulator, mode) => {
    accumulator[mode] = normalizeWorkspaceColumnsForMode(
      mode,
      columnsByMode[mode] ?? DEFAULT_WORKSPACE_COLUMNS_BY_MODE[mode],
      viewportWidth,
    );
    return accumulator;
  }, {});
}

function getInitialWorkspaceColumnsByMode(): WorkspaceColumnsByMode {
  if (typeof window === "undefined") {
    return DEFAULT_WORKSPACE_COLUMNS_BY_MODE;
  }
  const viewportWidth = window.innerWidth || 1366;
  try {
    const raw = window.localStorage.getItem(SUPPORT_WORKSPACE_COLUMNS_STORAGE_KEY);
    if (!raw) {
      return normalizeWorkspaceColumnsByMode(DEFAULT_WORKSPACE_COLUMNS_BY_MODE, viewportWidth);
    }
    const parsed = JSON.parse(raw) as Partial<WorkspaceColumnSizes & WorkspaceColumnsByMode>;
    if (typeof parsed.left === "number" || typeof parsed.right === "number") {
      return normalizeWorkspaceColumnsByMode(
        {
          ...DEFAULT_WORKSPACE_COLUMNS_BY_MODE,
          ticket: {
            left: Number(parsed.left) || DEFAULT_WORKSPACE_COLUMNS_BY_MODE.ticket.left,
            right: Number(parsed.right) || DEFAULT_WORKSPACE_COLUMNS_BY_MODE.ticket.right,
          },
        },
        viewportWidth,
      );
    }
    return normalizeWorkspaceColumnsByMode(parsed as WorkspaceColumnsByMode, viewportWidth);
  } catch {
    return normalizeWorkspaceColumnsByMode(DEFAULT_WORKSPACE_COLUMNS_BY_MODE, viewportWidth);
  }
}

function getWorkspaceGridPreset(mode: WorkspaceMode, columns: WorkspaceColumnSizes, viewportWidth: number): WorkspaceGridPreset {
  const isNarrow = viewportWidth < 1366;
  const isCompact = viewportWidth < 1200;
  if (isCompact) {
    if (mode === "queue") {
      return { left: "minmax(0, 1fr)", center: "0px", right: "0px" };
    }
    if (mode === "ticket") {
      return { left: "260px", center: "minmax(480px, 1fr)", right: "0px" };
    }
    return { left: "260px", center: "minmax(480px, 1fr)", right: "0px" };
  }
  if (mode === "ticket") {
    return {
      left: `${isNarrow ? Math.min(columns.left, 280) : columns.left}px`,
      center: `minmax(${isNarrow ? 560 : 620}px, 1fr)`,
      right: `${isNarrow ? Math.min(columns.right, 300) : columns.right}px`,
    };
  }
  if (mode === "queue") {
    return { left: `${columns.left}px`, center: "minmax(320px, 1fr)", right: `${columns.right}px` };
  }
  if (mode === "tools") {
    return isNarrow
      ? { left: `${Math.min(columns.left, 280)}px`, center: "minmax(320px, 1fr)", right: `${Math.min(columns.right, 720)}px` }
      : { left: `${columns.left}px`, center: "minmax(380px, 1fr)", right: `${columns.right}px` };
  }
  if (mode === "sla") {
    return isNarrow
      ? { left: `${Math.min(columns.left, 280)}px`, center: "minmax(340px, 1fr)", right: `${Math.min(columns.right, 720)}px` }
      : { left: `${columns.left}px`, center: "minmax(400px, 1fr)", right: `${columns.right}px` };
  }
  return isNarrow
    ? { left: `${Math.min(columns.left, 280)}px`, center: "minmax(320px, 1fr)", right: `${Math.min(columns.right, 740)}px` }
    : { left: `${columns.left}px`, center: "minmax(380px, 1fr)", right: `${columns.right}px` };
}

function getWorkspaceGridStyle(mode: WorkspaceMode, columns: WorkspaceColumnSizes, viewportWidth: number): CSSProperties {
  const preset = getWorkspaceGridPreset(mode, columns, viewportWidth);
  return {
    "--support-left": preset.left,
    "--support-center": preset.center,
    "--support-right": preset.right,
    gridTemplateColumns: "var(--support-left) var(--support-center) var(--support-right)",
  } as CSSProperties;
}

function workspaceHasLiveOperations(payload: SupportTicketWorkspacePayload | undefined): boolean {
  return Boolean(
    payload?.detail.snapshot.latest_operations.some((operation) => {
      const status = operation.display_status ?? operation.status;
      return LIVE_OPERATION_STATUSES.has(status);
    }),
  );
}

const sidebarTabs: Array<{ value: SidebarTab; label: string }> = [
  { value: "context", label: "Контекст" },
  { value: "quality", label: "Quality" },
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

const automationCatalogFilters: Array<{ value: AutomationCatalogFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "runnable", label: "Можно запустить" },
  { value: "playbook", label: "Playbooks" },
  { value: "tool", label: "Инструменты" },
  { value: "disabled", label: "Недоступные" },
];

const toolsWorkspaceTabs: Array<{ value: ToolsWorkspaceTab; label: string }> = [
  { value: "diagnostics", label: "Диагностика" },
  { value: "quick", label: "Быстрые" },
  { value: "playbook", label: "Playbook" },
  { value: "remote", label: "Удалённая помощь" },
  { value: "operations", label: "Операции" },
  { value: "history", label: "История" },
];

const slaWorkspaceTabs: Array<{ value: SlaWorkspaceTab; label: string }> = [
  { value: "overview", label: "SLA обзор" },
  { value: "ola", label: "OLA" },
  { value: "escalations", label: "Эскалации" },
  { value: "history", label: "История сроков" },
];

const passportWorkspaceTabs: Array<{ value: PassportWorkspaceTab; label: string }> = [
  { value: "sections", label: "Секции" },
  { value: "evidence", label: "Доказательства" },
  { value: "operations", label: "Операции" },
  { value: "readiness", label: "Готовность" },
];

function matchesAutomationSearch(item: SupportWorkspaceToolItem, search: string): boolean {
  if (!search) {
    return true;
  }
  const haystack = [item.id, item.title, item.subtitle, item.riskLabel, item.disabledReason, ...item.metaLabels]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(search);
}

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

function makeResolutionCloseDraft(ticket: { resolutionCode: string; requesterResolutionSummary: string; resolutionSummary: string } | null): ResolutionCloseDraft {
  return {
    resolutionCode: ticket?.resolutionCode ?? "",
    requesterResolutionSummary: ticket?.requesterResolutionSummary ?? "",
    resolutionSummary: ticket?.resolutionSummary ?? "",
    reason: "",
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

function diagnosticStatusClass(status: DiagnosticStatus) {
  if (status === "ok") {
    return "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
  }
  if (status === "error") {
    return "border-red-400/30 bg-red-500/10 text-red-100";
  }
  if (status === "warning") {
    return "border-amber-400/30 bg-amber-500/10 text-amber-100";
  }
  return "border-white/10 bg-white/[0.04] text-slate-300";
}

function DiagnosticOverviewPanel({
  isAttachingPassport,
  isBuildingBundle,
  isEvaluating,
  isLoading,
  isRunningProfile,
  onAttachPassport,
  onBuildBundle,
  onEvaluateFindings,
  onRunProfile,
  overview,
}: {
  isAttachingPassport: boolean;
  isBuildingBundle: boolean;
  isEvaluating: boolean;
  isLoading: boolean;
  isRunningProfile: boolean;
  onAttachPassport: () => void;
  onBuildBundle: () => void;
  onEvaluateFindings: () => void;
  onRunProfile: () => void;
  overview?: DiagnosticOverview;
}) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
        Загрузка диагностики...
      </div>
    );
  }
  if (!overview) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
        Диагностические данные пока не собраны.
      </div>
    );
  }
  const evidenceTotal = Object.values(overview.evidence_counts).reduce((sum, value) => sum + value, 0);
  const perspectives = ["endpoint", "server", "monitoring", "observer", "remote_assist", "manual"];
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{overview.profile?.title ?? "Diagnostics"}</p>
            <p className="mt-1 text-sm font-semibold text-white">{overview.summary}</p>
          </div>
          <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${diagnosticStatusClass(overview.status)}`}>
            {overview.status}
          </span>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-5">
          {(["ok", "warning", "error", "info", "unknown"] as const).map((status) => (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2" key={status}>
              <p className="text-xs text-slate-500">{status}</p>
              <p className="text-lg font-semibold text-white">{overview.evidence_counts[status] ?? 0}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">Всего evidence: {evidenceTotal}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-blue-400/30 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-100 transition hover:border-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isRunningProfile}
            onClick={onRunProfile}
            type="button"
          >
            {isRunningProfile ? "Запуск..." : "Запустить профиль"}
          </button>
          <button
            className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isEvaluating}
            onClick={onEvaluateFindings}
            type="button"
          >
            {isEvaluating ? "Расчёт..." : "Пересчитать вывод"}
          </button>
          <button
            className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isBuildingBundle}
            onClick={onBuildBundle}
            type="button"
          >
            {isBuildingBundle ? "Сборка..." : "Собрать пакет"}
          </button>
          <button
            className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isAttachingPassport || !overview.latest_evidence.some((item) => item.selected_for_passport)}
            onClick={onAttachPassport}
            type="button"
          >
            {isAttachingPassport ? "Отправка..." : "В паспорт"}
          </button>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        {perspectives.map((key) => {
          const item = overview.perspectives[key];
          return (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3" key={key}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">{key}</p>
                <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${diagnosticStatusClass(item?.status ?? "unknown")}`}>
                  {item?.count ?? 0}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-xs text-slate-400">{item?.latest?.summary ?? "Нет фактов"}</p>
            </div>
          );
        })}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <p className="text-sm font-semibold text-white">Последние факты</p>
          <div className="mt-2 space-y-2">
            {overview.latest_evidence.slice(0, 5).map((item) => (
              <div className="rounded-lg border border-white/10 bg-black/10 px-3 py-2" key={item.id}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-white">{item.title}</p>
                  <span className={diagnosticStepTextClass(item.status)}>{item.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-slate-400">{item.summary ?? item.kind}</p>
              </div>
            ))}
            {!overview.latest_evidence.length ? <p className="py-4 text-center text-sm text-slate-400">Evidence пока нет.</p> : null}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <p className="text-sm font-semibold text-white">Вывод и следующие действия</p>
          <div className="mt-2 space-y-2">
            {overview.findings.slice(0, 4).map((finding) => (
              <div className="rounded-lg border border-white/10 bg-black/10 px-3 py-2" key={finding.id}>
                <p className="text-sm font-semibold text-white">{finding.title}</p>
                <p className="mt-1 text-xs text-slate-400">{finding.description ?? finding.root_cause_code}</p>
              </div>
            ))}
            {!overview.findings.length ? <p className="text-sm text-slate-400">Подтверждённых выводов пока нет.</p> : null}
            {overview.recommended_actions.slice(0, 4).map((action) => (
              <p className="rounded-lg border border-blue-400/20 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-100" key={action.id}>
                {action.title}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
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
        {operation.traceUrl ? (
          <a
            className="rounded-md border border-blue-300/20 bg-blue-500/10 px-2 py-1 text-[11px] font-semibold text-blue-100 hover:bg-blue-500/20"
            href={operation.traceUrl}
            rel="noreferrer"
            target="_blank"
            title={`${operation.traceRelationLabel}: открыть трассу в observer`}
          >
            {operation.traceRelationLabel}
          </a>
        ) : null}
        {operation.rootTraceUrl && operation.traceUrl !== operation.rootTraceUrl ? (
          <a
            className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-semibold text-slate-200 hover:text-white"
            href={operation.rootTraceUrl}
            rel="noreferrer"
            target="_blank"
            title="Открыть root trace тикета"
          >
            Root trace
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
            title={
              operation.requiresConsentForRetry
                ? "Запросить новое согласие пользователя и создать безопасный повтор операции"
                : "Повторить операцию через policy-aware retry"
            }
            type="button"
          >
            {operation.requiresConsentForRetry ? "Запросить согласие и повторить" : "Повторить"}
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

function ObserverDiagnosticCard({
  isLightTheme,
  observer,
}: {
  isLightTheme: boolean;
  observer: SupportWorkspaceObserverDiagnostic;
}) {
  const hasTrace = Boolean(observer.rootTraceId);
  const primaryTraceUrl = observer.rootTraceUrl ?? observer.relatedTraces[0]?.traceUrl ?? null;
  const traceRows = observer.errorTraces.length ? observer.errorTraces : observer.activeTraces.length ? observer.activeTraces : observer.relatedTraces.slice(0, 2);
  const shellClass = isLightTheme ? "border border-slate-200 bg-white text-slate-950 shadow-sm" : "border border-white/10 bg-[#111f33]";
  const mutedTextClass = isLightTheme ? "text-slate-600" : "text-slate-400";
  const subtlePanelClass = isLightTheme ? "border border-slate-200 bg-slate-50" : "border border-white/10 bg-white/[0.03]";

  return (
    <section className={`rounded-xl p-4 ${shellClass}`} data-testid="observer-diagnostic-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Observer</p>
          <p className={`mt-1 font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>Диагностика тикета</p>
        </div>
        <span className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(observer.healthTone)}`}>
          {observer.healthLabel}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-4 gap-2">
        {[
          ["Трассы", observer.traceCount],
          ["Активн.", observer.activeTraceCount],
          ["Ошибки", observer.errorTraceCount],
          ["Сигн.", observer.signatureCount],
        ].map(([label, value]) => (
          <div className={`rounded-lg px-2 py-2 text-center ${subtlePanelClass}`} key={String(label)}>
            <p className="text-[11px] text-slate-500">{label}</p>
            <p className={`mt-1 text-sm font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className={`mt-3 rounded-lg px-3 py-2 ${subtlePanelClass}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Root trace</p>
            <p className={`mt-1 break-all text-sm font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>{observer.rootTraceCompactId}</p>
            <p className={`mt-1 text-xs ${mutedTextClass}`}>
              {observer.rootKind} · {observer.rootTraceStatusLabel} · {observer.latestTraceLabel}
            </p>
          </div>
          {primaryTraceUrl ? (
            <a
              className={`shrink-0 rounded-md border px-2 py-1 text-[11px] font-semibold ${
                isLightTheme ? "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100" : "border-blue-300/30 bg-blue-500/15 text-blue-100 hover:bg-blue-500/25"
              }`}
              href={primaryTraceUrl}
              rel="noreferrer"
              target="_blank"
              title="Открыть трассу в observer workbench"
            >
              Открыть
            </a>
          ) : null}
        </div>
        {!hasTrace ? (
          <p className={`mt-2 text-xs leading-5 ${mutedTextClass}`}>
            Трасса ещё не создана. Она появится после первого события или операции по тикету.
          </p>
        ) : null}
      </div>

      {observer.latestErrorLabel ? (
        <div className={`mt-3 rounded-lg px-3 py-2 ${isLightTheme ? "border border-red-200 bg-red-50" : "border border-red-300/20 bg-red-500/10"}`}>
          <div className="flex items-start gap-2">
            <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${isLightTheme ? "text-red-700" : "text-red-200"}`} />
            <div className="min-w-0">
              <p className={`break-words text-sm font-semibold ${isLightTheme ? "text-red-950" : "text-red-50"}`}>{observer.latestErrorLabel}</p>
              <p className={`mt-1 text-xs ${isLightTheme ? "text-red-800" : "text-red-100/80"}`}>
                {observer.latestErrorStage ?? "stage неизвестен"}
                {observer.latestErrorAtLabel ? ` · ${observer.latestErrorAtLabel}` : ""}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className={`mt-3 flex items-start gap-2 rounded-lg px-3 py-2 ${subtlePanelClass}`}>
          <CheckCircle2 className={`mt-0.5 h-4 w-4 shrink-0 ${isLightTheme ? "text-emerald-700" : "text-emerald-300"}`} />
          <p className={`text-xs leading-5 ${mutedTextClass}`}>Критичных ошибок по observer-сводке сейчас нет.</p>
        </div>
      )}

      {observer.topSignature ? (
        <div className={`mt-3 rounded-lg px-3 py-2 ${subtlePanelClass}`}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Top signature</p>
          <p className={`mt-1 break-words text-sm font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>{observer.topSignature.title}</p>
          <p className={`mt-1 text-xs ${mutedTextClass}`}>
            В тикете: {observer.topSignature.ticketOccurrences}
            {observer.topSignature.globalOccurrences !== null ? ` · глобально: ${observer.topSignature.globalOccurrences}` : ""}
            {observer.topSignature.lastSeenLabel ? ` · ${observer.topSignature.lastSeenLabel}` : ""}
          </p>
        </div>
      ) : null}

      {traceRows.length ? (
        <div className="mt-3 space-y-2">
          {traceRows.slice(0, 3).map((trace) => {
            const traceHref = trace.traceUrl ?? primaryTraceUrl;
            const content = (
              <>
                <span className={`block truncate font-semibold ${isLightTheme ? "text-slate-950" : "text-slate-100"}`}>{trace.title}</span>
                <span className={`mt-1 block ${mutedTextClass}`}>
                  {trace.compactId} · {trace.statusLabel} · ошибок: {trace.errorCount}
                </span>
              </>
            );
            return traceHref ? (
              <a
                className={`block rounded-lg px-3 py-2 text-xs transition ${subtlePanelClass} ${isLightTheme ? "hover:border-blue-300" : "hover:border-blue-300/40"}`}
                href={traceHref}
                key={trace.id}
                rel="noreferrer"
                target="_blank"
              >
                {content}
              </a>
            ) : (
              <div className={`rounded-lg px-3 py-2 text-xs ${subtlePanelClass}`} key={trace.id}>
                {content}
              </div>
            );
          })}
        </div>
      ) : null}

      {observer.summaryEndpoint ? (
        <p className="mt-3 break-all text-[11px] text-slate-500" title={observer.summaryEndpoint}>
          Summary API: {observer.summaryEndpoint}
        </p>
      ) : null}
    </section>
  );
}

function SupportWorkspaceTopbar({
  theme,
  onToggleTheme,
  onLogout,
  notificationCount,
  onRefresh,
  refreshing,
  userLogin,
  userRole,
}: {
  theme: SupportWorkspaceTheme;
  onToggleTheme: () => void;
  onLogout: () => void;
  notificationCount: number;
  onRefresh: () => void;
  refreshing: boolean;
  userLogin: string;
  userRole: string;
}) {
  const isLightTheme = theme === "light";
  const navItems = [
    { label: "Тикеты", to: "/app/tickets", icon: ClipboardList, active: true },
    { label: "Отчёты", to: "/app/reports", icon: BarChart3, active: false },
    { label: "Знания", to: "/app/knowledge", icon: BookOpen, active: false },
    { label: "Настройки", to: "/app/settings", icon: Settings2, active: false },
  ];

  return (
    <header className={`flex h-16 shrink-0 items-center gap-3 border-b px-4 backdrop-blur-xl ${isLightTheme ? "border-slate-200 bg-white/95 text-slate-950" : "border-white/10 bg-[#081321]/95 text-slate-100"}`}>
      <Link className="flex min-w-[180px] items-center gap-3" to="/app/tickets">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-950/40">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="text-base font-semibold">Service Desk</span>
        <span className="sr-only">Тикеты</span>
      </Link>

      <nav
        aria-label="Разделы поддержки"
        className={`hidden items-center gap-1 rounded-xl border p-1 min-[1180px]:flex ${isLightTheme ? "border-slate-200 bg-slate-100" : "border-white/10 bg-white/[0.04]"}`}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              className={`inline-flex h-9 items-center gap-2 rounded-lg px-2.5 text-xs font-semibold transition ${
                item.active
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-950/20"
                  : isLightTheme
                    ? "text-slate-600 hover:bg-white hover:text-slate-950"
                    : "text-slate-400 hover:bg-white/[0.06] hover:text-white"
              }`}
              key={item.to}
              to={item.to}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-1.5">
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500"
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
        <div className="hidden items-center gap-3 pl-2 md:flex">
          <div className={`flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl ${isLightTheme ? "bg-slate-200" : "bg-slate-700"}`}>
            <UserRound className={`h-5 w-5 ${isLightTheme ? "text-slate-700" : "text-slate-200"}`} />
          </div>
          <div className="leading-tight">
            <p className={`text-sm font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>{userLogin}</p>
            <p className={`text-xs ${isLightTheme ? "text-slate-500" : "text-slate-400"}`}>{userRole}</p>
          </div>
        </div>
        <button
          aria-label="Выйти из Service Desk"
          className={`flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-semibold transition ${isLightTheme ? "border-slate-200 bg-slate-100 text-slate-700 hover:text-slate-950" : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"}`}
          onClick={onLogout}
          title="Выйти"
          type="button"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden 2xl:inline">Выйти</span>
        </button>
      </div>
    </header>
  );
}

export function TicketListPage() {
  const navigate = useNavigate();
  const params = useParams<{ ticketId?: string }>();
  const queryClient = useQueryClient();
  const { logout, session } = useSession();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [smartView, setSmartView] = useState(() => getInitialWorkspaceSelectedView("my_action"));
  const [activeQueueId, setActiveQueueId] = useState<string | null>(() => getInitialWorkspaceSelectedQueue());
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(params.ticketId ?? null);
  const [search, setSearch] = useState("");
  const [composerMode, setComposerMode] = useState<ComposerMode>("public");
  const [composerText, setComposerText] = useState("");
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>("all");
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>(() => getInitialWorkspaceRightTab());
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>(() => getInitialWorkspaceMode());
  const [moreOpen, setMoreOpen] = useState(false);
  const [toolsWorkspaceTab, setToolsWorkspaceTab] = useState<ToolsWorkspaceTab>("quick");
  const [slaWorkspaceTab, setSlaWorkspaceTab] = useState<SlaWorkspaceTab>("overview");
  const [passportWorkspaceTab, setPassportWorkspaceTab] = useState<PassportWorkspaceTab>("sections");
  const [operatorActionDraft, setOperatorActionDraft] = useState<OperatorActionDraft | null>(null);
  const [automationLaunchDraft, setAutomationLaunchDraft] = useState<AutomationLaunchDraft>(null);
  const [resolutionCloseDraft, setResolutionCloseDraft] = useState<ResolutionCloseDraft | null>(null);
  const [closureFocus, setClosureFocus] = useState<ClosurePlanBlocker | null>(null);
  const [closureBlockersExpanded, setClosureBlockersExpanded] = useState(false);
  const [manualEvidenceTitle, setManualEvidenceTitle] = useState("");
  const [manualEvidenceSummary, setManualEvidenceSummary] = useState("");
  const [worklogMinutes, setWorklogMinutes] = useState("15");
  const [worklogNote, setWorklogNote] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [workspaceTheme, setWorkspaceTheme] = useState<SupportWorkspaceTheme>(() => getInitialSupportWorkspaceTheme());
  const [workspaceColumnsByMode, setWorkspaceColumnsByMode] = useState<WorkspaceColumnsByMode>(() => getInitialWorkspaceColumnsByMode());
  const [workspaceViewportWidth, setWorkspaceViewportWidth] = useState(() => (typeof window === "undefined" ? 1366 : window.innerWidth || 1366));
  const [resizingPane, setResizingPane] = useState<WorkspaceResizePane | null>(null);
  const [automationCatalogFilter, setAutomationCatalogFilter] = useState<AutomationCatalogFilter>("all");
  const [automationCatalogSearch, setAutomationCatalogSearch] = useState("");
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const selectedTicketIdRef = useRef<string | null>(null);
  const resizeStateRef = useRef<WorkspaceResizeState | null>(null);
  const deferredSearch = useDeferredValue(search);
  const deferredAutomationCatalogSearch = useDeferredValue(automationCatalogSearch);
  const workspaceColumns = workspaceColumnsByMode[workspaceMode] ?? DEFAULT_WORKSPACE_COLUMNS_BY_MODE[workspaceMode];
  const isCompactWorkspace = workspaceViewportWidth < 1200;
  const rightPanelInDrawer = isCompactWorkspace && workspaceMode !== "queue";
  const canResizeWorkspace = workspaceViewportWidth >= 1200;

  useEffect(() => {
    setSelectedTicketId(params.ticketId ?? null);
  }, [params.ticketId]);

  useEffect(() => {
    selectedTicketIdRef.current = selectedTicketId;
  }, [selectedTicketId]);

  useEffect(() => {
    persistWorkspaceMode(workspaceMode);
  }, [workspaceMode]);

  useEffect(() => {
    if ((workspaceMode === "tools" || workspaceMode === "sla" || workspaceMode === "passport") && sidebarTab !== workspaceMode) {
      setSidebarTab(workspaceMode);
    }
  }, [sidebarTab, workspaceMode]);

  useEffect(() => {
    persistWorkspaceRightTab(sidebarTab);
  }, [sidebarTab]);

  useEffect(() => {
    persistWorkspaceSelectedView(smartView);
  }, [smartView]);

  useEffect(() => {
    persistWorkspaceSelectedQueue(activeQueueId);
  }, [activeQueueId]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setWorkspaceMode((current) => (current === "ticket" ? current : "ticket"));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const handleViewportResize = () => {
      setWorkspaceColumnsByMode((current) => normalizeWorkspaceColumnsByMode(current, window.innerWidth || 1366));
    };
    window.addEventListener("resize", handleViewportResize);
    return () => window.removeEventListener("resize", handleViewportResize);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(SUPPORT_WORKSPACE_COLUMNS_STORAGE_KEY, JSON.stringify(workspaceColumnsByMode));
    } catch {
      // Layout persistence is best-effort; the workspace stays usable without localStorage.
    }
  }, [workspaceColumnsByMode]);

  useEffect(() => {
    const handleResize = () => setWorkspaceViewportWidth(window.innerWidth || 1366);
    window.addEventListener("resize", handleResize, { passive: true });
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!resizingPane) {
      return;
    }
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handlePointerMove = (event: PointerEvent) => {
      const resizeState = resizeStateRef.current;
      if (!resizeState) {
        return;
      }
      const delta = event.clientX - resizeState.startX;
      const viewportWidth = window.innerWidth || 1366;
      setWorkspaceColumnsByMode((current) => {
        const currentSizes = current[workspaceMode] ?? DEFAULT_WORKSPACE_COLUMNS_BY_MODE[workspaceMode];
        const limits = WORKSPACE_COLUMN_LIMITS_BY_MODE[workspaceMode];
        if (resizeState.pane === "left") {
          const maxLeft = Math.min(
            limits.leftMax,
            viewportWidth - currentSizes.right - limits.centerMin,
          );
          return {
            ...current,
            [workspaceMode]: {
              ...currentSizes,
              left: clampNumber(resizeState.startLeft + delta, limits.leftMin, maxLeft),
            },
          };
        }
        const maxRight = Math.min(
          limits.rightMax,
          viewportWidth - currentSizes.left - limits.centerMin,
        );
        return {
          ...current,
          [workspaceMode]: {
            ...currentSizes,
            right: clampNumber(resizeState.startRight - delta, limits.rightMin, maxRight),
          },
        };
      });
    };

    const handlePointerUp = () => {
      resizeStateRef.current = null;
      setResizingPane(null);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, [resizingPane, workspaceMode]);

  const queueQuery = useQuery({
    queryKey: ["tickets-workspace-queue", scope, smartView, deferredSearch, showArchive],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter: "all",
        smartView,
        query: deferredSearch,
        includeArchived: showArchive,
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS,
  });

  const queueSavedViewsQuery = useQuery({
    queryKey: ["tickets-workspace-queue-saved-views"],
    queryFn: fetchSupportQueueSavedViews,
    retry: false,
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
    refetchInterval: (query) => {
      const payload = query.state.data as SupportTicketWorkspacePayload | undefined;
      return workspaceHasLiveOperations(payload) ? SUPPORT_OPERATION_REFRESH_MS : SUPPORT_SELECTED_TICKET_FALLBACK_REFRESH_MS;
    },
  });

  const timelineApiFilter: SupportTicketTimelineFilter =
    timelineFilter === "message" ? "messages" : timelineFilter;

  const timelineQuery = useQuery({
    queryKey: ["tickets-workspace-timeline", selectedTicketId, timelineApiFilter],
    queryFn: () => fetchSupportTicketTimeline(selectedTicketId!, timelineApiFilter),
    enabled: Boolean(selectedTicketId),
    retry: false,
    refetchInterval: workspaceHasLiveOperations(workspaceQuery.data)
      ? SUPPORT_OPERATION_REFRESH_MS
      : SUPPORT_SELECTED_TICKET_FALLBACK_REFRESH_MS,
  });

  const evidenceCandidatesQuery = useQuery({
    queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId],
    queryFn: () => fetchSupportTicketPassportEvidenceCandidates(selectedTicketId!),
    enabled: Boolean(selectedTicketId) && sidebarTab === "passport" && closureFocus?.actionKind === "attach_evidence",
    retry: false,
  });

  const diagnosticsOverviewQuery = useQuery({
    queryKey: ["tickets-workspace-diagnostics-overview", selectedTicketId],
    queryFn: () => getTicketDiagnosticsOverview(selectedTicketId!),
    enabled: Boolean(selectedTicketId) && workspaceMode === "tools" && toolsWorkspaceTab === "diagnostics",
    retry: false,
    refetchInterval: workspaceHasLiveOperations(workspaceQuery.data)
      ? SUPPORT_OPERATION_REFRESH_MS
      : SUPPORT_SELECTED_TICKET_FALLBACK_REFRESH_MS,
  });

  const invalidateDiagnostics = (ticketId: string) =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["tickets-workspace-diagnostics-overview", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["tickets-workspace", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["tickets-workspace-passport-evidence-candidates", ticketId] }),
    ]);

  const diagnosticProfileRunMutation = useMutation({
    mutationFn: (ticketId: string) =>
      runDiagnosticProfile(ticketId, {
        profile_id: diagnosticsOverviewQuery.data?.profile?.id ?? "generic",
        params: {},
        auto_select_evidence: true,
      }),
    onSuccess: (_result, ticketId) => {
      void invalidateDiagnostics(ticketId);
    },
  });

  const diagnosticFindingsMutation = useMutation({
    mutationFn: (ticketId: string) => evaluateDiagnosticFindings(ticketId),
    onSuccess: (_result, ticketId) => {
      void invalidateDiagnostics(ticketId);
    },
  });

  const diagnosticBundleMutation = useMutation({
    mutationFn: (ticketId: string) => buildDiagnosticBundle(ticketId, { include_agent_actions: true }),
    onSuccess: (_result, ticketId) => {
      void invalidateDiagnostics(ticketId);
    },
  });

  const diagnosticPassportAttachMutation = useMutation({
    mutationFn: (ticketId: string) => attachSelectedDiagnosticEvidenceToPassport(ticketId),
    onSuccess: (_result, ticketId) => {
      void invalidateDiagnostics(ticketId);
    },
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
      ? endpointTimeline ?? aggregateTimeline
      : endpointTimeline ?? aggregateTimeline.filter((item) => item.kind === timelineFilter);
  const workspaceErrorState = workspaceQuery.isError ? classifyWorkspaceError(workspaceQuery.error) : null;
  const timelineEmptyState = visibleTimeline.length === 0 ? getTimelineEmptyState(timelineFilter) : null;
  const firstRunnableTool = viewModel.right.tools.find((item) => item.enabled);
  const firstRunnablePlaybook = viewModel.right.playbooks.find((item) => item.enabled);
  const allAutomationItems = useMemo(
    () => [...viewModel.right.playbooks, ...viewModel.right.tools],
    [viewModel.right.playbooks, viewModel.right.tools],
  );
  const automationSearchValue = deferredAutomationCatalogSearch.trim().toLowerCase();
  const automationCatalogCounts = useMemo(
    () => ({
      all: allAutomationItems.length,
      runnable: allAutomationItems.filter((item) => item.enabled).length,
      playbook: viewModel.right.playbooks.length,
      tool: viewModel.right.tools.length,
      disabled: allAutomationItems.filter((item) => !item.enabled).length,
    }),
    [allAutomationItems, viewModel.right.playbooks.length, viewModel.right.tools.length],
  );
  const visibleAutomationItems = useMemo(
    () =>
      allAutomationItems.filter((item) => {
        const filterMatches =
          automationCatalogFilter === "all" ||
          (automationCatalogFilter === "runnable" && item.enabled) ||
          (automationCatalogFilter === "disabled" && !item.enabled) ||
          item.kind === automationCatalogFilter;
        return filterMatches && matchesAutomationSearch(item, automationSearchValue);
      }),
    [allAutomationItems, automationCatalogFilter, automationSearchValue],
  );
  const activeOperations = viewModel.right.operations.filter((operation) => operation.active);
  const statusActionOptions = workspaceQuery.data?.detail.actions.status_options ?? [];
  const queueActionOptions = (queueQuery.data?.summary.queue_counts ?? []).filter((queue) => queue.id !== null);
  const firstQueueActionId = queueActionOptions[0]?.id ?? null;
  const firstStatusActionValue = statusActionOptions[0]?.value ?? null;
  const selectedTicketQuality = workspaceQuery.data?.detail.quality ?? null;
  const selectedTicketProblemsQuery = useQuery({
    enabled: Boolean(selectedTicketId && sidebarTab === "quality"),
    queryKey: ["ticket", selectedTicketId, "problems"],
    queryFn: () => fetchTicketProblemLinks(selectedTicketId ?? ""),
  });

  const refreshSelectedTicketData = async () => {
    if (!selectedTicketId) {
      return;
    }
    await Promise.all([
      queryClient.refetchQueries({ queryKey: ["tickets-workspace", selectedTicketId], type: "active" }),
      queryClient.refetchQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId], type: "active" }),
      queryClient.refetchQueries({ queryKey: ["tickets-workspace-queue"], type: "active" }),
    ]);
  };

  useEffect(() => {
    if (!selectedTicketId) {
      return undefined;
    }

    const realtimeClient = getSharedWebRealtimeClient();
    return realtimeClient.subscribeTicket(selectedTicketId, (message) => {
      const currentSelectedTicketId = selectedTicketIdRef.current;
      if (!currentSelectedTicketId || message.ticketId !== currentSelectedTicketId) {
        return;
      }

      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", currentSelectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", currentSelectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
        queryClient.invalidateQueries({
          queryKey: ["tickets-workspace-passport-evidence-candidates", currentSelectedTicketId],
        }),
      ]);
    });
  }, [queryClient, selectedTicketId]);

  function selectRightTab(tab: SidebarTab) {
    setSidebarTab(tab);
    if (tab === "tools" || tab === "sla" || tab === "passport") {
      setWorkspaceMode(tab);
      return;
    }
    if (workspaceMode !== "ticket") {
      setWorkspaceMode("ticket");
    }
  }

  const openAutomationLauncher = (draft: AutomationLaunchDraft = null) => {
    selectRightTab("tools");
    setAutomationLaunchDraft(draft ?? (firstRunnablePlaybook ? { kind: "playbook", id: firstRunnablePlaybook.id } : firstRunnableTool ? { kind: "tool", id: firstRunnableTool.id } : null));
  };

  const selectedLaunchTool =
    automationLaunchDraft?.kind === "tool"
      ? workspaceQuery.data?.tools.tools.find((item) => item.tool_name === automationLaunchDraft.id) ?? null
      : null;
  const selectedLaunchPlaybook =
    automationLaunchDraft?.kind === "playbook"
      ? workspaceQuery.data?.playbooks.playbooks.find((item) => String(item.playbook_version_id) === automationLaunchDraft.id) ?? null
      : null;

  const messageMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicketId) {
        return null;
      }
      return postSupportTicketMessage(selectedTicketId, composerText.trim(), composerMode);
    },
    onSuccess: async () => {
      setComposerText("");
      await refreshSelectedTicketData();
    },
  });

  const toolRunMutation = useMutation({
    mutationFn: async (toolName: string) => {
      const tool = workspaceQuery.data?.tools.tools.find((item) => item.tool_name === toolName);
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
      setTimelineFilter("diagnostics");
      setAutomationLaunchDraft(null);
      await refreshSelectedTicketData();
    },
  });

  const playbookRunMutation = useMutation({
    mutationFn: async (playbookVersionId: number) => {
      const playbook = workspaceQuery.data?.playbooks.playbooks.find((item) => item.playbook_version_id === playbookVersionId);
      if (!selectedTicketId || !playbook) {
        return null;
      }
      return postSupportTicketPlaybookRun(selectedTicketId, { playbookVersionId: playbook.playbook_version_id });
    },
    onSuccess: async () => {
      setTimelineFilter("diagnostics");
      setAutomationLaunchDraft(null);
      await refreshSelectedTicketData();
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

  const ticketVisibilityMutation = useMutation({
    mutationFn: async (action: "hide" | "unhide" | "archive" | "unarchive") => {
      if (!selectedTicketId) {
        return null;
      }
      const reason =
        action === "hide"
          ? "support workspace hide"
          : action === "unhide"
            ? "support workspace unhide"
            : action === "archive"
              ? "support workspace archive"
              : "support workspace unarchive";
      if (action === "hide") {
        return postSupportTicketHide(selectedTicketId, { reason });
      }
      if (action === "unhide") {
        return postSupportTicketUnhide(selectedTicketId, { reason });
      }
      if (action === "archive") {
        return postSupportTicketArchive(selectedTicketId, { reason });
      }
      return postSupportTicketUnarchive(selectedTicketId, { reason });
    },
    onSuccess: async () => {
      setMoreOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
      ]);
    },
  });

  const cleanupNoiseMutation = useMutation({
    mutationFn: () => postSupportWorkspaceCleanupNoise(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] });
    },
  });

  const queueMassActionMutation = useMutation({
    mutationFn: (request: SupportQueueMassActionRequest) => postSupportQueueMassAction(request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["support-workspace-summary"] }),
        selectedTicketId ? queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }) : Promise.resolve(),
        selectedTicketId ? queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }) : Promise.resolve(),
      ]);
    },
  });

  const queueSavedViewCreateMutation = useMutation({
    mutationFn: (request: SupportQueueSavedViewUpsertRequest) => createSupportQueueSavedView(request),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue-saved-views"] });
    },
  });

  const queueSavedViewUpdateMutation = useMutation({
    mutationFn: ({ viewId, request }: { viewId: string; request: SupportQueueSavedViewUpsertRequest }) =>
      updateSupportQueueSavedView(viewId, request),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue-saved-views"] });
    },
  });

  const queueSavedViewDeleteMutation = useMutation({
    mutationFn: (viewId: string) => deleteSupportQueueSavedView(viewId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue-saved-views"] });
    },
  });

  const resolutionCloseMutation = useMutation({
    mutationFn: async (draft: ResolutionCloseDraft) => {
      if (!selectedTicketId) {
        return null;
      }
      return postSupportTicketStatus(selectedTicketId, "resolved", {
        reason: draft.reason.trim(),
        resolutionCode: draft.resolutionCode.trim(),
        requesterResolutionSummary: draft.requesterResolutionSummary.trim(),
        resolutionSummary: draft.resolutionSummary.trim(),
      });
    },
    onSuccess: async () => {
      setResolutionCloseDraft(null);
      setClosureFocus(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-passport-evidence-candidates", selectedTicketId] }),
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
    setWorkspaceMode("ticket");
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
  const selectedTicketIsUnassigned = Boolean(selectedTicket?.assigneeLabel.toLowerCase().includes("не назнач"));
  const getCompactTicketSlaLabel = (ticket: (typeof visibleTickets)[number]) => {
    if (selectedTicket?.id === ticket.id && selectedTicket.nextAction.timerType !== "none") {
      return selectedTicket.nextAction.remainingLabel;
    }
    return ticket.nextDueLabel.toLowerCase().includes("нет") ? "SLA не рассчитан" : ticket.nextDueLabel;
  };
  const getCompactTicketSlaClassName = (label: string, ticket: (typeof visibleTickets)[number]) => {
    if (label.toLowerCase().includes("не рассчитан") || label.toLowerCase().includes("нет")) return "text-slate-400";
    if (label.toLowerCase().includes("просроч")) return "text-red-300";
    return ticket.slaRisk ? "text-red-300" : "text-emerald-300";
  };
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
    resolutionCloseMutation.error ||
    operationCancelMutation.error ||
    operationRetryMutation.error ||
    ticketVisibilityMutation.error ||
    cleanupNoiseMutation.error;
  const isAdmin = session?.actor_role === "admin";
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
  const resolutionCloseReady =
    Boolean(resolutionCloseDraft?.resolutionCode.trim()) &&
    (resolutionCloseDraft?.requesterResolutionSummary.trim().length ?? 0) >= 3 &&
    (resolutionCloseDraft?.resolutionSummary.trim().length ?? 0) >= 3 &&
    (resolutionCloseDraft?.reason.trim().length ?? 0) >= 3;
  const resolutionCloseSubmitDisabled = !resolutionCloseReady || resolutionCloseMutation.isPending;

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
    selectRightTab("passport");
    if (blocker.actionKind === "edit_resolution") {
      setResolutionCloseDraft(makeResolutionCloseDraft(selectedTicket));
    }
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
    setResolutionCloseDraft(null);
  }, [selectedTicket?.id]);

  const isLightTheme = workspaceTheme === "light";

  async function handleLogout() {
    await logout();
    startTransition(() => {
      navigate("/app/login", { replace: true });
    });
  }

  function startColumnResize(pane: WorkspaceResizePane, event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    resizeStateRef.current = {
      pane,
      startX: event.clientX,
      startLeft: workspaceColumns.left,
      startRight: workspaceColumns.right,
    };
    setResizingPane(pane);
  }

  function resetWorkspaceColumnsForCurrentMode() {
    setWorkspaceColumnsByMode((current) => ({
      ...current,
      [workspaceMode]: normalizeWorkspaceColumnsForMode(
        workspaceMode,
        DEFAULT_WORKSPACE_COLUMNS_BY_MODE[workspaceMode],
        workspaceViewportWidth,
      ),
    }));
  }

  return (
    <section
      className={`support-workspace flex h-screen min-h-screen flex-col overflow-hidden ${isLightTheme ? "bg-slate-100 text-slate-950" : "bg-[#07111f] text-slate-100"}`}
      data-testid="support-workspace-root"
      data-compact-layout={isCompactWorkspace ? "true" : "false"}
      data-mode={workspaceMode}
      data-theme={workspaceTheme}
    >
      <h1 className="sr-only">Тикеты</h1>
      <SupportWorkspaceTopbar
        theme={workspaceTheme}
        onToggleTheme={toggleWorkspaceTheme}
        onLogout={() => void handleLogout()}
        notificationCount={workspaceQuery.data?.detail.snapshot.notification_unread ?? 0}
        onRefresh={refreshAll}
        refreshing={queueQuery.isFetching || workspaceQuery.isFetching}
        userLogin={session?.user_login ?? "operator"}
        userRole={session?.actor_role === "admin" ? "Администратор" : "Оператор L1"}
      />

      <div
        className="relative grid min-h-0 flex-1 overflow-hidden support-workspace__mode-grid"
        data-overlay-right={rightPanelInDrawer ? "true" : "false"}
        style={getWorkspaceGridStyle(workspaceMode, workspaceColumns, workspaceViewportWidth)}
      >
        {canResizeWorkspace ? <button
          aria-label="Изменить ширину левой колонки"
          className={`support-workspace__column-resizer absolute bottom-0 top-0 z-30 w-3 -translate-x-1/2 cursor-col-resize ${
            resizingPane === "left" ? "support-workspace__column-resizer--active" : ""
          }`}
          onPointerDown={(event) => startColumnResize("left", event)}
          onDoubleClick={resetWorkspaceColumnsForCurrentMode}
          style={{ left: `${workspaceColumns.left}px` }}
          title="Потяните, чтобы изменить ширину списка тикетов"
          type="button"
        >
          <span className="support-workspace__column-resizer-line">
            <GripVertical className="h-4 w-4" />
          </span>
        </button> : null}
        {canResizeWorkspace ? <button
          aria-label="Изменить ширину правой колонки"
          className={`support-workspace__column-resizer absolute bottom-0 top-0 z-30 w-3 translate-x-1/2 cursor-col-resize ${
            resizingPane === "right" ? "support-workspace__column-resizer--active" : ""
          }`}
          onPointerDown={(event) => startColumnResize("right", event)}
          onDoubleClick={resetWorkspaceColumnsForCurrentMode}
          style={{ right: `${workspaceColumns.right}px` }}
          title="Потяните, чтобы изменить ширину контекстной панели"
          type="button"
        >
          <span className="support-workspace__column-resizer-line">
            <GripVertical className="h-4 w-4" />
          </span>
        </button> : null}
        <aside className="flex min-h-0 flex-col border-r border-white/10 bg-[#0b1624]">
          {workspaceMode === "queue" ? (
            <QueueExplorer
              activeQueueId={activeQueueId}
              cleanupNoisePending={cleanupNoiseMutation.isPending}
              defaultColumns={queueSavedViewsQuery.data?.default_columns}
              defaultViewId={queueSavedViewsQuery.data?.default_view_id ?? null}
              massActionPending={queueMassActionMutation.isPending}
              massActionResult={queueMassActionMutation.data ?? null}
              onActiveQueueChange={setActiveQueueId}
              onCleanupNoise={() => cleanupNoiseMutation.mutate()}
              onDeleteSavedView={(viewId) => queueSavedViewDeleteMutation.mutate(viewId)}
              onMassAction={(request) => queueMassActionMutation.mutate(request)}
              onOpenTicket={openTicket}
              onPersistDefaultColumns={(viewId, request) => {
                if (viewId) {
                  queueSavedViewUpdateMutation.mutate({ viewId, request });
                  return;
                }
                queueSavedViewCreateMutation.mutate(request);
              }}
              onSaveSavedView={(request) => queueSavedViewCreateMutation.mutate(request)}
              onScopeChange={setScope}
              onSearchChange={setSearch}
              onShowArchiveChange={setShowArchive}
              onSelectTicket={(ticketId) => {
                setWorkspaceMode("queue");
                startTransition(() => {
                  navigate(`/app/tickets/${ticketId}`);
                });
              }}
              onSmartViewChange={setSmartView}
              queues={viewModel.left.queues}
              scope={scope}
              search={search}
              selectedTicket={selectedTicket}
              selectedViewId={smartView}
              savedViewMutationPending={queueSavedViewCreateMutation.isPending || queueSavedViewUpdateMutation.isPending || queueSavedViewDeleteMutation.isPending}
              savedViews={queueSavedViewsQuery.data?.views ?? []}
              savedViewsError={queueSavedViewsQuery.isError}
              savedViewsLoading={queueSavedViewsQuery.isLoading}
              showArchive={showArchive}
              slices={viewModel.left.slices}
              tickets={visibleTickets}
            />
          ) : (
          <>
          <div className="border-b border-white/10 px-4 py-4">
            <button
              className="mb-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 hover:bg-blue-500"
              onClick={() => setWorkspaceMode("queue")}
              type="button"
            >
              Развернуть очередь
            </button>
            <label className="flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-400">
              <Search className="h-4 w-4 shrink-0" />
              <input
                className="min-w-0 flex-1 bg-transparent text-slate-100 outline-none placeholder:text-slate-500"
                onChange={(event) => setSearch(event.currentTarget.value)}
                placeholder="Поиск по моим тикетам..."
                type="search"
                value={search}
              />
            </label>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${scope === "mine" ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                onClick={() => setScope("mine")}
                type="button"
              >
                Мои тикеты
              </button>
              <button
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${smartView === "sla_risk" ? "border-amber-400/60 bg-amber-500/15 text-amber-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                onClick={() => setSmartView("sla_risk")}
                type="button"
              >
                SLA риск
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
            <div className="mb-2 flex items-center justify-between px-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              <span>Мой рабочий список</span>
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
              {visibleTickets.map((ticket) => {
                const slaLabel = getCompactTicketSlaLabel(ticket);
                return (
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
                    {ticket.archivedAt ? (
                      <span className="rounded-md border border-slate-400/30 bg-slate-500/10 px-2 py-0.5 text-[11px] font-semibold text-slate-200">
                        Архив
                      </span>
                    ) : null}
                    {ticket.hiddenFromWorkspace ? (
                      <span className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-100">
                        Скрыт
                      </span>
                    ) : null}
                    <span className={`ml-auto text-xs font-semibold ${getCompactTicketSlaClassName(slaLabel, ticket)}`}>
                      {slaLabel}
                    </span>
                  </div>
                </button>
                );
              })}
            </div>
          </div>
          </>
          )}
        </aside>

        <main className="flex min-h-0 flex-col border-r border-white/10 bg-[#07111f]">
          {workspaceMode === "queue" ? (
            <TicketPreviewPanel
              canTakeTicket={selectedTicketIsUnassigned}
              onAssignTicket={() => openOperatorAction("assign_self")}
              onOpenTicket={openTicket}
              onTakeTicket={() => openOperatorAction("assign_self")}
              selectedTicket={selectedTicket}
            />
          ) : null}

          {workspaceMode !== "queue" && !selectedTicketId ? (
            <div className="flex flex-1 items-center justify-center px-8 text-center">
              <div>
                <Inbox className="mx-auto h-10 w-10 text-slate-500" />
                <h2 className="mt-4 text-xl font-semibold text-white">Выберите тикет из очереди</h2>
                <p className="mt-2 max-w-md text-sm text-slate-400">Центральная рабочая область появится после выбора обращения.</p>
              </div>
            </div>
          ) : null}

          {workspaceMode !== "queue" && selectedTicketId && workspaceQuery.isLoading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">Загружаем тикет...</div>
          ) : null}

          {workspaceMode !== "queue" && selectedTicketId && workspaceErrorState ? (
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

          {workspaceMode !== "queue" && selectedTicket ? (
            <>
              <div className="border-b border-white/10 bg-[#0b1624]/70 px-5 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="mb-2 flex items-center gap-3 text-sm text-slate-400">
                      <Link className="hover:text-white" to="/app/tickets">Очередь</Link>
                      <span>/</span>
                      <span>{selectedTicket.code}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <h2 className="truncate text-xl font-semibold tracking-tight text-white min-[1600px]:text-2xl">
                        {selectedTicket.code} {selectedTicket.subject}
                      </h2>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                      <span className={`rounded-md border px-2 py-1 font-bold ${toneClasses(selectedTicket.priorityTone)}`}>{selectedTicket.priority}</span>
                      <span>Очередь: {selectedTicket.queueLabel}</span>
                      <span>Исполнитель: {selectedTicket.assigneeLabel}</span>
                      <span className={`rounded-md border px-2 py-1 font-semibold ${toneClasses(selectedTicket.statusTone)}`}>{selectedTicket.statusLabel}</span>
                      {selectedTicket.archivedAt ? (
                        <span className="rounded-md border border-slate-400/30 bg-slate-500/10 px-2 py-1 font-semibold text-slate-200">Архив</span>
                      ) : null}
                      {selectedTicket.hiddenFromWorkspace ? (
                        <span className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2 py-1 font-semibold text-amber-100">Скрыт из списков</span>
                      ) : null}
                      <span>SLA: {selectedTicket.nextAction.remainingLabel}</span>
                    </div>
                  </div>
                </div>

                <section className={`mt-3 grid grid-cols-[auto_minmax(0,1fr)_minmax(180px,240px)] items-center gap-4 rounded-xl border p-3 ${toneClasses(selectedTicket.nextAction.tone)}`}>
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
                    <Play className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">Следующее действие</p>
                    <p className="mt-1 text-base font-semibold text-white">{selectedTicket.nextAction.label}</p>
                    <p className="mt-1 truncate text-sm text-slate-300">{selectedTicket.nextAction.hint}</p>
                  </div>
                  <div className="border-l border-white/10 pl-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Осталось времени</p>
                    <p className="mt-1 text-xl font-semibold text-white">{selectedTicket.nextAction.remainingLabel}</p>
                    <p className="mt-1 text-xs text-slate-400">до контрольного срока</p>
                  </div>
                </section>

                <div className="mt-3 flex items-center justify-end">
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <button
                        aria-expanded={moreOpen}
                        className="h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 hover:text-white disabled:opacity-50"
                        disabled={operatorActionMutation.isPending || ticketVisibilityMutation.isPending}
                        onClick={() => setMoreOpen((open) => !open)}
                        type="button"
                      >
                        Ещё
                      </button>
                      {moreOpen ? (
                        <div className="absolute right-0 z-20 mt-2 max-h-[min(70vh,520px)] w-[340px] overflow-y-auto rounded-xl border border-white/10 bg-[#101d30] p-1 shadow-2xl shadow-black/40">
                          <button
                            className={`block w-full rounded-lg px-3 py-2 text-left text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${
                              selectedTicketIsUnassigned ? "bg-blue-600 text-white hover:bg-blue-500" : "text-slate-500"
                            }`}
                            disabled={!session?.user_login || !selectedTicketIsUnassigned}
                            onClick={() => openOperatorAction("assign_self")}
                            type="button"
                          >
                            Взять себе
                          </button>
                          <div className="my-1 border-t border-white/10" />
                          {selectedTicket.hiddenFromWorkspace ? (
                            <button
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={!selectedTicket.canUnhideFromWorkspace || ticketVisibilityMutation.isPending}
                              onClick={() => ticketVisibilityMutation.mutate("unhide")}
                              type="button"
                            >
                              <Eye className="h-4 w-4" />
                              Вернуть в списки
                            </button>
                          ) : (
                            <button
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={!selectedTicket.canHideFromWorkspace || ticketVisibilityMutation.isPending}
                              onClick={() => ticketVisibilityMutation.mutate("hide")}
                              type="button"
                            >
                              <EyeOff className="h-4 w-4" />
                              Скрыть у всех
                            </button>
                          )}
                          {isAdmin && selectedTicket.archivedAt ? (
                            <button
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={!selectedTicket.canUnarchiveTicket || ticketVisibilityMutation.isPending}
                              onClick={() => ticketVisibilityMutation.mutate("unarchive")}
                              type="button"
                            >
                              <ArchiveRestore className="h-4 w-4" />
                              Вернуть из архива
                            </button>
                          ) : null}
                          {isAdmin && !selectedTicket.archivedAt ? (
                            <button
                              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={!selectedTicket.canArchiveTicket || ticketVisibilityMutation.isPending}
                              onClick={() => ticketVisibilityMutation.mutate("archive")}
                              type="button"
                            >
                              <Archive className="h-4 w-4" />
                              Архивировать
                            </button>
                          ) : null}
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
                {resolutionCloseDraft ? (
                  <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm" role="presentation">
                    <section
                      aria-labelledby="resolution-close-title"
                      aria-modal="true"
                      className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#101d30] p-5 text-slate-100 shadow-2xl shadow-black/50"
                      role="dialog"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h2 className="text-lg font-semibold" id="resolution-close-title">Перевести тикет в решение</h2>
                          <p className="mt-1 text-sm leading-6 text-slate-400">
                            Публичный итог увидит заявитель. Внутренний итог останется в истории поддержки.
                          </p>
                        </div>
                        <button
                          aria-label="Закрыть форму решения"
                          className="rounded-lg border border-white/10 px-2 py-1 text-sm text-slate-300 hover:text-white"
                          onClick={() => setResolutionCloseDraft(null)}
                          type="button"
                        >
                          ×
                        </button>
                      </div>

                      <div className="mt-4 rounded-xl border border-blue-400/20 bg-blue-500/10 px-3 py-2 text-sm leading-6 text-blue-100">
                        Переход в статус «Решено» всё равно пройдёт через workflow, approval и closure policy. Если не хватает evidence,
                        worklog или согласования, сервер вернёт точное требование.
                      </div>

                      <div className="mt-5 space-y-4">
                        <label className="block text-sm font-medium text-slate-300">
                          Код решения
                          <input
                            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const resolutionCode = event.currentTarget.value;
                              setResolutionCloseDraft((draft) => draft ? { ...draft, resolutionCode } : draft);
                            }}
                            placeholder="Например: fixed_remote"
                            value={resolutionCloseDraft.resolutionCode}
                          />
                        </label>

                        <label className="block text-sm font-medium text-slate-300">
                          Итог для заявителя
                          <textarea
                            className="mt-2 min-h-24 w-full resize-none rounded-xl border border-white/10 bg-[#0d1828] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const requesterResolutionSummary = event.currentTarget.value;
                              setResolutionCloseDraft((draft) => draft ? { ...draft, requesterResolutionSummary } : draft);
                            }}
                            placeholder="Коротко и понятно: что исправлено, как проверить результат."
                            value={resolutionCloseDraft.requesterResolutionSummary}
                          />
                        </label>

                        <label className="block text-sm font-medium text-slate-300">
                          Внутренний итог
                          <textarea
                            className="mt-2 min-h-24 w-full resize-none rounded-xl border border-white/10 bg-[#0d1828] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const resolutionSummary = event.currentTarget.value;
                              setResolutionCloseDraft((draft) => draft ? { ...draft, resolutionSummary } : draft);
                            }}
                            placeholder="Причина, действия оператора, технические детали и риски повторения."
                            value={resolutionCloseDraft.resolutionSummary}
                          />
                        </label>

                        <label className="block text-sm font-medium text-slate-300">
                          Причина перевода
                          <input
                            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                            onChange={(event) => {
                              const reason = event.currentTarget.value;
                              setResolutionCloseDraft((draft) => draft ? { ...draft, reason } : draft);
                            }}
                            placeholder="Например: решение проверено оператором"
                            value={resolutionCloseDraft.reason}
                          />
                        </label>

                        {!resolutionCloseReady ? (
                          <p className="text-xs text-amber-200">
                            Заполните код решения, оба итога и причину перевода. Это защитит от случайного закрытия без паспорта.
                          </p>
                        ) : null}
                      </div>

                      <div className="mt-5 flex justify-end gap-2">
                        <button
                          className="h-10 rounded-xl border border-white/10 px-4 text-sm font-semibold text-slate-300 hover:text-white"
                          onClick={() => setResolutionCloseDraft(null)}
                          type="button"
                        >
                          Отмена
                        </button>
                        <button
                          className="h-10 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={resolutionCloseSubmitDisabled}
                          onClick={() => resolutionCloseMutation.mutate(resolutionCloseDraft)}
                          type="button"
                        >
                          {resolutionCloseMutation.isPending ? "Переводим..." : "Перевести в решение"}
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
                        onClick={() => selectRightTab("passport")}
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
                      className={`border-b-2 px-1 py-3 text-sm font-semibold transition ${
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

                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
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

                <div className="border-t border-white/10 bg-[#0b1624] p-3">
                  <div className="rounded-xl border border-white/10 bg-[#0d1828]">
                    <div className="flex items-center gap-4 border-b border-white/10 px-4">
                      {(["public", "internal"] as const).map((mode) => (
                        <button
                          className={`border-b-2 py-2.5 text-sm font-semibold ${
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
                      className="h-20 min-h-16 max-h-44 w-full resize-y bg-transparent px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
                      data-testid="support-reply-composer"
                      onChange={(event) => setComposerText(event.currentTarget.value)}
                      placeholder={composerMode === "public" ? "Напишите сообщение пользователю..." : "Напишите внутреннюю заметку для команды..."}
                      value={composerText}
                      ref={composerTextareaRef}
                    />
                    <div className="flex items-center gap-2 px-4 pb-3">
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

        <aside
          className={`flex min-h-0 flex-col bg-[#0b1624] ${
            rightPanelInDrawer ? "support-workspace__right-panel--drawer" : ""
          }`}
        >
          {workspaceMode === "queue" ? (
            <div className="flex min-h-0 flex-1">
              <button
                className={`flex h-full w-full items-center justify-center px-1 text-xs font-semibold leading-5 transition [writing-mode:vertical-rl] ${
                  selectedTicket
                    ? "bg-blue-500/10 text-blue-100 hover:bg-blue-500/20"
                    : "cursor-not-allowed bg-white/[0.02] text-slate-600"
                }`}
                disabled={!selectedTicket}
                onClick={() => {
                  setSidebarTab("context");
                  setWorkspaceMode("ticket");
                }}
                type="button"
              >
                Развернуть контекст
              </button>
            </div>
          ) : (
            <>
          {workspaceMode === "tools" ? (
            <ExpandedWorkspaceHeader onReturnToTicket={() => setWorkspaceMode("ticket")} title="Инструменты" />
          ) : workspaceMode === "sla" ? (
            <ExpandedWorkspaceHeader onReturnToTicket={() => setWorkspaceMode("ticket")} title="SLA режим" />
          ) : workspaceMode === "passport" ? (
            <ExpandedWorkspaceHeader onReturnToTicket={() => setWorkspaceMode("ticket")} title="Паспорт решения" />
          ) : null}
          <div className="border-b border-white/10 p-3">
            <div className="grid grid-cols-6 gap-1 rounded-xl bg-white/[0.04] p-1">
              {sidebarTabs.map((tab) => (
                <button
                  className={`rounded-lg px-2 py-2 text-xs font-semibold transition ${
                    sidebarTab === tab.value ? "bg-[#13233a] text-white shadow" : "text-slate-400 hover:text-white"
                  }`}
                  key={tab.value}
                  onClick={() => selectRightTab(tab.value)}
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
                <ObserverDiagnosticCard isLightTheme={isLightTheme} observer={viewModel.right.observer} />

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

            {selectedTicket && sidebarTab === "quality" ? (
              <div className="space-y-3" data-testid="support-quality-panel">
                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Quality</p>
                      <h3 className="mt-1 font-semibold text-white">Experience signals</h3>
                    </div>
                    <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs font-semibold text-slate-300">
                      {(selectedTicketQuality?.indicators.length ?? 0) || "No flags"}
                    </span>
                  </div>
                  <dl className="mt-4 grid gap-2 text-sm">
                    <ContextInfoRow
                      icon={BarChart3}
                      label="Latest CSAT"
                      value={
                        selectedTicketQuality?.latest_feedback
                          ? `${selectedTicketQuality.latest_feedback.rating}/5 (${selectedTicketQuality.latest_feedback.sentiment ?? "unknown"})`
                          : "n/a"
                      }
                    />
                    <ContextInfoRow
                      icon={CheckCircle2}
                      label="Problem resolved"
                      value={
                        selectedTicketQuality?.latest_feedback?.problem_resolved === false
                          ? "No"
                          : selectedTicketQuality?.latest_feedback
                            ? "Yes"
                            : "n/a"
                      }
                    />
                    <ContextInfoRow icon={RefreshCcw} label="Reopen history" value={selectedTicketQuality?.reopen_events.length ?? 0} />
                    <ContextInfoRow icon={ShieldCheck} label="QA reviews" value={selectedTicketQuality?.reviews.length ?? 0} />
                    <ContextInfoRow icon={Sparkles} label="Improvement actions" value={selectedTicketQuality?.improvement_actions.length ?? 0} />
                  </dl>
                  {selectedTicketQuality?.latest_feedback?.comment ? (
                    <p className="mt-4 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm leading-6 text-slate-200">
                      {selectedTicketQuality.latest_feedback.comment}
                    </p>
                  ) : null}
                </section>

                {selectedTicketQuality?.indicators.length ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Indicators</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedTicketQuality.indicators.map((indicator) => (
                        <span className="rounded-md border border-amber-300/20 bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-100" key={indicator}>
                          {indicator}
                        </span>
                      ))}
                    </div>
                  </section>
                ) : null}

                {(selectedTicketQuality?.reviews.length ?? 0) > 0 ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">QA review queue</p>
                    <div className="mt-3 space-y-2">
                      {selectedTicketQuality?.reviews.slice(0, 4).map((review) => (
                        <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2" key={review.review_id}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <strong className="text-white">{review.review_type}</strong>
                            <span className="text-slate-300">{review.status}</span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {review.severity} / score {review.score ?? "n/a"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}

                {(selectedTicketQuality?.improvement_actions.length ?? 0) > 0 ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Improvement actions</p>
                    <div className="mt-3 space-y-2">
                      {selectedTicketQuality?.improvement_actions.slice(0, 4).map((action) => (
                        <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2" key={action.action_id}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <strong className="text-white">{action.title}</strong>
                            <span className="text-slate-300">{action.status}</span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {action.priority} / {action.action_type} / owner {action.owner_actor_id ?? "unassigned"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}

                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Linked problems</p>
                  <div className="mt-3 space-y-2">
                    {(selectedTicketProblemsQuery.data ?? []).length > 0 ? (
                      selectedTicketProblemsQuery.data?.slice(0, 4).map((item) => (
                        <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2" key={item.link.link_id}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <strong className="text-white">{item.problem.problem_key}</strong>
                            <span className="text-slate-300">{item.problem.status}</span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {item.problem.title} / {item.link.link_type}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">
                        {selectedTicketProblemsQuery.isLoading ? "Loading problem links..." : "No linked problems."}
                      </p>
                    )}
                  </div>
                </section>
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "sla" ? (
              <div className="space-y-3">
                {workspaceMode === "sla" ? (
                  <div aria-label="SLA workspace" className="flex flex-wrap gap-2 rounded-xl border border-white/10 bg-[#111f33] p-3" role="tablist">
                    {slaWorkspaceTabs.map((tab) => (
                      <button
                        aria-selected={slaWorkspaceTab === tab.value}
                        className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                          slaWorkspaceTab === tab.value
                            ? "border-blue-400/60 bg-blue-500/15 text-blue-100"
                            : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
                        }`}
                        key={tab.value}
                        onClick={() => setSlaWorkspaceTab(tab.value)}
                        role="tab"
                        type="button"
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                {workspaceMode === "sla" && slaWorkspaceTab === "overview" ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <div className="grid gap-3 md:grid-cols-2">
                      {selectedTicket.timers.map((timer) => (
                        <div className={`rounded-xl border border-white/10 bg-white/[0.03] p-4 ${timerStatusRing(timer.status)}`} key={`expanded:${timer.key}`}>
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-semibold text-white">{timer.label}</p>
                              <p className="mt-1 text-xs text-slate-500">{formatDueLabel(timer.dueAt)}</p>
                            </div>
                            <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(timerStatusToTone(timer.status))}`}>
                              {timerStatusLabel(timer.status)}
                            </span>
                          </div>
                          <p className="mt-4 text-2xl font-semibold text-white">{timer.remainingLabel}</p>
                          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                            <div className={`h-full rounded-full ${progressTone(timer.status)}`} style={{ width: `${Math.max(4, timer.progress)}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">OLA</p>
                        <p className="mt-2 text-sm text-slate-300">Ack и Processing берутся из текущего SLA/OLA payload.</p>
                      </div>
                      <div className="rounded-xl border border-amber-300/20 bg-amber-500/10 p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-100/80">Эскалации</p>
                        <p className="mt-2 text-sm text-amber-50">
                          {selectedTicket.timers.some((timer) => timer.status === "breached" || timer.status === "at_risk")
                            ? "Есть риск или нарушение срока."
                            : "Активных эскалаций нет."}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">История сроков</p>
                        <p className="mt-2 text-sm text-slate-300">События SLA/OLA доступны во вкладке истории timeline.</p>
                      </div>
                    </div>
                  </section>
                ) : null}
                {workspaceMode === "sla" && slaWorkspaceTab === "ola" ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="font-semibold text-white">OLA по очереди</p>
                    <p className="mt-1 text-sm text-slate-400">Внутренние сроки берутся из текущего SLA/OLA payload без нового API.</p>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {selectedTicket.timers.length ? selectedTicket.timers.map((timer) => (
                        <div className={`rounded-xl border border-white/10 bg-white/[0.03] p-3 ${timerStatusRing(timer.status)}`} key={`ola:${timer.key}`}>
                          <div className="flex items-start justify-between gap-3">
                            <p className="font-semibold text-white">{timer.label}</p>
                            <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(timerStatusToTone(timer.status))}`}>
                              {timerStatusLabel(timer.status)}
                            </span>
                          </div>
                          <p className="mt-3 text-lg font-semibold text-white">{timer.remainingLabel}</p>
                          <p className="mt-1 text-xs text-slate-500">{formatDueLabel(timer.dueAt)}</p>
                        </div>
                      )) : (
                        <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400 md:col-span-2">
                          OLA данные для тикета пока не заданы.
                        </p>
                      )}
                    </div>
                  </section>
                ) : null}
                {workspaceMode === "sla" && slaWorkspaceTab === "escalations" ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="font-semibold text-white">Эскалационный контроль</p>
                    <p className="mt-1 text-sm text-slate-400">
                      {selectedTicket.timers.some((timer) => timer.status === "breached" || timer.status === "at_risk")
                        ? "Есть риск или нарушение срока. Действия показаны безопасно и не обходят backend policy."
                        : "Активных SLA/OLA эскалаций по текущим данным нет."}
                    </p>
                    <div className="mt-4 grid gap-2 md:grid-cols-3">
                      <button className="rounded-xl border border-red-300/30 bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-100 disabled:opacity-60" disabled type="button">
                        Эскалировать
                      </button>
                      <button className="rounded-xl border border-amber-300/30 bg-amber-500/10 px-3 py-2 text-sm font-semibold text-amber-100 disabled:opacity-60" disabled type="button">
                        Сообщить руководителю
                      </button>
                      <button className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-200 disabled:opacity-60" disabled type="button">
                        Добавить причину задержки
                      </button>
                    </div>
                  </section>
                ) : null}
                {workspaceMode === "sla" && slaWorkspaceTab === "history" ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <p className="font-semibold text-white">История сроков</p>
                    <div className="mt-3 space-y-2">
                      {selectedTicket.timeline.filter((item) => item.kind === "history" || item.kind === "diagnostics").slice(0, 8).map((item) => (
                        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2" key={`sla-history:${item.id}`}>
                          <div className="flex justify-between gap-3 text-xs text-slate-500">
                            <span>{item.actor}</span>
                            <span>{item.timestampLabel}</span>
                          </div>
                          <p className="mt-1 text-sm font-semibold text-white">{item.title}</p>
                          {item.body ? <p className="mt-1 text-xs leading-5 text-slate-400">{item.body}</p> : null}
                        </div>
                      ))}
                      {!selectedTicket.timeline.some((item) => item.kind === "history" || item.kind === "diagnostics") ? (
                        <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
                          Событий сроков пока нет.
                        </p>
                      ) : null}
                    </div>
                  </section>
                ) : null}
                {workspaceMode !== "sla" ? (
                  selectedTicket.timers.length ? selectedTicket.timers.map((timer) => (
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
                  )
                ) : null}
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "tools" ? (
              <div className="space-y-3">
                {workspaceMode !== "tools" ? (
                  <RemoteAssistPanel
                    deviceId={viewModel.right.context?.device.id ?? null}
                    deviceOnline={viewModel.right.context?.device.online ?? false}
                    onChanged={() => {
                      void queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicket.id] });
                      void queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicket.id] });
                    }}
                    permissions={session?.permissions ?? []}
                    ticketId={selectedTicket.id}
                  />
                ) : null}
                {workspaceMode === "tools" ? (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                    <div aria-label="Режим инструментов" className="mb-4 flex flex-wrap gap-2" role="tablist">
                      {toolsWorkspaceTabs.map((tab) => (
                        <button
                          aria-selected={toolsWorkspaceTab === tab.value}
                          className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                            toolsWorkspaceTab === tab.value
                              ? "border-blue-400/60 bg-blue-500/15 text-blue-100"
                              : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
                          }`}
                          key={tab.value}
                          onClick={() => setToolsWorkspaceTab(tab.value)}
                          role="tab"
                          type="button"
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>
                    {toolsWorkspaceTab === "diagnostics" ? (
                      <DiagnosticCenterPanel ticketId={selectedTicket.id} />
                    ) : null}
                    {toolsWorkspaceTab === "quick" ? (
                      <div className="grid gap-2 md:grid-cols-2">
                        {viewModel.right.tools.slice(0, 8).map((tool) => (
                          <button
                            className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-left transition hover:border-blue-400/30 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!tool.enabled}
                            key={tool.id}
                            onClick={() => setAutomationLaunchDraft({ kind: "tool", id: tool.id })}
                            title={tool.disabledReason ?? tool.subtitle}
                            type="button"
                          >
                            <p className="text-sm font-semibold text-white">{tool.title}</p>
                            <p className="mt-1 line-clamp-2 text-xs text-slate-400">{tool.subtitle}</p>
                            {tool.disabledReason ? <p className="mt-2 text-xs text-amber-200">Причина: {tool.disabledReason}</p> : null}
                          </button>
                        ))}
                        {!viewModel.right.tools.length ? (
                          <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400 md:col-span-2">
                            Доступных быстрых инструментов пока нет.
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    {toolsWorkspaceTab === "playbook" ? (
                      <div className="grid gap-2">
                        {viewModel.right.playbooks.map((playbook) => (
                          <button
                            className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-left transition hover:border-blue-400/30 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!playbook.enabled}
                            key={playbook.id}
                            onClick={() => setAutomationLaunchDraft({ kind: "playbook", id: playbook.id })}
                            title={playbook.disabledReason ?? playbook.subtitle}
                            type="button"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-semibold text-white">{playbook.title}</p>
                              <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${playbook.enabled ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100" : "border-amber-400/30 bg-amber-500/10 text-amber-100"}`}>
                                {playbook.enabled ? "Готов" : "Недоступен"}
                              </span>
                            </div>
                            <p className="mt-1 line-clamp-2 text-xs text-slate-400">{playbook.subtitle}</p>
                            {playbook.disabledReason ? <p className="mt-2 text-xs text-amber-200">Причина: {playbook.disabledReason}</p> : null}
                          </button>
                        ))}
                        {!viewModel.right.playbooks.length ? (
                          <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
                            Playbook для этого тикета пока нет.
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    {toolsWorkspaceTab === "remote" ? (
                      <RemoteAssistPanel
                        deviceId={viewModel.right.context?.device.id ?? null}
                        deviceOnline={viewModel.right.context?.device.online ?? false}
                        onChanged={() => {
                          void queryClient.invalidateQueries({ queryKey: ["tickets-workspace", selectedTicket.id] });
                          void queryClient.invalidateQueries({ queryKey: ["tickets-workspace-timeline", selectedTicket.id] });
                        }}
                        permissions={session?.permissions ?? []}
                        ticketId={selectedTicket.id}
                      />
                    ) : null}
                    {toolsWorkspaceTab === "operations" ? (
                      <OperationsTable
                        onCancel={(operationId) => operationCancelMutation.mutate(operationId)}
                        onRetry={(operationId) => operationRetryMutation.mutate(operationId)}
                        operations={viewModel.right.operations}
                      />
                    ) : null}
                    {toolsWorkspaceTab === "history" ? (
                      <div className="space-y-2">
                        {selectedTicket.timeline
                          .filter((item) => item.kind === "diagnostics" || item.kind === "history")
                          .slice(0, 8)
                          .map((item) => (
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2" key={item.id}>
                              <div className="flex justify-between gap-3 text-xs text-slate-500">
                                <span>{item.actor}</span>
                                <span>{item.timestampLabel}</span>
                              </div>
                              <p className="mt-1 text-sm font-semibold text-white">{item.title}</p>
                              {item.body ? <p className="mt-1 text-xs leading-5 text-slate-400">{item.body}</p> : null}
                            </div>
                          ))}
                        {!selectedTicket.timeline.some((item) => item.kind === "diagnostics" || item.kind === "history") ? (
                          <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
                            Технических событий для истории пока нет.
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                  </section>
                ) : null}
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
                    <div className="min-w-0">
                      <p className="font-semibold text-white">Инструменты / Playbook</p>
                      <p className="mt-1 text-xs text-slate-400">
                        Показано {visibleAutomationItems.length} из {automationCatalogCounts.all} · Playbooks {automationCatalogCounts.playbook} · Инструменты {automationCatalogCounts.tool}
                      </p>
                    </div>
                    <button
                      className="shrink-0 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                      disabled={toolRunMutation.isPending || playbookRunMutation.isPending || (!firstRunnableTool && !firstRunnablePlaybook)}
                      onClick={() => openAutomationLauncher()}
                      type="button"
                    >
                      Запустить
                    </button>
                  </div>
                  <div className="mt-4 space-y-3">
                    <label className="relative block">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                      <input
                        className="h-10 w-full rounded-xl border border-white/10 bg-[#0d1828] pl-9 pr-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-blue-400/60 focus:ring-2 focus:ring-blue-500/20"
                        onChange={(event) => setAutomationCatalogSearch(event.currentTarget.value)}
                        placeholder="Поиск по модулю, команде, playbook..."
                        type="search"
                        value={automationCatalogSearch}
                      />
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {automationCatalogFilters.map((filter) => {
                        const count = automationCatalogCounts[filter.value];
                        return (
                          <button
                            className={`rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition ${
                              automationCatalogFilter === filter.value
                                ? "border-blue-400/60 bg-blue-500/15 text-blue-100"
                                : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-white"
                            }`}
                            key={filter.value}
                            onClick={() => setAutomationCatalogFilter(filter.value)}
                            type="button"
                          >
                            {filter.label}
                            <span className="ml-1 text-[11px] opacity-75">{count}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  {automationLaunchDraft ? (
                    <div className="mt-4 rounded-xl border border-blue-400/30 bg-blue-500/10 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-200">Запуск диагностики</p>
                          <p className="mt-1 truncate text-sm font-semibold text-white">
                            {selectedLaunchPlaybook?.name ?? selectedLaunchTool?.tool_name ?? "Выберите инструмент"}
                          </p>
                          <p className="mt-1 text-xs text-slate-300">
                            {selectedLaunchPlaybook
                              ? selectedLaunchPlaybook.readiness_label
                              : selectedLaunchTool
                                ? selectedLaunchTool.presets[0]?.label ?? selectedLaunchTool.description ?? "Без пресета"
                                : "Выберите конкретный playbook или модуль ниже."}
                          </p>
                        </div>
                        <button
                          className="rounded-lg border border-white/10 px-2 py-1 text-xs font-semibold text-slate-300 hover:text-white"
                          onClick={() => setAutomationLaunchDraft(null)}
                          type="button"
                        >
                          Закрыть
                        </button>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedLaunchPlaybook ? (
                          <button
                            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!selectedLaunchPlaybook.can_run || playbookRunMutation.isPending}
                            onClick={() => playbookRunMutation.mutate(selectedLaunchPlaybook.playbook_version_id)}
                            type="button"
                          >
                            Запустить playbook
                          </button>
                        ) : null}
                        {selectedLaunchTool ? (
                          <button
                            className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={toolRunMutation.isPending}
                            onClick={() => toolRunMutation.mutate(selectedLaunchTool.tool_name)}
                            type="button"
                          >
                            Запустить инструмент
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
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
                          <div className="mt-3 flex justify-end">
                            <button
                              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={!item.enabled || toolRunMutation.isPending || playbookRunMutation.isPending}
                              onClick={() => setAutomationLaunchDraft({ kind: item.kind, id: item.id })}
                              type="button"
                            >
                              Выбрать
                            </button>
                          </div>
                        </div>
                      );
                    })}
                    {!allAutomationItems.length ? (
                      <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-6 text-sm text-slate-400">
                        Доступные инструменты не найдены или устройство offline.
                      </p>
                    ) : null}
                    {allAutomationItems.length && !visibleAutomationItems.length ? (
                      <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-6 text-sm text-slate-400">
                        По текущему поиску и фильтру ничего не найдено. Измените запрос или покажите все элементы каталога.
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
              <section className={`rounded-xl p-4 ${isLightTheme ? "border border-slate-200 bg-white text-slate-950 shadow-sm" : "border border-white/10 bg-[#111f33]"}`}>
                {workspaceMode === "passport" ? (
                  <div aria-label="Паспорт решения workspace" className="mb-4 flex flex-wrap gap-2" role="tablist">
                    {passportWorkspaceTabs.map((tab) => (
                      <button
                        aria-selected={passportWorkspaceTab === tab.value}
                        className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                          passportWorkspaceTab === tab.value
                            ? "border-blue-400/60 bg-blue-500/15 text-blue-100"
                            : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
                        }`}
                        key={tab.value}
                        onClick={() => setPassportWorkspaceTab(tab.value)}
                        role="tab"
                        type="button"
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                {workspaceMode === "passport" && passportWorkspaceTab === "sections" ? (
                  <div className="mb-4 grid gap-3 md:grid-cols-3">
                    {["Проблема", "Причина", "Решение", "Проверка результата", "Подтверждение пользователя", "Доказательства", "Удалённая помощь", "Операции и диагностика", "Готовность к закрытию"].map((label, index) => {
                      const item = viewModel.right.passport.items[index % Math.max(1, viewModel.right.passport.items.length)];
                      const done = Boolean(item?.done);
                      return (
                        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3" key={label}>
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-white">{label}</p>
                            {done ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <Clock3 className="h-4 w-4 text-amber-200" />}
                          </div>
                          <p className="mt-2 text-xs leading-5 text-slate-400">{done ? "Заполнено по текущему паспорту." : "Требует внимания перед закрытием."}</p>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
                {workspaceMode === "passport" && passportWorkspaceTab === "evidence" ? (
                  <div className="mb-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <p className="font-semibold text-white">Доказательства</p>
                    <p className="mt-1 text-sm text-slate-400">Evidence связывается только через существующий passport flow и closure policy.</p>
                    <div className="mt-3 grid gap-2">
                      {viewModel.right.passport.items.filter((item) => !item.done).slice(0, 4).map((item) => (
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2" key={`passport-evidence:${item.key}`}>
                          <p className="text-sm font-semibold text-white">{item.label}</p>
                          <p className="mt-1 text-xs text-slate-400">Требует подтверждения или связанного события перед закрытием.</p>
                        </div>
                      ))}
                      {!viewModel.right.passport.items.some((item) => !item.done) ? (
                        <p className="rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                          Обязательные evidence-секции заполнены по текущему паспорту.
                        </p>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {workspaceMode === "passport" && passportWorkspaceTab === "operations" ? (
                  <div className="mb-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <p className="font-semibold text-white">Операции и диагностика</p>
                    <p className="mt-1 text-sm text-slate-400">Связанные операции используются как доказательная база паспорта решения.</p>
                    <OperationsTable
                      onCancel={(operationId) => operationCancelMutation.mutate(operationId)}
                      onRetry={(operationId) => operationRetryMutation.mutate(operationId)}
                      operations={viewModel.right.operations}
                    />
                  </div>
                ) : null}
                {workspaceMode === "passport" && passportWorkspaceTab === "readiness" ? (
                  <div className="mb-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <p className="font-semibold text-white">Готовность к закрытию</p>
                    <p className="mt-1 text-sm text-slate-400">
                      Заполнено {viewModel.right.passport.done} из {viewModel.right.passport.total}. Закрытие остаётся через существующую проверку прав и closure policy.
                    </p>
                    <div className="mt-4 h-3 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full rounded-full bg-emerald-400" style={{ width: `${passportProgress(viewModel.right.passport)}%` }} />
                    </div>
                    {selectedTicket.closurePlan.blockers.length ? (
                      <div className="mt-4 grid gap-2">
                        {selectedTicket.closurePlan.blockers.slice(0, 4).map((blocker) => (
                          <div className="rounded-lg border border-amber-300/20 bg-amber-500/10 px-3 py-2" key={`passport-readiness:${blocker.key}`}>
                            <p className="text-sm font-semibold text-amber-50">{blocker.label}</p>
                            {blocker.detail ? <p className="mt-1 text-xs text-amber-100/80">{blocker.detail}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-4 rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                        Блокеров закрытия по текущему payload нет.
                      </p>
                    )}
                  </div>
                ) : null}
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Паспорт решения</p>
                    <p className={`mt-1 font-semibold ${isLightTheme ? "text-slate-950" : "text-white"}`}>
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
                  <div
                    className={`mt-4 rounded-xl px-4 py-3 ${
                      isLightTheme ? "border border-amber-300 bg-amber-50 text-amber-950" : "border border-amber-400/25 bg-amber-500/10"
                    }`}
                    data-testid="closure-focus-card"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`text-xs font-semibold uppercase tracking-[0.16em] ${isLightTheme ? "text-amber-800" : "text-amber-100/80"}`}>Фокус паспорта</p>
                        <p className={`mt-1 break-words text-sm font-semibold ${isLightTheme ? "text-amber-950" : "text-white"}`}>{closureFocus.label}</p>
                        {closureGuide ? (
                          <p className={`mt-1 text-xs font-semibold ${isLightTheme ? "text-amber-900" : "text-amber-100"}`}>Секция: {closureGuide.section}</p>
                        ) : null}
                      </div>
                      <span
                        className={`shrink-0 rounded-md border px-2 py-1 text-[11px] font-semibold ${
                          isLightTheme ? "border-amber-300 bg-white text-amber-900" : "border-amber-300/25 bg-white/[0.06] text-amber-50"
                        }`}
                      >
                        {closureFocus.actionLabel}
                      </span>
                    </div>
                    {closureFocus.detail ? (
                      <p className={`mt-2 break-words text-xs leading-5 ${isLightTheme ? "text-amber-900" : "text-amber-100/80"}`}>{closureFocus.detail}</p>
                    ) : null}
                    {closureGuide ? (
                      <div className={`mt-3 rounded-lg px-3 py-2 ${isLightTheme ? "border border-amber-200 bg-white" : "border border-white/10 bg-white/[0.04]"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${isLightTheme ? "text-amber-800" : "text-amber-100/70"}`}>Следующий шаг</p>
                        <p className={`mt-1 text-xs leading-5 ${isLightTheme ? "text-amber-950" : "text-amber-50"}`}>{closureGuide.hint}</p>
                      </div>
                    ) : null}
                    {closureGuide?.targetAction ? (
                      <div className={`mt-2 rounded-lg px-3 py-2 ${isLightTheme ? "border border-amber-300 bg-amber-100" : "border border-amber-300/20 bg-amber-300/10"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${isLightTheme ? "text-amber-800" : "text-amber-100/70"}`}>Целевое действие</p>
                        <p className={`mt-1 text-xs font-semibold ${isLightTheme ? "text-amber-950" : "text-amber-50"}`}>{closureGuide.targetAction}</p>
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
            </>
          )}
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
