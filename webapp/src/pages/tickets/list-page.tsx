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
  fetchSupportQueue,
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
  postSupportTicketAssign,
  postSupportTicketMessage,
  postSupportTicketPlaybookRun,
  postSupportTicketPriority,
  postSupportTicketQueue,
  postSupportTicketReroute,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportQueueScope,
  type SupportTicketTimelineFilter,
} from "../../features/queues/api";
import {
  mapSupportTimelineEntries,
  mapSupportWorkspaceViewModel,
} from "../../features/queues/support-workspace-mappers";
import type {
  SupportWorkspacePassport,
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

function OperationSummaryCard({ operation }: { operation: SupportWorkspaceOperationSummary }) {
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
      {operation.summary ? <p className="mt-2 break-words text-xs leading-5 text-slate-400">{operation.summary}</p> : null}
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
          type="button"
        >
          <RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </button>
        <button
          aria-label={isLightTheme ? "Тёмная тема" : "Светлая тема"}
          className={`flex h-10 w-10 items-center justify-center rounded-xl border transition ${isLightTheme ? "border-slate-200 bg-slate-100 text-slate-700 hover:text-slate-950" : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"}`}
          onClick={onToggleTheme}
          type="button"
        >
          {isLightTheme ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </button>
        <button
          aria-label="Уведомления"
          className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300"
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
          type="button"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
        <button
          aria-label="Помощь"
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300"
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
  const [statusDraft, setStatusDraft] = useState("");
  const [moreOpen, setMoreOpen] = useState(false);
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

  const viewModel = useMemo(
    () =>
      mapSupportWorkspaceViewModel({
        activeQueueId,
        activeSmartView: smartView,
        detail: workspaceQuery.data?.detail,
        knowledge: workspaceQuery.data?.knowledge,
        passport: workspaceQuery.data?.passport,
        passportReadiness: workspaceQuery.data?.passport_readiness,
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
  const firstRunnableTool = viewModel.right.tools.find((item) => item.enabled);
  const firstRunnablePlaybook = viewModel.right.playbooks.find((item) => item.enabled);
  const activeOperations = viewModel.right.operations.filter((operation) => operation.active);

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

  const statusMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicketId || !statusDraft) {
        return null;
      }
      return postSupportTicketStatus(selectedTicketId, statusDraft);
    },
    onSuccess: async () => {
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

  const moreActionMutation = useMutation({
    mutationFn: async (action: "assign_self" | "queue" | "priority" | "reroute") => {
      if (!selectedTicketId) {
        return null;
      }
      if (action === "assign_self") {
        return postSupportTicketAssign(selectedTicketId, {
          assigneeId: session?.user_login ?? undefined,
          reason: "operator_self_assign",
        });
      }
      if (action === "queue") {
        const targetQueue = queueQuery.data?.summary.queue_counts.find(
          (queue) => queue.id !== null && String(queue.code ?? queue.name ?? queue.id) !== viewModel.selectedTicket?.queueLabel,
        );
        if (!targetQueue?.id) {
          return null;
        }
        return postSupportTicketQueue(selectedTicketId, {
          queueId: targetQueue.id,
          reason: "operator_queue_change",
        });
      }
      if (action === "priority") {
        return postSupportTicketPriority(selectedTicketId, {
          priority: viewModel.selectedTicket?.priority === "P0" ? "P1" : "P0",
          reason: "operator_priority_change",
        });
      }
      return postSupportTicketReroute(selectedTicketId, { reason: "manual_recalculate" });
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
  const internalNoteAllowed = selectedTicket?.canSendInternalNote ?? false;
  const actionError =
    messageMutation.error || statusMutation.error || toolRunMutation.error || playbookRunMutation.error || moreActionMutation.error;

  useEffect(() => {
    if (composerMode === "internal" && selectedTicket && !selectedTicket.canSendInternalNote) {
      setComposerMode("public");
    }
  }, [composerMode, selectedTicket]);

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

          {selectedTicketId && workspaceQuery.isError ? (
            <div className="m-6 rounded-xl border border-red-400/30 bg-red-500/10 px-5 py-4 text-sm text-red-100">
              {workspaceQuery.error instanceof Error ? workspaceQuery.error.message : "Не удалось загрузить тикет"}
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
                    <select
                      className="h-10 rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-200 outline-none"
                      onChange={(event) => setStatusDraft(event.currentTarget.value)}
                      value={statusDraft}
                    >
                      <option value="">Сменить статус</option>
                      {(workspaceQuery.data?.detail.actions.status_options ?? []).map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <button
                      className="h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 disabled:opacity-50"
                      disabled={!statusDraft || statusMutation.isPending}
                      onClick={() => statusMutation.mutate()}
                      type="button"
                    >
                      Применить
                    </button>
                    <div className="relative">
                      <button
                        aria-expanded={moreOpen}
                        className="h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 hover:text-white disabled:opacity-50"
                        disabled={moreActionMutation.isPending}
                        onClick={() => setMoreOpen((open) => !open)}
                        type="button"
                      >
                        Ещё
                      </button>
                      {moreOpen ? (
                        <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-xl border border-white/10 bg-[#101d30] p-1 shadow-2xl shadow-black/40">
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10"
                            onClick={() => moreActionMutation.mutate("assign_self")}
                            type="button"
                          >
                            Назначить на себя
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!queueQuery.data?.summary.queue_counts.some((queue) => queue.id !== null)}
                            onClick={() => moreActionMutation.mutate("queue")}
                            type="button"
                          >
                            Сменить очередь
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10"
                            onClick={() => moreActionMutation.mutate("priority")}
                            type="button"
                          >
                            Изменить приоритет
                          </button>
                          <button
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10"
                            onClick={() => moreActionMutation.mutate("reroute")}
                            type="button"
                          >
                            Пересчитать маршрут
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
                {actionError ? (
                  <p className="mt-3 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                    {actionError instanceof Error ? actionError.message : "Действие не выполнено"}
                  </p>
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
                  {visibleTimeline.length === 0 ? (
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-5 py-10 text-center text-sm text-slate-400">
                      В выбранном фильтре нет событий.
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
                                  <p className={`mt-1 font-semibold ${operationResultTextClass(item.operation)}`}>
                                    {item.operation.summary ?? item.operation.preview ?? "Нет результата"}
                                  </p>
                                </div>
                              </div>
                              {item.operation.preview && item.operation.summary && item.operation.preview !== item.operation.summary ? (
                                <p className="mt-3 break-words rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs leading-5 text-slate-400">
                                  {item.operation.preview}
                                </p>
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
                        <OperationSummaryCard key={operation.id} operation={operation} />
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
                    {[...viewModel.right.playbooks, ...viewModel.right.tools].slice(0, 8).map((item) => {
                      const Icon = toolIcon(item);
                      return (
                        <div className={`rounded-xl border p-3 ${item.enabled ? "border-white/10 bg-white/[0.03]" : "border-white/5 bg-white/[0.02] opacity-55"}`} key={`${item.id}:${item.title}`}>
                          <div className="flex items-start gap-3">
                            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/15 text-blue-200">
                              <Icon className="h-4 w-4" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-white">{item.title}</p>
                                <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-semibold text-slate-400">
                                  {item.kind === "playbook" ? "Playbook" : "Tool"}
                                </span>
                              </div>
                              <p className="truncate text-xs text-slate-400">{item.subtitle}</p>
                            </div>
                          </div>
                          {item.metaLabels.length ? (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {item.metaLabels.slice(0, 4).map((label) => (
                                <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-slate-400" key={`${item.id}:${label}`}>
                                  {label}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {!item.enabled && item.disabledReason ? (
                            <p className="mt-2 rounded-lg border border-amber-400/20 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-100">
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
                <div className="mt-4 space-y-2">
                  {viewModel.right.passport.items.map((item) => (
                    <div className="flex items-center gap-3 text-sm" key={item.key}>
                      {item.done ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <Clock3 className="h-4 w-4 text-slate-500" />}
                      <span className={item.done ? "text-slate-200" : "text-slate-500"}>{item.label}</span>
                    </div>
                  ))}
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
