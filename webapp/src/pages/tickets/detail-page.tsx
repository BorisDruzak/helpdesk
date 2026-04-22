import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Copy,
  Paperclip,
  RefreshCcw,
  Wrench
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Avatar } from "../../components/ui/avatar";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import {
  fetchSupportQueue,
  fetchSupportTicketDetail,
  fetchSupportTicketTools,
  postSupportTicketMessage,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportCountItem,
  type SupportQueueScope,
  type SupportTicketDetailPayload,
  type SupportTicketToolsPayload
} from "../../features/queues/api";
import { getSharedWebRealtimeClient } from "../../shared/realtime/client";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function getStatusTone(status: string) {
  switch (status) {
    case "in_progress":
      return "success" as const;
    case "waiting_on_user":
      return "warning" as const;
    case "resolved":
    case "closed":
      return "info" as const;
    case "new":
      return "brand" as const;
    default:
      return "neutral" as const;
  }
}

function getCount(items: SupportCountItem[] | undefined, value: string) {
  return items?.find((item) => item.value === value)?.count ?? 0;
}

function getRoleTone(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.from_role === "support" || entry.from_role === "agent") {
    return "agent" as const;
  }
  if (entry.from_role === "user" || entry.from_role === "client") {
    return "client" as const;
  }
  return "neutral" as const;
}

function getRoleLabel(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.visibility === "internal") {
    return "Внутренняя заметка";
  }
  if (entry.event_type === "tool_call_started" || entry.event_type === "tool_call_result") {
    return "Инструмент";
  }
  if (entry.from_role === "support" || entry.from_role === "agent") {
    return "Агент";
  }
  if (entry.from_role === "user" || entry.from_role === "client") {
    return "Клиент";
  }
  return "Система";
}

function getRoleBadgeTone(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.visibility === "internal") {
    return "warning" as const;
  }
  if (entry.event_type === "tool_call_started" || entry.event_type === "tool_call_result") {
    return "info" as const;
  }
  if (entry.from_role === "support" || entry.from_role === "agent") {
    return "info" as const;
  }
  if (entry.from_role === "user" || entry.from_role === "client") {
    return "neutral" as const;
  }
  return "brand" as const;
}

function describePresence(value: boolean) {
  return value ? "онлайн" : "офлайн";
}

function describeToolRiskLevel(value: string) {
  if (value === "safe_read") {
    return "Безопасное чтение";
  }
  if (value === "confirmation_required") {
    return "Нужно подтверждение";
  }
  return value.replaceAll("_", " ");
}

function flattenAttachments(timeline: SupportTicketDetailPayload["timeline"]) {
  return timeline.flatMap((entry, entryIndex) =>
    entry.attachments.map((attachment, attachmentIndex) => ({
      id: `${entry.event_id ?? entryIndex}-${attachmentIndex}`,
      label:
        String(
          attachment.name ??
            attachment.filename ??
            attachment.label ??
            attachment.artifact_id ??
            attachment.type ??
            "Вложение"
        ) || "Вложение",
      summary: JSON.stringify(attachment)
    }))
  );
}

function parseToolParams(
  selectedTool: SupportTicketToolsPayload["tools"][number] | null,
  selectedPresetId: string,
  toolParams: Record<string, string>
) {
  if (!selectedTool) {
    throw new Error("Выберите инструмент.");
  }

  if (selectedPresetId.trim()) {
    return {
      presetId: selectedPresetId.trim(),
      params: {}
    };
  }

  const params: Record<string, unknown> = {};
  for (const field of selectedTool.params_schema) {
    const defaultValue =
      field.default == null
        ? ""
        : typeof field.default === "object"
          ? JSON.stringify(field.default, null, 2)
          : String(field.default);
    const rawValue = toolParams[field.name] ?? defaultValue;
    const trimmedValue = rawValue.trim();

    if (!trimmedValue) {
      if (field.required) {
        throw new Error(`Заполните поле «${field.label ?? field.name}».`);
      }
      continue;
    }

    if (field.type === "boolean") {
      params[field.name] = trimmedValue === "true";
      continue;
    }
    if (field.type === "integer") {
      params[field.name] = Number.parseInt(trimmedValue, 10);
      continue;
    }
    if (field.type === "number") {
      params[field.name] = Number.parseFloat(trimmedValue);
      continue;
    }
    if (field.type === "object" || field.type === "array") {
      try {
        params[field.name] = JSON.parse(trimmedValue);
      } catch {
        throw new Error(`Поле «${field.label ?? field.name}» должно содержать валидный JSON.`);
      }
      continue;
    }
    params[field.name] = trimmedValue;
  }

  return {
    presetId: null,
    params
  };
}

export function TicketDetailPage() {
  const navigate = useNavigate();
  const { ticketId } = useParams();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<SupportQueueScope>("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [queueSearch, setQueueSearch] = useState("");
  const [activeTab, setActiveTab] = useState("dialog");
  const [messageMode, setMessageMode] = useState<"internal" | "public">("public");
  const [messageDraft, setMessageDraft] = useState("");
  const [statusAction, setStatusAction] = useState("");
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [toolParams, setToolParams] = useState<Record<string, string>>({});
  const deferredQueueSearch = useDeferredValue(queueSearch);

  const queueQuery = useQuery({
    queryKey: ["ticket-detail-queue", scope, statusFilter, deferredQueueSearch],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter,
        query: deferredQueueSearch
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS
  });

  const detailQuery = useQuery({
    queryKey: ["ticket-detail", ticketId],
    queryFn: () => fetchSupportTicketDetail(ticketId!),
    enabled: Boolean(ticketId),
    retry: false
  });

  const toolsQuery = useQuery({
    queryKey: ["ticket-tools", ticketId],
    queryFn: () => fetchSupportTicketTools(ticketId!),
    enabled: Boolean(ticketId),
    retry: false
  });

  useEffect(() => {
    setStatusAction("");
    setMessageDraft("");
  }, [ticketId]);

  useEffect(() => {
    const tools = toolsQuery.data?.tools ?? [];
    if (!tools.length) {
      setSelectedToolName(null);
      setSelectedPresetId("");
      setToolParams({});
      return;
    }

    if (!selectedToolName || !tools.some((tool) => tool.tool_name === selectedToolName)) {
      setSelectedToolName(tools[0].tool_name);
      setSelectedPresetId("");
      setToolParams({});
    }
  }, [selectedToolName, toolsQuery.data?.tools]);

  useEffect(() => {
    if (!ticketId) {
      return;
    }

    const realtimeClient = getSharedWebRealtimeClient();
    return realtimeClient.subscribeTicket(ticketId, () => {
      void queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] });
    });
  }, [queryClient, ticketId]);

  const sendMessageMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      return postSupportTicketMessage(ticketId, messageDraft.trim(), messageMode);
    },
    onSuccess: async () => {
      setMessageDraft("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] })
      ]);
    }
  });

  const statusMutation = useMutation({
    mutationFn: async (nextStatus: string) => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      return postSupportTicketStatus(ticketId, nextStatus);
    },
    onSuccess: async () => {
      setStatusAction("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] })
      ]);
    }
  });

  const toolMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const selectedTool =
        toolsQuery.data?.tools.find((tool) => tool.tool_name === selectedToolName) ?? null;
      const parsed = parseToolParams(selectedTool, selectedPresetId, toolParams);
      return postSupportTicketToolRun(ticketId, {
        toolName: selectedTool!.tool_name,
        presetId: parsed.presetId,
        params: parsed.params
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] })
      ]);
    }
  });

  if (!ticketId) {
    return <Navigate replace to="/app/tickets" />;
  }

  const queue = queueQuery.data;
  const detail = detailQuery.data;
  const attachments = detail ? flattenAttachments(detail.timeline) : [];
  const historyItems = detail?.timeline.filter((entry) => entry.event_type !== "chat_message") ?? [];
  const selectedTool = toolsQuery.data?.tools.find((tool) => tool.tool_name === selectedToolName) ?? null;
  const statusCounts = queue?.summary.status_counts ?? [];
  const scopeCounts = queue?.summary.scope_counts ?? [];
  const canSendInternal = detail?.actions.can_send_internal_note ?? false;

  const tabItems = [
    { value: "dialog", label: "Диалог", count: detail?.timeline.length ?? 0 },
    { value: "info", label: "Информация" },
    { value: "files", label: "Файлы", count: attachments.length },
    { value: "history", label: "История", count: historyItems.length }
  ];

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate("/app/tickets")}
              size="sm"
              variant="outline"
            >
              Назад
            </Button>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">
                Тикет #{detail?.ticket.ticket_code ?? ticketId}
              </h1>
              <button
                className="rounded-full border border-border p-2 text-slate-400 transition-colors hover:text-brand-700"
                onClick={async () => {
                  await navigator.clipboard.writeText(detail?.ticket.ticket_code ?? ticketId);
                }}
                type="button"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div>
            <p className="text-2xl font-semibold tracking-tight text-slate-950">
              {detail?.ticket.title ?? "Загружаем карточку тикета..."}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Создан: {formatDateTime(detail?.ticket.created_at)}
              {detail?.ticket.requester_display_name ? ` • Клиент: ${detail.ticket.requester_display_name}` : ""}
              {detail?.ticket.queue.code ? ` • Очередь: ${detail.ticket.queue.code}` : ""}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={getStatusTone(detail?.ticket.status ?? "")} withDot>
            {detail?.ticket.status_label ?? "Загружаем"}
          </Badge>
          <Select
            className="min-w-[230px]"
            disabled={!detail || statusMutation.isPending}
            onChange={(event) => {
              const value = event.target.value;
              setStatusAction(value);
              if (!value) {
                return;
              }
              void statusMutation.mutateAsync(value);
            }}
            value={statusAction}
          >
            <option value="">Быстрое действие по статусу</option>
            {(detail?.actions.status_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Button
            disabled={detailQuery.isFetching || toolsQuery.isFetching}
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => {
              void Promise.all([detailQuery.refetch(), queueQuery.refetch(), toolsQuery.refetch()]);
            }}
            size="sm"
            variant="outline"
          >
            Обновить
          </Button>
        </div>
      </div>

      {detailQuery.isError ? (
        <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
          {detailQuery.error instanceof Error ? detailQuery.error.message : "Не удалось открыть карточку тикета."}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Очередь</CardTitle>
            <CardDescription>
              Отдельное рабочее окно со статусами, моими тикетами и быстрым поиском по реальной очереди.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-2">
              {scopeCounts.map((item) => (
                <button
                  key={item.value}
                  className={`rounded-pill px-3 py-2 text-sm font-medium transition-colors ${
                    scope === item.value
                      ? "bg-brand-600 text-white"
                      : "bg-surface-subtle text-slate-600 hover:bg-brand-50 hover:text-brand-800"
                  }`}
                  onClick={() => {
                    startTransition(() => {
                      setScope(item.value as SupportQueueScope);
                    });
                  }}
                  type="button"
                >
                  {item.label} ({item.count})
                </button>
              ))}
            </div>

            <SearchField
              onChange={(event) => setQueueSearch(event.target.value)}
              placeholder="Код, тема, инициатор"
              value={queueSearch}
            />

            <div className="space-y-2">
              {statusCounts.map((item) => (
                <button
                  key={item.value}
                  className={`flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors ${
                    statusFilter === item.value
                      ? "border-brand-200 bg-brand-50 text-brand-900"
                      : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white"
                  }`}
                  onClick={() => {
                    startTransition(() => {
                      setStatusFilter(item.value);
                    });
                  }}
                  type="button"
                >
                  <span className="font-medium">{item.label}</span>
                  <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-soft">
                    {item.count}
                  </span>
                </button>
              ))}
            </div>

            {queueQuery.isLoading ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                Загружаем очередь...
              </div>
            ) : null}

            {queue && queue.tickets.length === 0 ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                По текущим фильтрам тикеты не найдены.
              </div>
            ) : null}

            {queue?.tickets.map((queueTicket) => {
              const active = queueTicket.ticket_id === ticketId;

              return (
                <button
                  key={queueTicket.ticket_id}
                  className={`w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors ${
                    active
                      ? "border-brand-200 bg-brand-50"
                      : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                  }`}
                  onClick={() => navigate(`/app/tickets/${queueTicket.ticket_id}`)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">
                        {queueTicket.ticket_code ?? queueTicket.ticket_id}
                      </p>
                      <p className="mt-2 text-base font-semibold text-slate-950">{queueTicket.title}</p>
                    </div>
                    <Badge tone={getStatusTone(queueTicket.status)}>{queueTicket.status_label}</Badge>
                  </div>
                  <p className="mt-3 text-sm text-slate-500">
                    {queueTicket.requester_display_name ?? "Инициатор не указан"}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    {formatDateTime(queueTicket.updated_at ?? queueTicket.created_at)}
                    {queueTicket.unread_user_messages > 0 ? ` • ${queueTicket.unread_user_messages} непрочит.` : ""}
                  </p>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardContent className="px-0 pb-0 pt-0">
              <div className="border-b border-border px-6 py-5">
                <Tabs items={tabItems} onValueChange={setActiveTab} value={activeTab} />
              </div>

              <div className="space-y-4 px-6 py-6">
                {detailQuery.isLoading ? (
                  <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                    Загружаем карточку тикета...
                  </div>
                ) : null}

                {detail && activeTab === "dialog"
                  ? detail.timeline.map((entry, entryIndex) => (
                      <div
                        key={`${entry.event_id ?? entry.message_id ?? entry.ts ?? entryIndex}`}
                        className={`rounded-[1.3rem] border px-5 py-5 shadow-soft ${
                          entry.from_role === "support" || entry.from_role === "agent"
                            ? "border-blue-100 bg-blue-50/60"
                            : entry.visibility === "internal"
                              ? "border-amber-100 bg-amber-50/70"
                              : "border-border bg-white"
                        }`}
                      >
                        <div className="flex items-start gap-4">
                          <Avatar
                            name={entry.sender_display_name ?? getRoleLabel(entry)}
                            tone={getRoleTone(entry)}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-slate-950">
                                {entry.sender_display_name ?? getRoleLabel(entry)}
                              </p>
                              <span className="text-sm text-slate-400">{formatDateTime(entry.ts)}</span>
                              <Badge className="ml-auto" tone={getRoleBadgeTone(entry)}>
                                {getRoleLabel(entry)}
                              </Badge>
                            </div>

                            {entry.reply_to?.preview ? (
                              <div className="mt-3 rounded-panel border border-border bg-white/70 px-4 py-3 text-sm text-slate-500">
                                <p className="font-medium text-slate-700">
                                  {entry.reply_to.sender_display_name ?? entry.reply_to.sender_role ?? "Сообщение"}
                                </p>
                                <p className="mt-1 line-clamp-2">{entry.reply_to.preview}</p>
                              </div>
                            ) : null}

                            <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-slate-700">
                              {entry.text}
                            </p>

                            {entry.result_summary ? (
                              <div className="mt-3 rounded-panel border border-border bg-white/80 px-4 py-3 text-sm text-slate-600">
                                <p className="font-medium text-slate-800">Результат</p>
                                <p className="mt-1">{entry.result_summary}</p>
                                {entry.result_preview ? (
                                  <pre className="mt-3 overflow-x-auto rounded-panel bg-slate-950 px-4 py-3 text-xs text-slate-100">
                                    {entry.result_preview}
                                  </pre>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ))
                  : null}

                {detail && activeTab === "info" ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <Card className="border-dashed shadow-none">
                      <CardHeader>
                        <CardTitle>Контекст обращения</CardTitle>
                        <CardDescription>
                          Реальные поля тикета и текущего observer-среза из typed detail boundary.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4 text-sm">
                        <div>
                          <p className="text-slate-500">Описание</p>
                          <p className="mt-1 whitespace-pre-line text-slate-800">
                            {detail.ticket.description ?? "Описание не заполнено."}
                          </p>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="rounded-panel bg-white px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Очередь</p>
                            <p className="mt-2 font-semibold text-slate-950">
                              {detail.ticket.queue.name ?? detail.ticket.queue.code ?? "Не указана"}
                            </p>
                          </div>
                          <div className="rounded-panel bg-white px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Устройство</p>
                            <p className="mt-2 font-semibold text-slate-950">
                              {detail.snapshot.device.hostname ?? detail.snapshot.device.device_id ?? "Нет привязки"}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-dashed shadow-none">
                      <CardHeader>
                        <CardTitle>Observer</CardTitle>
                        <CardDescription>Тот же ticket observer summary, который уже отдаёт backend.</CardDescription>
                      </CardHeader>
                      <CardContent className="grid gap-3 text-sm md:grid-cols-2">
                        <div className="rounded-panel bg-white px-4 py-4">
                          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Root trace</p>
                          <p className="mt-2 break-all font-semibold text-slate-950">
                            {detail.observer.summary.root_trace_id ?? "Нет trace"}
                          </p>
                        </div>
                        <div className="rounded-panel bg-white px-4 py-4">
                          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Трасс / ошибок</p>
                          <p className="mt-2 font-semibold text-slate-950">
                            {detail.observer.summary.trace_count} / {detail.observer.summary.error_trace_count}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                ) : null}

                {detail && activeTab === "files" ? (
                  <div className="space-y-3">
                    {attachments.length ? (
                      attachments.map((attachment) => (
                        <div
                          key={attachment.id}
                          className="flex items-center justify-between rounded-[1.1rem] border border-border bg-white px-4 py-4"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                              <Paperclip className="h-4 w-4" />
                            </div>
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-slate-900">{attachment.label}</p>
                              <p className="truncate text-sm text-slate-500">{attachment.summary}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                        В реальной ленте пока нет вложений или артефактов.
                      </div>
                    )}
                  </div>
                ) : null}

                {detail && activeTab === "history" ? (
                  <div className="space-y-3">
                    {historyItems.length ? (
                      historyItems.map((entry) => (
                        <div key={`${entry.event_id ?? entry.ts ?? entry.text}`} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-950">{getRoleLabel(entry)}</p>
                            <span className="text-sm text-slate-400">{formatDateTime(entry.ts)}</span>
                          </div>
                          <p className="mt-2 text-sm text-slate-600">{entry.text}</p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                        Отдельных событий истории пока нет.
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {activeTab === "dialog" ? (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex gap-6 border-b border-border pb-3">
                  <button
                    className={`text-sm font-semibold ${messageMode === "public" ? "text-brand-700" : "text-slate-500"}`}
                    onClick={() => setMessageMode("public")}
                    type="button"
                  >
                    Ответить
                  </button>
                  {canSendInternal ? (
                    <button
                      className={`text-sm font-semibold ${messageMode === "internal" ? "text-brand-700" : "text-slate-500"}`}
                      onClick={() => setMessageMode("internal")}
                      type="button"
                    >
                      Внутренний комментарий
                    </button>
                  ) : null}
                </div>

                <textarea
                  aria-label="Ответ оператору"
                  className="field-base min-h-[140px] w-full resize-none px-4 py-4 text-sm text-slate-800"
                  onChange={(event) => setMessageDraft(event.target.value)}
                  placeholder={
                    messageMode === "public"
                      ? "Напишите сообщение пользователю..."
                      : "Добавьте внутренний комментарий для команды..."
                  }
                  value={messageDraft}
                />

                {sendMessageMutation.isError ? (
                  <p className="text-sm text-rose-700">
                    {sendMessageMutation.error instanceof Error
                      ? sendMessageMutation.error.message
                      : "Не удалось отправить сообщение."}
                  </p>
                ) : null}

                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-slate-500">
                    Последнее событие: {formatDateTime(detail?.snapshot.last_event_id ? detail.timeline[0]?.ts : null)}
                  </p>
                  <Button
                    disabled={!messageDraft.trim() || sendMessageMutation.isPending}
                    onClick={() => {
                      void sendMessageMutation.mutateAsync();
                    }}
                  >
                    {sendMessageMutation.isPending ? "Отправляем..." : "Отправить"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Информация о тикете</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">ID</span>
                <span className="font-medium text-slate-900">{detail?.ticket.ticket_code ?? ticketId}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Статус</span>
                <Badge tone={getStatusTone(detail?.ticket.status ?? "")}>
                  {detail?.ticket.status_label ?? "Загружаем"}
                </Badge>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Создан</span>
                <span className="font-medium text-slate-900">{formatDateTime(detail?.ticket.created_at)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Обновлён</span>
                <span className="font-medium text-slate-900">{formatDateTime(detail?.ticket.updated_at)}</span>
              </div>
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Инициатор</p>
                <p className="mt-2 font-semibold text-slate-950">
                  {detail?.ticket.requester_display_name ?? "Не указан"}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Устройство и присутствие</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="font-semibold text-slate-950">
                  {detail?.snapshot.device.hostname ?? detail?.snapshot.device.device_id ?? "Нет привязки"}
                </p>
                <p className="mt-1 text-slate-500">{detail?.snapshot.device.os ?? "ОС не определена"}</p>
                <p className="mt-2 text-slate-500">
                  Агент: {detail?.snapshot.device.agent_version ?? "нет данных"} •{" "}
                  {detail?.snapshot.device.online ? "онлайн" : "офлайн"}
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Пользователь</span>
                  <span className="font-medium text-slate-900">
                    {describePresence(detail?.snapshot.presence.requester_online ?? false)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Поддержка</span>
                  <span className="font-medium text-slate-900">
                    {describePresence(detail?.snapshot.presence.support_online ?? false)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Агент</span>
                  <span className="font-medium text-slate-900">
                    {describePresence(detail?.snapshot.presence.agent_online ?? false)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Инструменты</CardTitle>
              <CardDescription>Функционал остаётся реальным: список инструментов и запуск идут через typed API.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {toolsQuery.isLoading ? (
                <p className="text-sm text-slate-500">Загружаем инструменты...</p>
              ) : null}

              {toolsQuery.isError ? (
                <p className="text-sm text-rose-700">
                  {toolsQuery.error instanceof Error
                    ? toolsQuery.error.message
                    : "Не удалось загрузить инструменты."}
                </p>
              ) : null}

              {selectedTool ? (
                <>
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Инструмент</span>
                    <Select
                      onChange={(event) => {
                        setSelectedToolName(event.target.value);
                        setSelectedPresetId("");
                        setToolParams({});
                      }}
                      value={selectedToolName ?? ""}
                    >
                      {(toolsQuery.data?.tools ?? []).map((tool) => (
                        <option key={tool.tool_name} value={tool.tool_name}>
                          {tool.tool_name}
                        </option>
                      ))}
                    </Select>
                  </label>

                  <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm text-slate-600">
                    <p className="font-semibold text-slate-900">{selectedTool.description ?? selectedTool.tool_name}</p>
                    <p className="mt-2">
                      Риск: {describeToolRiskLevel(selectedTool.risk_level)}
                      {selectedTool.requires_consent ? " • нужно подтверждение" : ""}
                      {selectedTool.install_required ? " • требуется установка" : ""}
                    </p>
                  </div>

                  {selectedTool.presets.length ? (
                    <label className="space-y-2 text-sm font-medium text-slate-800">
                      <span>Preset</span>
                      <Select onChange={(event) => setSelectedPresetId(event.target.value)} value={selectedPresetId}>
                        <option value="">Без preset</option>
                        {selectedTool.presets.map((preset) => (
                          <option key={preset.preset_id} value={preset.preset_id}>
                            {preset.label}
                          </option>
                        ))}
                      </Select>
                    </label>
                  ) : null}

                  {selectedPresetId ? null : selectedTool.params_schema.map((field) => {
                    const defaultValue =
                      field.default == null
                        ? ""
                        : typeof field.default === "object"
                          ? JSON.stringify(field.default, null, 2)
                          : String(field.default);
                    const value = toolParams[field.name] ?? defaultValue;
                    const multiline = field.type === "object" || field.type === "array" || field.type === "textarea";

                    return (
                      <label key={field.name} className="space-y-2 text-sm font-medium text-slate-800">
                        <span>
                          {field.label ?? field.name}
                          {field.required ? " *" : ""}
                        </span>
                        {multiline ? (
                          <textarea
                            className="field-base min-h-[110px] w-full resize-y px-4 py-4 text-sm"
                            onChange={(event) =>
                              setToolParams((current) => ({
                                ...current,
                                [field.name]: event.target.value
                              }))
                            }
                            value={value}
                          />
                        ) : field.type === "boolean" ? (
                          <Select
                            onChange={(event) =>
                              setToolParams((current) => ({
                                ...current,
                                [field.name]: event.target.value
                              }))
                            }
                            value={value || "false"}
                          >
                            <option value="false">false</option>
                            <option value="true">true</option>
                          </Select>
                        ) : (
                          <input
                            className="field-base h-11 w-full px-4 text-sm text-slate-900"
                            onChange={(event) =>
                              setToolParams((current) => ({
                                ...current,
                                [field.name]: event.target.value
                              }))
                            }
                            value={value}
                          />
                        )}
                        {field.description ? <p className="text-xs text-slate-500">{field.description}</p> : null}
                      </label>
                    );
                  })}

                  {toolMutation.isSuccess ? (
                    <p className="text-sm text-emerald-700">{toolMutation.data.message}</p>
                  ) : null}

                  {toolMutation.isError ? (
                    <p className="text-sm text-rose-700">
                      {toolMutation.error instanceof Error
                        ? toolMutation.error.message
                        : "Не удалось запустить инструмент."}
                    </p>
                  ) : null}

                  <Button
                    className="w-full"
                    disabled={toolMutation.isPending}
                    leadingIcon={<Wrench className="h-4 w-4" />}
                    onClick={() => {
                      void toolMutation.mutateAsync();
                    }}
                  >
                    {toolMutation.isPending ? "Запускаем..." : "Запустить инструмент"}
                  </Button>
                </>
              ) : (
                <p className="text-sm text-slate-500">Для этого тикета пока нет доступных инструментов.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Последние операции</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {detail?.snapshot.latest_operations.length ? (
                detail.snapshot.latest_operations.map((operation) => (
                  <div key={operation.operation_id} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-950">
                          {operation.tool_name ?? operation.command_name ?? operation.kind}
                        </p>
                        <p className="mt-1 text-slate-500">{operation.status}</p>
                      </div>
                      <Badge tone={getStatusTone(operation.status)}>{operation.status}</Badge>
                    </div>
                    <p className="mt-2 text-slate-500">
                      {operation.result_summary ?? operation.error_message ?? "Без краткого результата"}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">Свежих операций по тикету пока нет.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
