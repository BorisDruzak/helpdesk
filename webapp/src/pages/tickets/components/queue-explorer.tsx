import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Settings2 } from "lucide-react";
import type {
  SupportQueueMassActionRequest,
  SupportQueueMassActionResult,
  SupportQueueSavedViewItem,
  SupportQueueSavedViewScope,
  SupportQueueSavedViewUpsertRequest,
  SupportQueueScope,
} from "../../../features/queues/api";
import type {
  SupportWorkspaceQueue,
  SupportWorkspaceSelectedTicket,
  SupportWorkspaceSlice,
  SupportWorkspaceTicketItem,
} from "../../../features/queues/support-workspace-model";
import { toneClasses } from "./workspace-component-utils";

type QueueExplorerTab = "mine" | "queues" | "slices";
type QueueColumnId =
  | "number"
  | "subject"
  | "requester"
  | "priority"
  | "status"
  | "next_action"
  | "sla"
  | "queue"
  | "assignee"
  | "last_event"
  | "unread";

type QueueExplorerProps = {
  activeQueueId: string | null;
  cleanupNoisePending?: boolean;
  massActionPending?: boolean;
  massActionResult?: SupportQueueMassActionResult | null;
  defaultColumns?: string[];
  defaultViewId?: string | null;
  onActiveQueueChange: (queueId: string | null) => void;
  onCleanupNoise: () => void;
  onDeleteSavedView: (viewId: string) => void;
  onMassAction: (request: SupportQueueMassActionRequest) => void;
  onOpenTicket: (ticketId: string) => void;
  onPersistDefaultColumns: (viewId: string | null, request: SupportQueueSavedViewUpsertRequest) => void;
  onSaveSavedView: (request: SupportQueueSavedViewUpsertRequest) => void;
  onScopeChange: (scope: SupportQueueScope) => void;
  onSearchChange: (value: string) => void;
  onSelectTicket: (ticketId: string) => void;
  onShowArchiveChange: (value: boolean) => void;
  onSmartViewChange: (viewId: string) => void;
  queues: SupportWorkspaceQueue[];
  scope: SupportQueueScope;
  search: string;
  selectedTicket: SupportWorkspaceSelectedTicket | null;
  selectedViewId: string;
  savedViewMutationPending?: boolean;
  savedViews?: SupportQueueSavedViewItem[];
  savedViewsError?: boolean;
  savedViewsLoading?: boolean;
  showArchive: boolean;
  slices: SupportWorkspaceSlice[];
  tickets: SupportWorkspaceTicketItem[];
};

type SavedQueueView = {
  id: string;
  name: string;
  scope: SupportQueueScope;
  smartViewId: string;
  queueId: string | null;
  search: string;
  showArchive: boolean;
  columns: QueueColumnId[];
};

type SavedQueueViewLike = {
  id: string;
  name: string;
  scope: SupportQueueScope;
  smartViewId: string;
  queueId: string | null;
  search: string;
  showArchive: boolean;
  columns: QueueColumnId[];
  backendView?: SupportQueueSavedViewItem;
};

const QUEUE_COLUMNS_STORAGE_KEY = "support-workspace-queue-table-columns";
const QUEUE_SAVED_VIEWS_STORAGE_KEY = "support-workspace-queue-saved-views";
const REQUIRED_QUEUE_COLUMNS = new Set<QueueColumnId>(["number", "subject"]);
const DEFAULT_QUEUE_COLUMNS: QueueColumnId[] = [
  "number",
  "subject",
  "requester",
  "priority",
  "status",
  "next_action",
  "sla",
  "queue",
  "assignee",
  "last_event",
  "unread",
];
const QUEUE_COLUMN_OPTIONS: Array<{ id: QueueColumnId; label: string }> = [
  { id: "number", label: "№" },
  { id: "subject", label: "Тема" },
  { id: "requester", label: "Заявитель" },
  { id: "priority", label: "P" },
  { id: "status", label: "Статус" },
  { id: "next_action", label: "Next action" },
  { id: "sla", label: "SLA" },
  { id: "queue", label: "Очередь" },
  { id: "assignee", label: "Исполнитель" },
  { id: "last_event", label: "Последнее" },
  { id: "unread", label: "Непроч." },
];

function getInitialQueueColumns(): QueueColumnId[] {
  if (typeof window === "undefined") return DEFAULT_QUEUE_COLUMNS;
  try {
    const raw = window.localStorage.getItem(QUEUE_COLUMNS_STORAGE_KEY);
    if (!raw) return DEFAULT_QUEUE_COLUMNS;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return DEFAULT_QUEUE_COLUMNS;
    const valid = parsed.filter((item): item is QueueColumnId => QUEUE_COLUMN_OPTIONS.some((column) => column.id === item));
    return Array.from(new Set([...REQUIRED_QUEUE_COLUMNS, ...valid]));
  } catch {
    return DEFAULT_QUEUE_COLUMNS;
  }
}

function normalizeQueueColumns(columns: string[] | undefined): QueueColumnId[] {
  const valid = (columns ?? []).filter((item): item is QueueColumnId => QUEUE_COLUMN_OPTIONS.some((column) => column.id === item));
  if (!valid.length) return DEFAULT_QUEUE_COLUMNS;
  return Array.from(new Set([...REQUIRED_QUEUE_COLUMNS, ...valid]));
}

function getInitialSavedViews(): SavedQueueView[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(QUEUE_SAVED_VIEWS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is SavedQueueView =>
      Boolean(item && typeof item === "object" && "id" in item && "name" in item),
    );
  } catch {
    return [];
  }
}

function persistJson(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Queue preferences are a convenience; the table remains usable without localStorage.
  }
}

function stringFromFilters(filters: Record<string, unknown>, key: string, fallback = ""): string {
  const value = filters[key];
  return typeof value === "string" ? value : fallback;
}

function boolFromFilters(filters: Record<string, unknown>, key: string, fallback = false): boolean {
  const value = filters[key];
  return typeof value === "boolean" ? value : fallback;
}

function savedViewToViewLike(view: SupportQueueSavedViewItem): SavedQueueViewLike {
  const filters = view.filters ?? {};
  const scopeValue = stringFromFilters(filters, "scope", "all");
  return {
    id: view.id,
    name: view.name,
    scope: scopeValue === "mine" ? "mine" : "all",
    smartViewId: stringFromFilters(filters, "smartViewId", "all"),
    queueId: stringFromFilters(filters, "queueId", "") || (view.queue_id ? String(view.queue_id) : null),
    search: stringFromFilters(filters, "search"),
    showArchive: boolFromFilters(filters, "showArchive"),
    columns: normalizeQueueColumns(view.columns),
    backendView: view,
  };
}

function localSavedViewToViewLike(view: SavedQueueView): SavedQueueViewLike {
  return {
    id: view.id,
    name: view.name,
    scope: view.scope,
    smartViewId: view.smartViewId,
    queueId: view.queueId,
    search: view.search,
    showArchive: view.showArchive,
    columns: normalizeQueueColumns(view.columns),
  };
}

function ticketActionScore(ticket: SupportWorkspaceTicketItem): number {
  let score = 0;
  const slaLabel = ticket.nextDueLabel.toLowerCase();
  if (ticket.slaRisk && slaLabel.includes("просроч")) score += 1000;
  else if (ticket.slaRisk) score += 800;
  if (ticket.priority === "P0" || ticket.priority === "P1") score += 300;
  if (ticket.unread) score += 250;
  if (ticket.assigneeLabel.toLowerCase().includes("не назнач")) score += 200;
  if (ticket.statusLabel.toLowerCase().includes("очеред")) score += 120;
  return score;
}

function getTicketSlaLabel(ticket: SupportWorkspaceTicketItem, selectedTicket: SupportWorkspaceSelectedTicket | null): string {
  if (selectedTicket?.id === ticket.id && selectedTicket.nextAction.timerType !== "none") {
    return selectedTicket.nextAction.remainingLabel;
  }
  const label = ticket.nextDueLabel.trim();
  return label && !label.toLowerCase().includes("нет срока") ? label : "SLA не назначен";
}

function slaClassName(label: string, ticket: SupportWorkspaceTicketItem): string {
  const normalized = label.toLowerCase();
  if (normalized.includes("не назнач")) return "text-slate-400";
  if (normalized.includes("просроч")) return "text-red-300";
  return ticket.slaRisk ? "text-amber-300" : "text-emerald-300";
}

function nextActionLabel(ticket: SupportWorkspaceTicketItem): string {
  if (ticket.unread) return "Requester";
  if (ticket.slaRisk) return "Support";
  if (ticket.assigneeLabel.toLowerCase().includes("не назнач")) return "Queue";
  return "Operator";
}

function buildCsv(rows: SupportWorkspaceTicketItem[]): string {
  const header = ["ticket", "subject", "requester", "priority", "status", "sla", "queue", "assignee", "updated"];
  const body = rows.map((ticket) =>
    [
      ticket.code,
      ticket.subject,
      ticket.requester,
      ticket.priority,
      ticket.statusLabel,
      ticket.nextDueLabel,
      ticket.queueLabel,
      ticket.assigneeLabel,
      ticket.updatedLabel,
    ]
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(","),
  );
  return [header.join(","), ...body].join("\n");
}

function parseQueueId(queueId: string | null): number | null {
  if (!queueId) return null;
  const parsed = Number(queueId);
  return Number.isFinite(parsed) ? parsed : null;
}

export function QueueExplorer({
  activeQueueId,
  cleanupNoisePending = false,
  massActionPending = false,
  massActionResult = null,
  defaultColumns,
  defaultViewId = null,
  onActiveQueueChange,
  onCleanupNoise,
  onDeleteSavedView,
  onMassAction,
  onOpenTicket,
  onPersistDefaultColumns,
  onSaveSavedView,
  onScopeChange,
  onSearchChange,
  onSelectTicket,
  onShowArchiveChange,
  onSmartViewChange,
  queues,
  scope,
  search,
  selectedTicket,
  selectedViewId,
  savedViewMutationPending = false,
  savedViews = [],
  savedViewsError = false,
  savedViewsLoading = false,
  showArchive,
  slices,
  tickets,
}: QueueExplorerProps) {
  const [activeTab, setActiveTab] = useState<QueueExplorerTab>("mine");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [massActionsOpen, setMassActionsOpen] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<QueueColumnId[]>(() => getInitialQueueColumns());
  const [localFallbackViews] = useState<SavedQueueView[]>(() => getInitialSavedViews());
  const [savedViewName, setSavedViewName] = useState("");
  const [savedViewScope, setSavedViewScope] = useState<SupportQueueSavedViewScope>("personal");
  const [massReason, setMassReason] = useState("queue_triage");
  const [massNote, setMassNote] = useState("");
  const [massPriority, setMassPriority] = useState<"P0" | "P1" | "P2" | "P3">("P2");
  const [massQueueId, setMassQueueId] = useState<string>("");
  const [massToolName, setMassToolName] = useState("diagnostics.basic");
  const [massProblemKey, setMassProblemKey] = useState("");
  const appliedDefaultViewRef = useRef<string | null>(null);
  const columnsChangedByUserRef = useRef(false);

  useEffect(() => {
    persistJson(QUEUE_COLUMNS_STORAGE_KEY, visibleColumns);
  }, [visibleColumns]);

  useEffect(() => {
    if (!activeQueueId && savedViewScope === "queue") {
      setSavedViewScope("personal");
    }
  }, [activeQueueId, savedViewScope]);

  useEffect(() => {
    if (!defaultColumns?.length) return;
    if (appliedDefaultViewRef.current === defaultViewId) return;
    appliedDefaultViewRef.current = defaultViewId;
    setVisibleColumns(normalizeQueueColumns(defaultColumns));
  }, [defaultColumns, defaultViewId]);

  useEffect(() => {
    if (!columnsChangedByUserRef.current) return;
    const timeout = window.setTimeout(() => {
      columnsChangedByUserRef.current = false;
      onPersistDefaultColumns(defaultViewId, {
        name: "Мой вид очереди",
        scope: "personal",
        filters: {
          scope,
          smartViewId: selectedViewId,
          queueId: activeQueueId,
          search,
          showArchive,
        },
        columns: visibleColumns,
        sort: [{ field: "action_score", direction: "desc" }],
        is_default: true,
        is_favorite: true,
      });
    }, 600);
    return () => window.clearTimeout(timeout);
  }, [activeQueueId, defaultViewId, onPersistDefaultColumns, scope, search, selectedViewId, showArchive, visibleColumns]);

  const effectiveSavedViews = useMemo<SavedQueueViewLike[]>(() => {
    if (savedViews.length || savedViewsLoading || !savedViewsError) {
      return savedViews.map(savedViewToViewLike);
    }
    return localFallbackViews.map(localSavedViewToViewLike);
  }, [localFallbackViews, savedViews, savedViewsError, savedViewsLoading]);

  const columnSet = useMemo(() => new Set(visibleColumns), [visibleColumns]);
  const sortedTickets = useMemo(
    () =>
      [...tickets].sort((left, right) => {
        const scoreDelta = ticketActionScore(right) - ticketActionScore(left);
        if (scoreDelta !== 0) return scoreDelta;
        if (left.priority !== right.priority) return left.priority.localeCompare(right.priority);
        return right.updatedLabel.localeCompare(left.updatedLabel);
      }),
    [tickets],
  );

  const selectedRows = sortedTickets.filter((ticket) => selectedIds.has(ticket.id));
  const allVisibleSelected = sortedTickets.length > 0 && sortedTickets.every((ticket) => selectedIds.has(ticket.id));
  const selectedTicketIds = Array.from(selectedIds);
  const selectedCount = selectedIds.size;
  const selectedQueueNumericId = parseQueueId(massQueueId || activeQueueId);

  function toggleColumn(columnId: QueueColumnId) {
    if (REQUIRED_QUEUE_COLUMNS.has(columnId)) return;
    columnsChangedByUserRef.current = true;
    setVisibleColumns((current) => {
      if (current.includes(columnId)) {
        return current.filter((item) => item !== columnId);
      }
      const next = [...current, columnId];
      return normalizeQueueColumns(next);
    });
  }

  function toggleTicket(ticketId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(ticketId)) next.delete(ticketId);
      else next.add(ticketId);
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds((current) => {
      if (sortedTickets.length > 0 && sortedTickets.every((ticket) => current.has(ticket.id))) {
        return new Set();
      }
      return new Set(sortedTickets.map((ticket) => ticket.id));
    });
  }

  function submitMassAction(request: Omit<SupportQueueMassActionRequest, "ticket_ids">) {
    if (!selectedTicketIds.length || massActionPending) return;
    onMassAction({ ...request, ticket_ids: selectedTicketIds });
  }

  function exportSelected() {
    const rows = selectedRows.length ? selectedRows : sortedTickets;
    const blob = new Blob([buildCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "support-queue.csv";
    link.click();
    URL.revokeObjectURL(url);
    setMassActionsOpen(false);
  }

  function saveCurrentView() {
    const name = savedViewName.trim();
    if (!name) return;
    const viewScope: SupportQueueSavedViewScope = savedViewScope === "queue" && activeQueueId ? "queue" : "personal";
    onSaveSavedView({
      name,
      scope: viewScope,
      queue_id: viewScope === "queue" ? parseQueueId(activeQueueId) : null,
      filters: {
        scope,
        smartViewId: selectedViewId,
        queueId: activeQueueId,
        search,
        showArchive,
      },
      columns: visibleColumns,
      sort: [{ field: "action_score", direction: "desc" }],
      is_favorite: true,
      is_default: false,
    });
    setSavedViewName("");
  }

  function importLocalSavedView(view: SavedQueueViewLike) {
    onSaveSavedView({
      name: view.name,
      scope: "personal",
      filters: {
        scope: view.scope,
        smartViewId: view.smartViewId,
        queueId: view.queueId,
        search: view.search,
        showArchive: view.showArchive,
      },
      columns: view.columns,
      sort: [{ field: "action_score", direction: "desc" }],
      is_favorite: true,
      is_default: false,
    });
  }

  function applySavedView(view: SavedQueueViewLike) {
    onScopeChange(view.scope);
    onSmartViewChange(view.smartViewId);
    onActiveQueueChange(view.queueId);
    onSearchChange(view.search);
    onShowArchiveChange(view.showArchive);
    setVisibleColumns(normalizeQueueColumns(view.columns));
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Очередь тикетов</h2>
          <p className="mt-1 text-sm text-slate-400">Таблица triage по тикетам, доступным текущей роли и очередям.</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <div className="relative">
            <button
              aria-expanded={columnsOpen}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.08]"
              onClick={() => setColumnsOpen((open) => !open)}
              type="button"
            >
              <Settings2 className="h-4 w-4" />
              Колонки
            </button>
            {columnsOpen ? (
              <div className="absolute right-0 top-11 z-30 w-64 rounded-xl border border-white/10 bg-[#101d30] p-3 shadow-2xl shadow-black/40">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Видимые колонки</p>
                <div className="mt-2 grid gap-1">
                  {QUEUE_COLUMN_OPTIONS.map((column) => (
                    <label className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-200 hover:bg-white/[0.05]" key={column.id}>
                      <input
                        checked={columnSet.has(column.id)}
                        disabled={REQUIRED_QUEUE_COLUMNS.has(column.id)}
                        onChange={() => toggleColumn(column.id)}
                        type="checkbox"
                      />
                      {column.label}
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="relative">
            <button
              aria-expanded={massActionsOpen}
              className={`h-10 rounded-xl border px-3 text-xs font-semibold transition ${
                selectedCount > 0 ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"
              }`}
              onClick={() => setMassActionsOpen((open) => !open)}
              type="button"
            >
              Массовые действия{selectedCount ? ` · ${selectedCount}` : ""}
            </button>
            {massActionsOpen ? (
              <div className="absolute right-0 top-11 z-20 w-[420px] max-w-[calc(100vw-2rem)] rounded-xl border border-white/10 bg-[#101d30] p-3 shadow-2xl shadow-black/40">
                <p className="text-xs text-slate-400">Выбрано: {selectedCount}. Backend применяет права к каждому тикету отдельно.</p>
                <div className="mt-3 grid gap-2">
                  <label className="text-xs font-semibold text-slate-300">
                    Причина
                    <input
                      className="mt-1 h-9 w-full rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                      onChange={(event) => setMassReason(event.currentTarget.value)}
                      value={massReason}
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || massActionPending}
                      onClick={() => submitMassAction({ action: "assign_self", reason: massReason })}
                      type="button"
                    >
                      Взять себе
                    </button>
                    <button
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || massActionPending}
                      onClick={() => submitMassAction({ action: "assign", assignee_id: null, reason: massReason })}
                      type="button"
                    >
                      Назначить авто
                    </button>
                  </div>
                  <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                    <select
                      className="h-9 rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                      onChange={(event) => setMassQueueId(event.currentTarget.value)}
                      value={massQueueId}
                    >
                      <option value="">Текущая/активная очередь</option>
                      {queues.map((queue) => (
                        <option key={queue.id} value={queue.id}>
                          {queue.label}
                        </option>
                      ))}
                    </select>
                    <button
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || !selectedQueueNumericId || massActionPending}
                      onClick={() => submitMassAction({ action: "change_queue", queue_id: selectedQueueNumericId, reason: massReason })}
                      type="button"
                    >
                      Сменить очередь
                    </button>
                  </div>
                  <div className="grid gap-2 md:grid-cols-[120px_1fr]">
                    <select
                      className="h-9 rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                      onChange={(event) => setMassPriority(event.currentTarget.value as "P0" | "P1" | "P2" | "P3")}
                      value={massPriority}
                    >
                      <option value="P0">P0</option>
                      <option value="P1">P1</option>
                      <option value="P2">P2</option>
                      <option value="P3">P3</option>
                    </select>
                    <button
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || massReason.trim().length < 3 || massActionPending}
                      onClick={() => submitMassAction({ action: "change_priority", priority: massPriority, reason: massReason })}
                      type="button"
                    >
                      Сменить приоритет
                    </button>
                  </div>
                  <label className="text-xs font-semibold text-slate-300">
                    Внутренняя заметка
                    <textarea
                      className="mt-1 min-h-[72px] w-full resize-y rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-sm text-white outline-none"
                      onChange={(event) => setMassNote(event.currentTarget.value)}
                      value={massNote}
                    />
                  </label>
                  <button
                    className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!selectedCount || !massNote.trim() || massActionPending}
                    onClick={() => submitMassAction({ action: "internal_note", internal_note: massNote, reason: massReason })}
                    type="button"
                  >
                    Добавить заметку
                  </button>
                  <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                    <input
                      className="h-9 rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                      onChange={(event) => setMassToolName(event.currentTarget.value)}
                      placeholder="tool_name"
                      value={massToolName}
                    />
                    <button
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || !massToolName.trim() || massActionPending}
                      onClick={() => submitMassAction({ action: "run_diagnostics", tool_name: massToolName.trim(), reason: massReason })}
                      type="button"
                    >
                      Диагностика
                    </button>
                  </div>
                  <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                    <input
                      className="h-9 rounded-lg border border-white/10 bg-black/15 px-3 text-sm text-white outline-none"
                      onChange={(event) => setMassProblemKey(event.currentTarget.value)}
                      placeholder="Ключ массовой проблемы"
                      value={massProblemKey}
                    />
                    <button
                      className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!selectedCount || !massProblemKey.trim() || massActionPending}
                      onClick={() => submitMassAction({ action: "link_mass_problem", mass_problem_key: massProblemKey.trim(), reason: massReason })}
                      type="button"
                    >
                      Связать
                    </button>
                  </div>
                  <button
                    className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-left text-sm font-semibold text-slate-200 hover:bg-white/[0.08]"
                    onClick={exportSelected}
                    type="button"
                  >
                    Экспорт CSV
                  </button>
                </div>
                {massActionResult ? (
                  <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.04] p-3 text-xs text-slate-300">
                    <p className="font-semibold text-white">
                      Результат: {massActionResult.success_count} успешно, {massActionResult.skipped_count} пропущено, {massActionResult.error_count} ошибок
                    </p>
                    <div className="mt-2 max-h-28 space-y-1 overflow-auto">
                      {massActionResult.results.slice(0, 5).map((item) => (
                        <p key={`${item.ticket_id}:${item.status}`}>{item.ticket_code ?? item.ticket_id}: {item.message}</p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 rounded-xl border border-white/10 bg-[#0d1828] p-3">
        <div className="grid grid-cols-3 gap-2 rounded-xl bg-white/[0.04] p-1">
          {[
            ["mine", "Мои"],
            ["queues", "Очереди"],
            ["slices", "Срезы"],
          ].map(([value, label]) => (
            <button
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
                activeTab === value ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
              key={value}
              onClick={() => {
                setActiveTab(value as QueueExplorerTab);
                if (value === "mine") onScopeChange("mine");
                if (value === "queues") onScopeChange("all");
              }}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
          <label className="flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-slate-400">
            <Search className="h-4 w-4" />
            <input
              className="min-w-0 flex-1 bg-transparent text-slate-100 outline-none placeholder:text-slate-500"
              onChange={(event) => onSearchChange(event.currentTarget.value)}
              placeholder="Поиск по номеру, теме, заявителю..."
              type="search"
              value={search}
            />
          </label>
          <select
            className="h-10 rounded-xl border border-white/10 bg-[#101d30] px-3 text-sm text-slate-200 outline-none"
            onChange={(event) => onScopeChange(event.currentTarget.value as SupportQueueScope)}
            value={scope}
          >
            <option value="mine">Мои тикеты</option>
            <option value="all">Все доступные</option>
          </select>
          <select
            className="h-10 rounded-xl border border-white/10 bg-[#101d30] px-3 text-sm text-slate-200 outline-none"
            onChange={(event) => onSmartViewChange(event.currentTarget.value)}
            value={selectedViewId}
          >
            {slices.map((slice) => (
              <option key={slice.id} value={slice.id}>
                {slice.label} · {slice.count}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-2 xl:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex flex-wrap gap-2 text-xs">
            <button
              className={`rounded-lg border px-3 py-2 font-semibold ${showArchive ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
              onClick={() => onShowArchiveChange(!showArchive)}
              type="button"
            >
              {showArchive ? "Архив включён" : "Показывать архив"}
            </button>
            <button
              className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 font-semibold text-slate-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              disabled={cleanupNoisePending}
              onClick={onCleanupNoise}
              type="button"
            >
              Скрыть test
            </button>
            <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-400">
              SLA: сначала просроченные и ближайшие к нарушению
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="h-9 min-w-[180px] rounded-lg border border-white/10 bg-black/15 px-3 text-xs text-white outline-none placeholder:text-slate-500"
              onChange={(event) => setSavedViewName(event.currentTarget.value)}
              placeholder="Название вида"
              value={savedViewName}
            />
            <select
              className="h-9 rounded-lg border border-white/10 bg-[#101d30] px-2 text-xs text-slate-200 outline-none"
              onChange={(event) => setSavedViewScope(event.currentTarget.value as SupportQueueSavedViewScope)}
              value={savedViewScope}
            >
              <option value="personal">Личный</option>
              <option disabled={!activeQueueId} value="queue">
                Для очереди
              </option>
            </select>
            <button
              className="h-9 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!savedViewName.trim() || savedViewMutationPending}
              onClick={saveCurrentView}
              type="button"
            >
              Сохранить вид
            </button>
          </div>
        </div>

        {effectiveSavedViews.length || savedViewsLoading || savedViewsError ? (
          <div className="flex flex-wrap items-center gap-2">
            {savedViewsLoading ? <span className="text-xs text-slate-500">Loading views...</span> : null}
            {savedViewsError ? <span className="text-xs text-amber-300">Backend views unavailable; local fallback is shown.</span> : null}
            {effectiveSavedViews.map((view) => (
              <span className="inline-flex items-center overflow-hidden rounded-lg border border-blue-400/20 bg-blue-500/10 text-xs font-semibold text-blue-100" key={view.id}>
                <button
                  className="px-3 py-1.5 hover:bg-blue-500/20"
                  onClick={() => applySavedView(view)}
                  type="button"
                >
                  {view.name}
                </button>
                {view.backendView ? (
                  <button
                    aria-label={`Delete view ${view.name}`}
                    className="border-l border-blue-300/20 px-2 py-1.5 text-blue-100/70 hover:bg-red-500/20 hover:text-red-100"
                    disabled={savedViewMutationPending}
                    onClick={() => onDeleteSavedView(view.id)}
                    type="button"
                  >
                    ×
                  </button>
                ) : (
                  <button
                    className="border-l border-blue-300/20 px-2 py-1.5 text-blue-100/70 hover:bg-blue-500/20"
                    disabled={savedViewMutationPending}
                    onClick={() => importLocalSavedView(view)}
                    type="button"
                  >
                    import
                  </button>
                )}
              </span>
            ))}
          </div>
        ) : null}

        {activeTab === "queues" ? (
          <div className="flex flex-wrap gap-2">
            <button
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${activeQueueId === null ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
              onClick={() => onActiveQueueChange(null)}
              type="button"
            >
              Все очереди
            </button>
            {queues.map((queue) => (
              <button
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${queue.active ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                key={queue.id}
                onClick={() => onActiveQueueChange(queue.active ? null : queue.id)}
                type="button"
              >
                {queue.label} · {queue.count}
              </button>
            ))}
          </div>
        ) : null}

        {activeTab === "slices" ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {slices.map((slice) => (
              <button
                className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold ${slice.active ? "border-blue-400/60 bg-blue-500/15 text-blue-100" : "border-white/10 bg-white/[0.04] text-slate-300"}`}
                key={slice.id}
                onClick={() => onSmartViewChange(slice.id)}
                type="button"
              >
                <span>{slice.label}</span>
                <span className="float-right rounded-full bg-white/10 px-2 py-0.5">{slice.count}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-xl border border-white/10 bg-[#0d1828]">
        <table className="w-full min-w-[1180px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#101d30] text-xs uppercase tracking-[0.12em] text-slate-500">
            <tr>
              <th className="w-10 px-3 py-3">
                <input aria-label="Выбрать все тикеты" checked={allVisibleSelected} onChange={toggleAll} type="checkbox" />
              </th>
              {columnSet.has("number") ? <th className="px-3 py-3">№</th> : null}
              {columnSet.has("subject") ? <th className="px-3 py-3">Тема</th> : null}
              {columnSet.has("requester") ? <th className="px-3 py-3">Заявитель</th> : null}
              {columnSet.has("priority") ? <th className="px-3 py-3">P</th> : null}
              {columnSet.has("status") ? <th className="px-3 py-3">Статус</th> : null}
              {columnSet.has("next_action") ? <th className="px-3 py-3">Next action</th> : null}
              {columnSet.has("sla") ? <th className="px-3 py-3">SLA</th> : null}
              {columnSet.has("queue") ? <th className="px-3 py-3">Очередь</th> : null}
              {columnSet.has("assignee") ? <th className="px-3 py-3">Исполнитель</th> : null}
              {columnSet.has("last_event") ? <th className="px-3 py-3">Последнее</th> : null}
              {columnSet.has("unread") ? <th className="px-3 py-3">Непроч.</th> : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {sortedTickets.map((ticket, index) => {
              const slaLabel = getTicketSlaLabel(ticket, selectedTicket);
              return (
                <tr
                  className={`cursor-pointer transition ${ticket.active ? "bg-blue-600/15 text-white" : "text-slate-300 hover:bg-white/[0.04]"}`}
                  data-ticket-row-index={index}
                  key={ticket.id}
                  onClick={() => onSelectTicket(ticket.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      onOpenTicket(ticket.id);
                      return;
                    }
                    if (event.key === " ") {
                      event.preventDefault();
                      toggleTicket(ticket.id);
                      return;
                    }
                    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                      event.preventDefault();
                      const nextIndex = event.key === "ArrowDown" ? index + 1 : index - 1;
                      const nextRow = document.querySelector<HTMLElement>(`[data-ticket-row-index="${nextIndex}"]`);
                      nextRow?.focus();
                    }
                  }}
                  tabIndex={0}
                >
                  <td className="px-3 py-3">
                    <input
                      aria-label={`Выбрать ${ticket.code}`}
                      checked={selectedIds.has(ticket.id)}
                      onChange={() => toggleTicket(ticket.id)}
                      onClick={(event) => event.stopPropagation()}
                      type="checkbox"
                    />
                  </td>
                  {columnSet.has("number") ? <td className="whitespace-nowrap px-3 py-3 font-semibold text-blue-200">{ticket.code}</td> : null}
                  {columnSet.has("subject") ? (
                    <td className="min-w-[260px] px-3 py-3">
                      <p className="truncate font-semibold text-white" title={ticket.subject}>{ticket.subject}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">{ticket.requester} · {ticket.queueLabel}</p>
                    </td>
                  ) : null}
                  {columnSet.has("requester") ? <td className="max-w-[180px] truncate px-3 py-3" title={ticket.requester}>{ticket.requester}</td> : null}
                  {columnSet.has("priority") ? (
                    <td className="px-3 py-3">
                      <span className={`rounded-md border px-2 py-1 text-xs font-bold ${toneClasses(ticket.priorityTone)}`}>{ticket.priority}</span>
                    </td>
                  ) : null}
                  {columnSet.has("status") ? (
                    <td className="px-3 py-3">
                      <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(ticket.statusTone)}`}>{ticket.statusLabel}</span>
                    </td>
                  ) : null}
                  {columnSet.has("next_action") ? <td className="whitespace-nowrap px-3 py-3 text-xs font-semibold text-blue-200">{nextActionLabel(ticket)}</td> : null}
                  {columnSet.has("sla") ? <td className={`whitespace-nowrap px-3 py-3 text-xs font-semibold ${slaClassName(slaLabel, ticket)}`}>{slaLabel}</td> : null}
                  {columnSet.has("queue") ? <td className="px-3 py-3">{ticket.queueLabel}</td> : null}
                  {columnSet.has("assignee") ? <td className="px-3 py-3">{ticket.assigneeLabel}</td> : null}
                  {columnSet.has("last_event") ? <td className="whitespace-nowrap px-3 py-3 text-slate-400">{ticket.updatedLabel}</td> : null}
                  {columnSet.has("unread") ? (
                    <td className="px-3 py-3">
                      {ticket.unread ? <span className="rounded-full bg-blue-500 px-2 py-0.5 text-xs font-bold text-white">да</span> : <span className="text-slate-600">-</span>}
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!sortedTickets.length ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-slate-400">
          По текущим фильтрам тикеты не найдены.
        </div>
      ) : null}
      {selectedTicket ? <p className="mt-3 text-xs text-slate-500">Preview выбранного тикета открыт справа. Enter или кнопка в preview открывает полный чат.</p> : null}
    </section>
  );
}
