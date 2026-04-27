import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Clock3,
  Copy,
  FileImage,
  FileText,
  Film,
  History,
  ListFilter,
  Paperclip,
  RefreshCcw,
  Wrench,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Avatar } from "../../components/ui/avatar";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SchemaParamEditor } from "../../components/forms/schema-param-editor";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import {
  fetchSupportQueue,
  fetchSupportTicketPassport,
  fetchSupportTicketDetail,
  fetchSupportTicketTools,
  generateSupportTicketPassport,
  createSupportTicketKnowledgeDraft,
  postSupportTicketMessage,
  postSupportTicketStatus,
  postSupportTicketToolRun,
  type SupportQueueScope,
  type SupportTicketPassportPayload,
  type SupportTicketDetailPayload,
  type SupportTicketToolsPayload,
} from "../../features/queues/api";
import { supportToolParamFields, validateSupportToolParams } from "../../features/queues/tool-param-fields";
import { getSharedWebRealtimeClient } from "../../shared/realtime/client";
import { cn } from "../../shared/ui/cn";

const SUPPORT_QUEUE_REFRESH_MS = 15_000;

type NormalizedAttachment = {
  id: string;
  artifactId: string | null;
  label: string;
  summary: string;
  kind: string | null;
  mimeType: string | null;
  mediaType: "image" | "video" | "file";
  downloadUrl: string | null;
  sourceLabel: string;
  sourceTimestamp: string | null;
};

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
    minute: "2-digit",
  }).format(date);
}

function getStatusTone(status: string) {
  switch (status) {
    case "accepted":
    case "queued":
    case "assigned":
    case "sent":
    case "running":
    case "new":
    case "triaged":
      return "brand" as const;
    case "in_progress":
    case "scheduled":
      return "success" as const;
    case "waiting_on_user":
    case "waiting_on_internal_team":
    case "waiting_on_vendor":
    case "waiting_on_approval":
      return "warning" as const;
    case "success":
    case "succeeded":
    case "resolved":
    case "closed":
      return "success" as const;
    case "failed":
    case "timed_out":
    case "canceled":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function formatNextActionOwner(owner: string | null | undefined) {
  switch (owner) {
    case "support":
      return "Поддержка";
    case "requester":
      return "Пользователь";
    case "internal_team":
      return "Внутренняя группа";
    case "vendor":
      return "Внешняя сторона";
    case "approver":
      return "Согласующий";
    case "system":
      return "Система";
    default:
      return owner || "Не указан";
  }
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

function buildArtifactUrl(ticketId: string, attachment: Record<string, unknown>): string | null {
  const artifactId = String(attachment.artifact_id ?? attachment.id ?? "").trim();
  const rawUrl = String(attachment.url ?? "").trim();

  if (artifactId) {
    return `/api/artifacts/${encodeURIComponent(artifactId)}/download?ticket_id=${encodeURIComponent(ticketId)}`;
  }

  if (!rawUrl) {
    return null;
  }

  if (rawUrl.includes("ticket_id=")) {
    return rawUrl;
  }

  const separator = rawUrl.includes("?") ? "&" : "?";
  return `${rawUrl}${separator}ticket_id=${encodeURIComponent(ticketId)}`;
}

function getAttachmentMediaType(attachment: Record<string, unknown>): "image" | "video" | "file" {
  const mimeType = String(attachment.mime_type ?? attachment.mime ?? "").toLowerCase();
  const kind = String(attachment.kind ?? "").toLowerCase();

  if (mimeType.startsWith("video/") || kind === "screen_recording") {
    return "video";
  }
  if (mimeType.startsWith("image/") || kind === "screenshot") {
    return "image";
  }
  return "file";
}

function normalizeAttachment(
  attachment: Record<string, unknown>,
  ticketId: string,
  fallbackId: string,
  sourceLabel: string,
  sourceTimestamp: string | null,
): NormalizedAttachment {
  const summaryParts = [attachment.description, attachment.mime_type, attachment.kind]
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

  return {
    id: fallbackId,
    artifactId: String(attachment.artifact_id ?? attachment.id ?? "").trim() || null,
    label:
      String(
        attachment.name ??
          attachment.filename ??
          attachment.original_name ??
          attachment.label ??
          attachment.artifact_id ??
          "Вложение",
      ).trim() || "Вложение",
    summary: summaryParts.join(" • ") || "Артефакт из ленты тикета",
    kind: String(attachment.kind ?? "").trim() || null,
    mimeType: String(attachment.mime_type ?? attachment.mime ?? "").trim() || null,
    mediaType: getAttachmentMediaType(attachment),
    downloadUrl: buildArtifactUrl(ticketId, attachment),
    sourceLabel,
    sourceTimestamp,
  };
}

function flattenAttachments(ticketId: string, timeline: SupportTicketDetailPayload["timeline"]) {
  return timeline.flatMap((entry, entryIndex) =>
    entry.attachments.map((attachment, attachmentIndex) =>
      normalizeAttachment(
        attachment,
        ticketId,
        `${entry.event_id ?? entry.message_id ?? entryIndex}-${attachmentIndex}`,
        entry.sender_display_name ?? getRoleLabel(entry),
        entry.ts,
      ),
    ),
  );
}

function getOperationTitle(operation: SupportTicketDetailPayload["snapshot"]["latest_operations"][number]) {
  return operation.tool_name ?? operation.command_name ?? operation.kind;
}

function ArtifactPreview({ attachment }: { attachment: NormalizedAttachment }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(attachment.mediaType !== "file");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!attachment.downloadUrl || attachment.mediaType === "file") {
      setLoading(false);
      return;
    }

    let active = true;
    let localUrl: string | null = null;

    setLoading(true);
    setError(null);

    void fetch(attachment.downloadUrl, { credentials: "same-origin" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Не удалось загрузить артефакт");
        }
        return response.blob();
      })
      .then((blob) => {
        if (!active) {
          return;
        }
        localUrl = URL.createObjectURL(blob);
        setObjectUrl(localUrl);
      })
      .catch((loadError) => {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Ошибка загрузки");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
      if (localUrl) {
        URL.revokeObjectURL(localUrl);
      }
    };
  }, [attachment.downloadUrl, attachment.mediaType]);

  return (
    <div className="space-y-3 rounded-[1rem] border border-border bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-950">{attachment.label}</p>
          <p className="mt-1 text-xs text-slate-500">{attachment.summary}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
          {attachment.mediaType === "image" ? (
            <FileImage className="h-4 w-4" />
          ) : attachment.mediaType === "video" ? (
            <Film className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>
      </div>

      {loading ? (
        <div className="rounded-panel border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
          Загружаем предпросмотр...
        </div>
      ) : null}

      {!loading && error ? (
        <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {!loading && !error && attachment.mediaType === "image" && objectUrl ? (
        <img
          alt={attachment.label}
          className="max-h-[22rem] w-full rounded-panel border border-border object-contain"
          loading="lazy"
          src={objectUrl}
        />
      ) : null}

      {!loading && !error && attachment.mediaType === "video" && objectUrl ? (
        <video
          className="max-h-[22rem] w-full rounded-panel border border-border"
          controls
          preload="metadata"
          src={objectUrl}
        />
      ) : null}

      {attachment.mediaType === "file" && attachment.downloadUrl ? (
        <a
          className="inline-flex items-center gap-2 rounded-pill border border-border px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
          href={attachment.downloadUrl}
          rel="noreferrer"
          target="_blank"
        >
          <Paperclip className="h-4 w-4" />
          Скачать файл
        </a>
      ) : null}

      <p className="text-xs text-slate-400">
        {attachment.sourceLabel} • {formatDateTime(attachment.sourceTimestamp)}
      </p>
    </div>
  );
}

function parseToolParams(
  selectedTool: SupportTicketToolsPayload["tools"][number] | null,
  selectedPresetId: string,
  toolParams: Record<string, unknown>,
) {
  return validateSupportToolParams(selectedTool, selectedPresetId, toolParams);
}

export function TicketRequestFormCard({
  requestForm,
}: {
  requestForm: SupportTicketDetailPayload["request_form"];
}) {
  if (!requestForm) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Данные формы</CardTitle>
        <CardDescription>{requestForm.form_title ?? requestForm.form_key ?? "структурированный ввод"}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">request_kind</p>
            <p className="mt-2 font-semibold text-slate-950">{requestForm.request_kind ?? "не указан"}</p>
          </div>
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Форма</p>
            <p className="mt-2 font-semibold text-slate-950">{requestForm.form_key ?? "не указана"}</p>
          </div>
        </div>

        {requestForm.rows.length > 0 ? (
          <dl className="space-y-3">
            {requestForm.rows.map((row) => (
              <div
                className="flex items-start justify-between gap-3 rounded-[1rem] border border-slate-200/80 px-4 py-3"
                key={`${row.key}-${row.label}`}
              >
                <dt className="text-slate-500">{row.label}</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">{row.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-slate-500">Структурированные ответы пока не заполнены.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function TicketWorkVisibilityCard({
  ticket,
}: {
  ticket: Pick<
    SupportTicketDetailPayload["ticket"],
    | "status"
    | "status_label"
    | "requester_status_label"
    | "next_action_owner"
    | "next_action_due_at"
    | "status_reason"
    | "resolution_code"
    | "resolution_summary"
    | "requester_resolution_summary"
    | "evidence_required"
    | "evidence_ref"
  >;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ход работы</CardTitle>
        <CardDescription>Внутреннее состояние, пользовательский статус и следующий ответственный.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Внутренний статус</span>
          <Badge tone={getStatusTone(ticket.status)}>{ticket.status_label}</Badge>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Статус для пользователя</span>
          <span className="font-medium text-slate-900">{ticket.requester_status_label || "Не указан"}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Чей ход</span>
          <span className="font-medium text-slate-900">{formatNextActionOwner(ticket.next_action_owner)}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500">Следующий срок</span>
          <span className="font-medium text-slate-900">{formatDateTime(ticket.next_action_due_at)}</span>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Причина ожидания</p>
          <p className="mt-2 font-semibold text-slate-950">{ticket.status_reason || "Не указана"}</p>
        </div>
        {ticket.resolution_code ||
        ticket.resolution_summary ||
        ticket.requester_resolution_summary ||
        ticket.evidence_required ||
        ticket.evidence_ref ? (
          <div className="rounded-[1.1rem] border border-border px-4 py-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Решение и подтверждение</p>
            <dl className="mt-3 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Код решения</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.resolution_code || "Не указан"}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Для пользователя</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.requester_resolution_summary || ticket.resolution_summary || "Не заполнено"}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-slate-500">Доказательство</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">
                  {ticket.evidence_ref || (ticket.evidence_required ? "Требуется" : "Не требуется")}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export const PASSPORT_SECTION_LABELS: Array<[string, string]> = [
  ["requester", "Кто и откуда обратился"],
  ["problem", "Что произошло"],
  ["affected_object", "Какой объект затронут"],
  ["automated_checks", "Что проверили автоматически"],
  ["operator_checks", "Что проверил оператор"],
  ["changes_made", "Что изменили"],
  ["approvals", "Кто согласовал"],
  ["evidence", "Чем подтверждено решение"],
  ["user_result", "Итог для пользователя"],
  ["internal_result", "Внутренний тех. итог"],
  ["repeat_guidance", "Что делать при повторе"],
];

export function TicketPassportPanel({
  isCreatingKnowledgeDraft = false,
  isGenerating,
  knowledgeDraftMessage = null,
  onGenerate,
  onKnowledgeDraft,
  onPrint,
  onRefresh,
  payload,
}: {
  isCreatingKnowledgeDraft?: boolean;
  isGenerating: boolean;
  knowledgeDraftMessage?: string | null;
  onGenerate: () => void;
  onKnowledgeDraft: () => void;
  onPrint: () => void;
  onRefresh: () => void;
  payload?: SupportTicketPassportPayload;
}) {
  if (!payload || !payload.passport) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center">
        <p className="font-semibold text-slate-950">Паспорт решения ещё не собран</p>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">
          Система соберёт черновик из полей заявки, истории, операций, доказательств и итогов решения.
        </p>
        <Button className="mt-5" disabled={isGenerating} onClick={onGenerate}>
          {isGenerating ? "Собираем..." : "Собрать паспорт"}
        </Button>
      </div>
    );
  }

  const passport = payload.passport;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-[1.1rem] border border-border bg-white px-5 py-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-700">Паспорт решения</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">Версия {passport.version}</h2>
          <p className="mt-1 text-sm text-slate-500">
            Собран {formatDateTime(passport.generated_at)} • источник: {passport.summary_source}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={isGenerating} onClick={onRefresh} size="sm" variant="outline">
            Обновить по последним действиям
          </Button>
          <Button onClick={onPrint} size="sm" variant="outline">
            Печать / PDF
          </Button>
          <Button disabled={isCreatingKnowledgeDraft} onClick={onKnowledgeDraft} size="sm" variant="outline">
            {isCreatingKnowledgeDraft ? "Готовим черновик..." : "Сохранить как черновик знания"}
          </Button>
        </div>
      </div>

      {knowledgeDraftMessage ? (
        <div className="rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          {knowledgeDraftMessage}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {PASSPORT_SECTION_LABELS.map(([key, label]) => (
          <div key={key} className="rounded-[1.1rem] border border-border bg-white px-5 py-5">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</p>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
              {passport.sections[key] || "Нет данных"}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Доказательства</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.evidence.length}</p>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Действия</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.actions.length}</p>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Согласования</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.approvals.length}</p>
        </div>
      </div>
    </div>
  );
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
  const [toolParams, setToolParams] = useState<Record<string, unknown>>({});
  const [toolSearch, setToolSearch] = useState("");
  const [knowledgeDraftMessage, setKnowledgeDraftMessage] = useState<string | null>(null);
  const deferredQueueSearch = useDeferredValue(queueSearch);
  const deferredToolSearch = useDeferredValue(toolSearch);

  const queueQuery = useQuery({
    queryKey: ["ticket-detail-queue", scope, statusFilter, deferredQueueSearch],
    queryFn: () =>
      fetchSupportQueue({
        scope,
        statusFilter,
        query: deferredQueueSearch,
      }),
    retry: false,
    refetchInterval: SUPPORT_QUEUE_REFRESH_MS,
  });

  const detailQuery = useQuery({
    queryKey: ["ticket-detail", ticketId],
    queryFn: () => fetchSupportTicketDetail(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });

  const toolsQuery = useQuery({
    queryKey: ["ticket-tools", ticketId],
    queryFn: () => fetchSupportTicketTools(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });

  const passportQuery = useQuery({
    queryKey: ["ticket-passport", ticketId],
    queryFn: () => fetchSupportTicketPassport(ticketId!),
    enabled: Boolean(ticketId),
    retry: false,
  });

  useEffect(() => {
    setStatusAction("");
    setMessageDraft("");
    setKnowledgeDraftMessage(null);
  }, [ticketId]);

  const toolList = toolsQuery.data?.tools ?? [];
  const visibleTools = useMemo(() => {
    const normalized = deferredToolSearch.trim().toLowerCase();
    if (!normalized) {
      return toolList;
    }
    return toolList.filter((tool) =>
      [
        tool.tool_name,
        tool.module_name ?? "",
        tool.description ?? "",
        tool.source,
        tool.risk_level,
      ].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [deferredToolSearch, toolList]);

  useEffect(() => {
    if (!visibleTools.length) {
      setSelectedToolName(null);
      setSelectedPresetId("");
      setToolParams({});
      return;
    }

    if (!selectedToolName || !visibleTools.some((tool) => tool.tool_name === selectedToolName)) {
      setSelectedToolName(visibleTools[0].tool_name);
      setSelectedPresetId("");
      setToolParams({});
    }
  }, [selectedToolName, visibleTools]);

  useEffect(() => {
    if (!ticketId) {
      return;
    }

    const realtimeClient = getSharedWebRealtimeClient();
    return realtimeClient.subscribeTicket(ticketId, () => {
      void queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] });
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
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] }),
      ]);
    },
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
        queryClient.invalidateQueries({ queryKey: ["ticket-detail-queue"] }),
      ]);
    },
  });

  const toolMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      const selectedTool = toolList.find((tool) => tool.tool_name === selectedToolName) ?? null;
      const parsed = parseToolParams(selectedTool, selectedPresetId, toolParams);
      return postSupportTicketToolRun(ticketId, {
        toolName: selectedTool!.tool_name,
        presetId: parsed.presetId,
        params: parsed.params,
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-tools", ticketId] }),
      ]);
    },
  });

  const passportGenerateMutation = useMutation({
    mutationFn: async (mode: "create" | "refresh") => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      return generateSupportTicketPassport(ticketId, mode);
    },
    onSuccess: async () => {
      setKnowledgeDraftMessage(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
        queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      ]);
    },
  });

  const knowledgeDraftMutation = useMutation({
    mutationFn: async () => {
      if (!ticketId) {
        throw new Error("Карточка тикета не выбрана.");
      }
      return createSupportTicketKnowledgeDraft(ticketId);
    },
    onSuccess: (draft) => {
      setKnowledgeDraftMessage(`Черновик знания подготовлен: ${draft.title}`);
    },
  });

  if (!ticketId) {
    return <Navigate replace to="/app/tickets" />;
  }

  const queue = queueQuery.data;
  const detail = detailQuery.data;
  const passport = passportQuery.data;
  const attachments = detail ? flattenAttachments(ticketId, detail.timeline) : [];
  const historyItems = detail?.timeline.filter((entry) => entry.event_type !== "chat_message") ?? [];
  const selectedTool = toolList.find((tool) => tool.tool_name === selectedToolName) ?? null;
  const canSendInternal = detail?.actions.can_send_internal_note ?? false;
  const latestOperations = detail?.snapshot.latest_operations ?? [];

  const tabItems = [
    { value: "dialog", label: "Диалог", count: detail?.timeline.length ?? 0 },
    { value: "info", label: "Информация" },
    { value: "files", label: "Файлы", count: attachments.length },
    { value: "history", label: "История", count: historyItems.length + latestOperations.length },
    { value: "passport", label: "Паспорт", count: passport?.passport ? passport.passport.version : undefined },
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
          {detail?.ticket.requester_status_label ? (
            <Badge tone={getStatusTone(detail.ticket.status)}>{detail.ticket.requester_status_label}</Badge>
          ) : null}
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
              void Promise.all([detailQuery.refetch(), queueQuery.refetch(), toolsQuery.refetch(), passportQuery.refetch()]);
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
          {detailQuery.error instanceof Error
            ? detailQuery.error.message
            : "Не удалось открыть карточку тикета."}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
        <Card className="overflow-hidden xl:sticky xl:top-[8.5rem] xl:self-start">
          <CardHeader>
            <CardTitle>Очередь</CardTitle>
            <CardDescription>
              Фиксированное рабочее окно со статусами, поиском и реальной очередью тикетов.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex h-[min(68vh,58rem)] min-h-[30rem] flex-col gap-5 overflow-hidden">
            <div className="grid grid-cols-2 gap-2">
              {(queue?.summary.scope_counts ?? []).map((item) => (
                <button
                  key={item.value}
                  className={cn(
                    "rounded-pill px-3 py-2 text-sm font-medium transition-colors",
                    scope === item.value
                      ? "bg-brand-600 text-white"
                      : "bg-surface-subtle text-slate-600 hover:bg-brand-50 hover:text-brand-800",
                  )}
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
              {(queue?.summary.status_counts ?? []).map((item) => (
                <button
                  key={item.value}
                  className={cn(
                    "flex w-full items-center justify-between rounded-panel border px-4 py-3 text-left transition-colors",
                    statusFilter === item.value
                      ? "border-brand-200 bg-brand-50 text-brand-900"
                      : "border-transparent bg-surface-subtle text-slate-700 hover:border-border hover:bg-white",
                  )}
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

            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
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
                    className={cn(
                      "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                      active
                        ? "border-brand-200 bg-brand-50"
                        : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
                    )}
                    onClick={() => navigate(`/app/tickets/${queueTicket.ticket_id}`)}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
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
                      {queueTicket.unread_user_messages > 0
                        ? ` • ${queueTicket.unread_user_messages} непрочит.`
                        : ""}
                    </p>
                    <p className="mt-2 text-xs font-medium text-slate-500">
                      Ход: {formatNextActionOwner(queueTicket.next_action_owner)}
                      {queueTicket.requester_status_label ? ` • ${queueTicket.requester_status_label}` : ""}
                    </p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardContent className="flex h-[min(72vh,62rem)] min-h-[34rem] flex-col px-0 pb-0 pt-0">
            <div className="border-b border-border px-6 py-5">
              <Tabs items={tabItems} onValueChange={setActiveTab} value={activeTab} />
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
              {detailQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                  Загружаем карточку тикета...
                </div>
              ) : null}

              {detail && activeTab === "dialog" ? (
                <div className="space-y-4">
                  {detail.timeline.map((entry, entryIndex) => {
                    const entryAttachments = entry.attachments.map((attachment, attachmentIndex) =>
                      normalizeAttachment(
                        attachment,
                        ticketId,
                        `${entry.event_id ?? entry.message_id ?? entryIndex}-${attachmentIndex}`,
                        entry.sender_display_name ?? getRoleLabel(entry),
                        entry.ts,
                      ),
                    );

                    return (
                      <div
                        key={`${entry.event_id ?? entry.message_id ?? entry.ts ?? entryIndex}`}
                        className={cn(
                          "rounded-[1.3rem] border px-5 py-5 shadow-soft",
                          entry.from_role === "support" || entry.from_role === "agent"
                            ? "border-blue-100 bg-blue-50/60"
                            : entry.visibility === "internal"
                              ? "border-amber-100 bg-amber-50/70"
                              : "border-border bg-white",
                        )}
                      >
                        <div className="flex items-start gap-4">
                          <Avatar name={entry.sender_display_name ?? getRoleLabel(entry)} tone={getRoleTone(entry)} />
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

                            {entryAttachments.length ? (
                              <div className="mt-4 grid gap-3 md:grid-cols-2">
                                {entryAttachments.map((attachment) => (
                                  <ArtifactPreview key={attachment.id} attachment={attachment} />
                                ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}

              {detail && activeTab === "info" ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <Card className="border-dashed shadow-none">
                    <CardHeader>
                      <CardTitle>Контекст обращения</CardTitle>
                      <CardDescription>
                        Реальные поля тикета, очередь, устройство и состав участников.
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
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Участники очереди</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {detail.ticket.queue_members.length ? (
                            detail.ticket.queue_members.map((member) => (
                              <Badge key={member.actor_id} tone="neutral">
                                {member.actor_id}
                                {member.role_in_queue ? ` • ${member.role_in_queue}` : ""}
                              </Badge>
                            ))
                          ) : (
                            <p className="text-sm text-slate-500">Состав очереди не передан.</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border-dashed shadow-none">
                    <CardHeader>
                      <CardTitle>Observer</CardTitle>
                      <CardDescription>
                        Тот же observer summary, который backend уже отдаёт для тикета.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 text-sm md:grid-cols-2">
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Root trace</p>
                        <p className="mt-2 break-all font-semibold text-slate-950">
                          {detail.observer.summary.root_trace_id ?? "Нет trace"}
                        </p>
                      </div>
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Трассы / ошибки</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {detail.observer.summary.trace_count} / {detail.observer.summary.error_trace_count}
                        </p>
                      </div>
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Signatures</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {detail.observer.summary.signature_count}
                        </p>
                      </div>
                      <div className="rounded-panel bg-white px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Последняя trace</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {formatDateTime(detail.observer.summary.latest_trace_at)}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : null}

              {detail && activeTab === "files" ? (
                <div className="space-y-3">
                  {attachments.length ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      {attachments.map((attachment) => (
                        <ArtifactPreview key={attachment.id} attachment={attachment} />
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                      В реальной ленте пока нет вложений или артефактов.
                    </div>
                  )}
                </div>
              ) : null}

              {detail && activeTab === "history" ? (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4 text-brand-700" />
                      <p className="text-sm font-semibold text-slate-900">Последние операции</p>
                    </div>
                    {latestOperations.length ? (
                      latestOperations.map((operation) => (
                        <div
                          key={operation.operation_id}
                          className="rounded-[1.1rem] border border-border bg-white px-4 py-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-semibold text-slate-950">{getOperationTitle(operation)}</p>
                              <p className="mt-1 text-sm text-slate-500">
                                {operation.result_summary ?? operation.error_message ?? "Без краткого результата"}
                              </p>
                            </div>
                            <Badge tone={getStatusTone(operation.status)}>{operation.status}</Badge>
                          </div>
                          <p className="mt-3 text-xs text-slate-400">
                            queued {formatDateTime(operation.queued_at)} • finished {formatDateTime(operation.finished_at)}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                        Свежих операций по тикету пока нет.
                      </div>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Clock3 className="h-4 w-4 text-brand-700" />
                      <p className="text-sm font-semibold text-slate-900">Системные события</p>
                    </div>
                    {historyItems.length ? (
                      historyItems.map((entry) => (
                        <div
                          key={`${entry.event_id ?? entry.ts ?? entry.text}`}
                          className="rounded-[1.1rem] border border-border bg-white px-4 py-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-950">{getRoleLabel(entry)}</p>
                            <span className="text-sm text-slate-400">{formatDateTime(entry.ts)}</span>
                          </div>
                          <p className="mt-2 text-sm text-slate-600">{entry.text}</p>
                          {entry.result_summary ? (
                            <p className="mt-2 text-sm text-slate-500">{entry.result_summary}</p>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                        Отдельных событий истории пока нет.
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              {activeTab === "passport" ? (
                passportQuery.isLoading ? (
                  <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                    Загружаем паспорт решения...
                  </div>
                ) : passportQuery.isError ? (
                  <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-5 text-sm text-rose-700">
                    {passportQuery.error instanceof Error
                      ? passportQuery.error.message
                      : "Не удалось загрузить паспорт решения."}
                  </div>
                ) : (
                  <TicketPassportPanel
                    isCreatingKnowledgeDraft={knowledgeDraftMutation.isPending}
                    isGenerating={passportGenerateMutation.isPending}
                    knowledgeDraftMessage={knowledgeDraftMessage}
                    onGenerate={() => passportGenerateMutation.mutate("create")}
                    onKnowledgeDraft={() => knowledgeDraftMutation.mutate()}
                    onPrint={() => navigate(`/app/tickets/${ticketId}/passport/print`)}
                    onRefresh={() => passportGenerateMutation.mutate("refresh")}
                    payload={passport}
                  />
                )
              ) : null}
            </div>

            {activeTab === "dialog" ? (
              <div className="border-t border-border bg-white px-6 py-5">
                <div className="space-y-4">
                  <div className="flex gap-6 border-b border-border pb-3">
                    <button
                      className={cn(
                        "text-sm font-semibold",
                        messageMode === "public" ? "text-brand-700" : "text-slate-500",
                      )}
                      onClick={() => setMessageMode("public")}
                      type="button"
                    >
                      Ответить
                    </button>
                    {canSendInternal ? (
                      <button
                        className={cn(
                          "text-sm font-semibold",
                          messageMode === "internal" ? "text-brand-700" : "text-slate-500",
                        )}
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
                      Последнее событие: {formatDateTime(detail?.timeline[0]?.ts)}
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
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4 xl:sticky xl:top-[8.5rem] xl:max-h-[calc(100vh-10rem)] xl:self-start xl:overflow-y-auto xl:pr-1">
          {detail ? <TicketWorkVisibilityCard ticket={detail.ticket} /> : null}

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

          {detail?.request_form ? (
            <Card>
              <CardHeader>
                <CardTitle>Данные формы</CardTitle>
                <CardDescription>
                  {detail.request_form.form_title ?? detail.request_form.form_key ?? "структурированный ввод"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">request_kind</p>
                    <p className="mt-2 font-semibold text-slate-950">
                      {detail.request_form.request_kind ?? "не указан"}
                    </p>
                  </div>
                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Форма</p>
                    <p className="mt-2 font-semibold text-slate-950">
                      {detail.request_form.form_key ?? "не указана"}
                    </p>
                  </div>
                </div>

                {detail.request_form.rows.length > 0 ? (
                  <dl className="space-y-3">
                    {detail.request_form.rows.map((row) => (
                      <div
                        className="flex items-start justify-between gap-3 rounded-[1rem] border border-slate-200/80 px-4 py-3"
                        key={`${row.key}-${row.label}`}
                      >
                        <dt className="text-slate-500">{row.label}</dt>
                        <dd className="max-w-[60%] text-right font-medium text-slate-900">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="text-slate-500">Структурированные ответы пока не заполнены.</p>
                )}
              </CardContent>
            </Card>
          ) : null}

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

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Инструменты</CardTitle>
              <CardDescription>
                Живой launcher по реальным typed API: поиск, выбор инструмента, presets и параметры.
              </CardDescription>
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

              {toolList.length ? (
                <>
                  <SearchField
                    onChange={(event) => setToolSearch(event.target.value)}
                    placeholder="Поиск по tool, module или описанию"
                    value={toolSearch}
                  />

                  <div className="space-y-2 rounded-[1.1rem] border border-border bg-surface-subtle p-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <ListFilter className="h-4 w-4 text-brand-700" />
                      Выбор инструмента
                    </div>
                    <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                      {visibleTools.length ? (
                        visibleTools.map((tool) => {
                          const active = tool.tool_name === selectedToolName;
                          return (
                            <button
                              key={tool.tool_name}
                              className={cn(
                                "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                                active
                                  ? "border-brand-200 bg-brand-50"
                                  : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
                              )}
                              onClick={() => {
                                setSelectedToolName(tool.tool_name);
                                setSelectedPresetId("");
                                setToolParams({});
                              }}
                              type="button"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="truncate font-semibold text-slate-950">{tool.tool_name}</p>
                                  <p className="mt-1 truncate text-xs text-slate-500">
                                    {tool.module_name ?? "module не указан"}
                                  </p>
                                </div>
                                <Badge tone={tool.source === "server" ? "brand" : "info"}>
                                  {tool.source}
                                </Badge>
                              </div>
                              <p className="mt-3 text-sm text-slate-600">
                                {tool.description ?? "Описание инструмента не заполнено."}
                              </p>
                            </button>
                          );
                        })
                      ) : (
                        <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-6 text-sm text-slate-500">
                          Под текущий поиск инструменты не найдены.
                        </div>
                      )}
                    </div>
                  </div>

                  {selectedTool ? (
                    <>
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm text-slate-600">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-slate-900">{selectedTool.tool_name}</p>
                          <Badge tone={selectedTool.source === "server" ? "brand" : "info"}>
                            {selectedTool.source}
                          </Badge>
                          <Badge tone={getStatusTone(selectedTool.risk_level)}>
                            {describeToolRiskLevel(selectedTool.risk_level)}
                          </Badge>
                        </div>
                        <p className="mt-3">
                          {selectedTool.description ?? "Описание инструмента не заполнено."}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">
                          {selectedTool.requires_consent ? "Требуется подтверждение • " : ""}
                          {selectedTool.install_required ? "Нужна установка на устройстве" : "Готов к запуску"}
                        </p>
                      </div>

                      {selectedTool.presets.length ? (
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Preset</span>
                          <Select
                            onChange={(event) => {
                              const value = event.target.value;
                              setSelectedPresetId(value);
                              const preset = selectedTool.presets.find((item) => item.preset_id === value);
                              setToolParams(preset?.params ? { ...preset.params } : {});
                            }}
                            value={selectedPresetId}
                          >
                            <option value="">Без preset</option>
                            {selectedTool.presets.map((preset) => (
                              <option key={preset.preset_id} value={preset.preset_id}>
                                {preset.label}
                              </option>
                            ))}
                          </Select>
                        </label>
                      ) : null}

                      {selectedPresetId ? null : (
                        <SchemaParamEditor
                          className="space-y-3"
                          fields={supportToolParamFields(selectedTool)}
                          onChange={setToolParams}
                          value={toolParams}
                        />
                      )}

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
                    <p className="text-sm text-slate-500">
                      Выберите инструмент слева, чтобы открыть presets и параметры.
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500">Для этого тикета пока нет доступных инструментов.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
