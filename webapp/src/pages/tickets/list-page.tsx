import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  Clock3,
  FileCheck2,
  Inbox,
  Lock,
  MessageSquare,
  MoreHorizontal,
  Network,
  Paperclip,
  Play,
  Printer,
  RefreshCcw,
  Search,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Star,
  UserRound,
  UsersRound,
  Wrench,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  fetchSupportQueue,
  fetchSupportTicketDetail,
  fetchSupportTicketPassport,
  fetchSupportTicketPlaybooks,
  fetchSupportTicketTools,
  postSupportTicketMessage,
  postSupportTicketPlaybookRun,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportQueueScope,
} from "../../features/queues/api";
import {
  mapSupportWorkspaceViewModel,
} from "../../features/queues/support-workspace-mappers";
import type {
  SupportWorkspaceQueue,
  SupportWorkspaceSlice,
  SupportWorkspaceTimelineKind,
  SupportWorkspaceToolItem,
} from "../../features/queues/support-workspace-model";
import { useSession } from "../../features/auth/session-provider";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

type ComposerMode = "public" | "internal";
type SidebarTab = "context" | "sla" | "tools" | "knowledge" | "passport";
type TimelineFilter = "all" | SupportWorkspaceTimelineKind;

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

function toolIcon(item: SupportWorkspaceToolItem) {
  if (item.id.includes("dns")) {
    return Network;
  }
  if (item.id.includes("playbook") || item.id.includes("diagnose")) {
    return Sparkles;
  }
  return Wrench;
}

function SupportWorkspaceTopbar({
  notificationCount,
  onRefresh,
  refreshing,
  search,
  setSearch,
  userLogin,
  userRole,
}: {
  notificationCount: number;
  onRefresh: () => void;
  refreshing: boolean;
  search: string;
  setSearch: (value: string) => void;
  userLogin: string;
  userRole: string;
}) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-white/10 bg-[#081321]/95 px-4 text-slate-100 backdrop-blur-xl">
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

  const detailQuery = useQuery({
    queryKey: ["tickets-workspace-detail", selectedTicketId],
    queryFn: () => fetchSupportTicketDetail(selectedTicketId!),
    enabled: Boolean(selectedTicketId),
    retry: false,
  });

  const toolsQuery = useQuery({
    queryKey: ["tickets-workspace-tools", selectedTicketId],
    queryFn: () => fetchSupportTicketTools(selectedTicketId!),
    enabled: Boolean(selectedTicketId),
    retry: false,
  });

  const playbooksQuery = useQuery({
    queryKey: ["tickets-workspace-playbooks", selectedTicketId],
    queryFn: () => fetchSupportTicketPlaybooks(selectedTicketId!),
    enabled: Boolean(selectedTicketId),
    retry: false,
  });

  const passportQuery = useQuery({
    queryKey: ["tickets-workspace-passport", selectedTicketId],
    queryFn: () => fetchSupportTicketPassport(selectedTicketId!),
    enabled: Boolean(selectedTicketId),
    retry: false,
  });

  const viewModel = useMemo(
    () =>
      mapSupportWorkspaceViewModel({
        activeQueueId,
        activeSmartView: smartView,
        detail: detailQuery.data,
        passport: passportQuery.data,
        playbooks: playbooksQuery.data,
        queue: queueQuery.data,
        selectedTicketId,
        tools: toolsQuery.data,
      }),
    [activeQueueId, detailQuery.data, passportQuery.data, playbooksQuery.data, queueQuery.data, selectedTicketId, smartView, toolsQuery.data],
  );

  const visibleTickets = activeQueueId
    ? viewModel.left.tickets.filter((ticket) => ticket.queueLabel === activeQueueId)
    : viewModel.left.tickets;

  const visibleTimeline =
    timelineFilter === "all"
      ? viewModel.selectedTicket?.timeline ?? []
      : (viewModel.selectedTicket?.timeline ?? []).filter((item) => item.kind === timelineFilter);

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
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-detail", selectedTicketId] }),
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
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-detail", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-queue"] }),
      ]);
    },
  });

  const toolRunMutation = useMutation({
    mutationFn: async () => {
      const tool = toolsQuery.data?.tools.find((item) => !item.install_required);
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
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-detail", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-tools", selectedTicketId] }),
      ]);
    },
  });

  const playbookRunMutation = useMutation({
    mutationFn: async () => {
      const playbook = playbooksQuery.data?.playbooks.find((item) => item.can_run);
      if (!selectedTicketId || !playbook) {
        return null;
      }
      return postSupportTicketPlaybookRun(selectedTicketId, { playbookVersionId: playbook.playbook_version_id });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-detail", selectedTicketId] }),
        queryClient.invalidateQueries({ queryKey: ["tickets-workspace-playbooks", selectedTicketId] }),
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
      detailQuery.refetch(),
      toolsQuery.refetch(),
      playbooksQuery.refetch(),
      passportQuery.refetch(),
    ]);
  }

  const selectedTicket = viewModel.selectedTicket;
  const internalNoteAllowed = selectedTicket?.canSendInternalNote ?? false;
  const actionError =
    messageMutation.error || statusMutation.error || toolRunMutation.error || playbookRunMutation.error;

  useEffect(() => {
    if (composerMode === "internal" && selectedTicket && !selectedTicket.canSendInternalNote) {
      setComposerMode("public");
    }
  }, [composerMode, selectedTicket]);

  return (
    <section className="flex h-screen min-h-screen flex-col overflow-hidden bg-[#07111f] text-slate-100">
      <h1 className="sr-only">Тикеты</h1>
      <SupportWorkspaceTopbar
        notificationCount={detailQuery.data?.snapshot.notification_unread ?? 0}
        onRefresh={refreshAll}
        refreshing={queueQuery.isFetching || detailQuery.isFetching}
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

          {selectedTicketId && detailQuery.isLoading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">Загружаем тикет...</div>
          ) : null}

          {selectedTicketId && detailQuery.isError ? (
            <div className="m-6 rounded-xl border border-red-400/30 bg-red-500/10 px-5 py-4 text-sm text-red-100">
              {detailQuery.error instanceof Error ? detailQuery.error.message : "Не удалось загрузить тикет"}
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
                    disabled={toolRunMutation.isPending || viewModel.right.tools.length === 0}
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
                      {(detailQuery.data?.actions.status_options ?? []).map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <button
                      className="h-10 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-slate-200 disabled:opacity-50"
                      disabled={!statusDraft || statusMutation.isPending}
                      onClick={() => statusMutation.mutate()}
                      type="button"
                    >
                      Ещё
                    </button>
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
                            <div className="mt-3 grid gap-3 rounded-lg border border-white/10 bg-[#111f33] p-3 text-sm md:grid-cols-3">
                              <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Операция</p>
                                <p className="mt-1 font-semibold text-white">{item.operation.name}</p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Статус</p>
                                <p className="mt-1 font-semibold text-amber-200">{item.operation.status}</p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Итог</p>
                                <p className="mt-1 font-semibold text-red-200">{item.operation.summary ?? item.operation.preview ?? "Нет результата"}</p>
                              </div>
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
            <div className="grid grid-cols-5 gap-1 rounded-xl bg-white/[0.04] p-1">
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
                    <div>
                      <p className="font-semibold text-white">{viewModel.right.context.requester.name}</p>
                      <p className="text-sm text-slate-400">{viewModel.right.context.requester.department}</p>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-slate-300">
                    <p>{viewModel.right.context.requester.phone}</p>
                    <p>{viewModel.right.context.requester.email}</p>
                    <p>{viewModel.right.context.requester.location}</p>
                  </div>
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
                  <p className="mt-2 text-sm text-slate-500">Последний вход: {viewModel.right.context.device.lastSeenLabel}</p>
                </section>

                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Категория / услуга</p>
                  <dl className="mt-3 space-y-2 text-sm">
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Тип</dt><dd className="text-right text-slate-200">{viewModel.right.context.classification.ticketType}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Сервис</dt><dd className="text-right text-slate-200">{viewModel.right.context.classification.service}</dd></div>
                    <div className="flex justify-between gap-3"><dt className="text-slate-500">Источник</dt><dd className="text-right text-slate-200">{viewModel.right.context.classification.source}</dd></div>
                  </dl>
                </section>
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "sla" ? (
              <div className="space-y-3">
                {selectedTicket.timers.map((timer) => (
                  <section className="rounded-xl border border-white/10 bg-[#111f33] p-4" key={timer.key}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-white">{timer.label}</p>
                      <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(timerStatusToTone(timer.status))}`}>
                        {timer.remainingLabel}
                      </span>
                    </div>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                      <div className={`h-full ${progressTone(timer.status)}`} style={{ width: `${timer.progress}%` }} />
                    </div>
                  </section>
                ))}
                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <p className="font-semibold text-white">OLA обработка</p>
                  <p className="mt-2 text-sm text-slate-400">Детальные OLA timers будут подключены через backend DTO. Текущий риск уже учитывается в smart views.</p>
                </section>
              </div>
            ) : null}

            {selectedTicket && sidebarTab === "tools" ? (
              <div className="space-y-3">
                <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-white">Инструменты / Playbook</p>
                    <button
                      className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                      disabled={playbookRunMutation.isPending || !playbooksQuery.data?.playbooks.some((item) => item.can_run)}
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
                          <div className="flex items-center gap-3">
                            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/15 text-blue-200">
                              <Icon className="h-4 w-4" />
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-white">{item.title}</p>
                              <p className="truncate text-xs text-slate-400">{item.subtitle}</p>
                            </div>
                          </div>
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
              <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-violet-300" />
                  <p className="font-semibold text-white">AI-рекомендация / Бета</p>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  Knowledge suggestions пока не имеют отдельного typed endpoint. Блок оставлен вторичным и не запускает действий без подтверждения оператора.
                </p>
                <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-400">
                  <BookOpen className="mr-2 inline h-4 w-4" />
                  Связанные статьи и похожие тикеты появятся после подключения knowledge API.
                </div>
              </section>
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
                  <FileCheck2 className="h-5 w-5 text-emerald-300" />
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
