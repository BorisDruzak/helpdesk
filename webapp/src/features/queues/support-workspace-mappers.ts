import type {
  SupportQueuePayload,
  SupportTicketDetailPayload,
  SupportTicketKnowledgeSuggestionsPayload,
  SupportTicketPassportReadinessPayload,
  SupportTicketPassportPayload,
  SupportTicketPlaybooksPayload,
  SupportTicketSlaOlaPayload,
  SupportTicketSlaOlaTimerPayload,
  SupportTicketToolsPayload,
} from "./api";
import type {
  SupportWorkspaceContext,
  SupportWorkspaceKnowledge,
  SupportWorkspaceNextAction,
  SupportWorkspacePassport,
  SupportWorkspaceQueue,
  SupportWorkspaceSlice,
  SupportWorkspaceTicketItem,
  SupportWorkspaceTimelineItem,
  SupportWorkspaceTimer,
  SupportWorkspaceToolItem,
  SupportWorkspaceViewModel,
} from "./support-workspace-model";
import {
  getNextActionOwnerForStatus,
  getNextActionOwnerLabel,
  getTicketStatusPresentation,
  type TicketBadgeTone,
} from "../tickets/status-presentation";

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const DATE_TIME_WITH_YEAR_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const WORK_SLICE_ORDER = ["my_action", "sla_risk", "unassigned", "requester_reply"];

const WORK_SLICE_FALLBACK_LABELS: Record<string, string> = {
  my_action: "Нужен ответ",
  sla_risk: "SLA риск",
  unassigned: "Без исполнителя",
  requester_reply: "Ответил пользователь",
};

const QUEUE_ICON_HINTS: Array<[RegExp, SupportWorkspaceQueue["icon"]]> = [
  [/сет|network/i, "network"],
  [/сервер|server/i, "server"],
  [/орг|принтер|print/i, "printer"],
  [/систем|system/i, "monitor"],
  [/иб|security|sec/i, "shield"],
];

function formatDateTime(value: string | null | undefined, withYear = false): string {
  if (!value) {
    return "Нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return (withYear ? DATE_TIME_WITH_YEAR_FORMATTER : DATE_TIME_FORMATTER).format(date);
}

function secondsUntil(value: string | null | undefined, now = new Date()): number | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return Math.round((date.getTime() - now.getTime()) / 1000);
}

export function formatRemainingSeconds(seconds: number | null | undefined): string {
  if (seconds === null || typeof seconds === "undefined") {
    return "Нет срока";
  }
  const absSeconds = Math.abs(seconds);
  const hours = Math.floor(absSeconds / 3600);
  const minutes = Math.floor((absSeconds % 3600) / 60);
  const formatted = hours > 0 ? `${hours} ч ${minutes.toString().padStart(2, "0")} мин` : `${minutes} мин`;
  return seconds < 0 ? `Просрочено на ${formatted}` : formatted;
}

function timerStatus(seconds: number | null): SupportWorkspaceTimer["status"] {
  if (seconds === null) {
    return "unknown";
  }
  if (seconds < 0) {
    return "breached";
  }
  if (seconds <= 30 * 60) {
    return "at_risk";
  }
  return "ok";
}

function timerTone(status: SupportWorkspaceTimer["status"]): TicketBadgeTone {
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

function countFor(queue: SupportQueuePayload | undefined, value: string): number {
  return queue?.summary.smart_view_counts.find((item) => item.value === value)?.count ?? 0;
}

function queueIcon(label: string): SupportWorkspaceQueue["icon"] {
  for (const [pattern, icon] of QUEUE_ICON_HINTS) {
    if (pattern.test(label)) {
      return icon;
    }
  }
  return "layers";
}

function priorityTone(priority: string): TicketBadgeTone {
  if (priority === "P0" || priority === "P1") {
    return "danger";
  }
  if (priority === "P2") {
    return "warning";
  }
  if (priority === "P3") {
    return "success";
  }
  return "neutral";
}

function normalizePriority(raw: string | null | undefined): string {
  const value = String(raw || "").trim().toUpperCase();
  return value || "P3";
}

export function mapWorkspaceSlices(queue: SupportQueuePayload | undefined, activeSmartView: string): SupportWorkspaceSlice[] {
  const optionMap = new Map((queue?.filters.smart_view_options ?? []).map((option) => [option.value, option.label]));
  const knownIds = new Set(WORK_SLICE_ORDER);
  const primarySlices: SupportWorkspaceSlice[] = WORK_SLICE_ORDER.map((id) => ({
    id,
    label: WORK_SLICE_FALLBACK_LABELS[id] ?? optionMap.get(id) ?? id,
    count: countFor(queue, id),
    icon: id === "sla_risk" ? "alert" : id === "unassigned" ? "user" : id === "requester_reply" ? "message" : "inbox",
    active: activeSmartView === id,
  }));
  const customSlices: SupportWorkspaceSlice[] = (queue?.summary.smart_view_counts ?? [])
    .filter((item) => item.value !== "all" && !knownIds.has(item.value))
    .map((item) => ({
      id: item.value,
      label: optionMap.get(item.value) ?? item.label,
      count: item.count,
      icon: item.value.includes("risk") ? "alert" : "spark",
      active: activeSmartView === item.value,
    }));
  return [...primarySlices, ...customSlices];
}

export function mapWorkspaceQueues(queue: SupportQueuePayload | undefined, activeQueueId: string | null): SupportWorkspaceQueue[] {
  if ((queue?.summary.queue_counts ?? []).length > 0) {
    return (queue?.summary.queue_counts ?? []).map((item) => {
      const label = item.name ?? item.code ?? "Без очереди";
      const id = item.code ?? String(item.id ?? label);
      return {
        id,
        label,
        count: item.count,
        icon: queueIcon(label),
        active: activeQueueId === id || activeQueueId === label,
      };
    });
  }
  const counts = new Map<string, number>();
  for (const ticket of queue?.tickets ?? []) {
    const key = ticket.queue_code || "Без очереди";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  if (counts.size === 0) {
    return [
      "ServiceDesk L1",
      "Сети",
      "Серверы",
      "Оргтехника",
      "Системы",
      "ИБ",
    ].map((label) => ({
      id: label,
      label,
      count: 0,
      icon: queueIcon(label),
      active: activeQueueId === label,
    }));
  }
  return Array.from(counts.entries()).map(([id, count]) => ({
    id,
    label: id,
    count,
    icon: queueIcon(id),
    active: activeQueueId === id,
  }));
}

export function mapWorkspaceTicketItems(
  queue: SupportQueuePayload | undefined,
  selectedTicketId: string | null,
  now = new Date(),
): SupportWorkspaceTicketItem[] {
  return (queue?.tickets ?? []).map((ticket) => {
    const presentation = getTicketStatusPresentation({
      status: ticket.status,
      statusLabel: ticket.status_label,
      requesterStatusLabel: ticket.requester_status_label,
      nextActionOwner: ticket.next_action_owner,
      statusReason: ticket.status_reason,
    });
    const remainingSeconds = secondsUntil(ticket.next_action_due_at, now);
    const status = timerStatus(remainingSeconds);
    const priority = normalizePriority(ticket.priority_class ?? ticket.priority);
    return {
      id: ticket.ticket_id,
      code: ticket.ticket_code ?? ticket.ticket_id,
      subject: ticket.title,
      requester: ticket.requester_display_name ?? "Инициатор не указан",
      priority,
      priorityTone: priorityTone(priority),
      statusLabel: presentation.statusLabel,
      statusTone: presentation.tone,
      queueLabel: ticket.queue_code ?? "Без очереди",
      assigneeLabel: ticket.assignee_display_name ?? ticket.assignee_id ?? "Не назначен",
      updatedLabel: formatDateTime(ticket.updated_at ?? ticket.created_at),
      unread: ticket.unread_user_messages > 0,
      nextDueLabel: formatRemainingSeconds(remainingSeconds),
      slaRisk: status === "at_risk" || status === "breached",
      active: ticket.ticket_id === selectedTicketId,
    };
  });
}

function buildTimer(
  key: SupportWorkspaceTimer["key"],
  label: string,
  dueAt: string | null | undefined,
  now: Date,
): SupportWorkspaceTimer {
  const remainingSeconds = secondsUntil(dueAt, now);
  const status = timerStatus(remainingSeconds);
  const progress = remainingSeconds === null ? 0 : Math.max(0, Math.min(100, 100 - (remainingSeconds / (4 * 3600)) * 100));
  return {
    key,
    label,
    dueAt: dueAt ?? null,
    remainingSeconds,
    remainingLabel: formatRemainingSeconds(remainingSeconds),
    status,
    progress,
  };
}

function normalizeTimerPayloadStatus(status: string): SupportWorkspaceTimer["status"] {
  if (status === "ok" || status === "at_risk" || status === "breached" || status === "paused" || status === "unknown") {
    return status;
  }
  return "unknown";
}

function buildCompactTimer(
  key: SupportWorkspaceTimer["key"],
  label: string,
  timer: SupportTicketSlaOlaTimerPayload,
): SupportWorkspaceTimer {
  const targetSeconds = timer.target_seconds ?? null;
  const remainingSeconds = timer.remaining_seconds ?? null;
  const progress =
    targetSeconds && remainingSeconds !== null
      ? Math.max(0, Math.min(100, 100 - (remainingSeconds / targetSeconds) * 100))
      : 0;
  return {
    key,
    label,
    dueAt: timer.due_at ?? null,
    remainingSeconds,
    remainingLabel: formatRemainingSeconds(remainingSeconds),
    status: normalizeTimerPayloadStatus(timer.status),
    progress,
  };
}

function mapCompactTimers(slaOla: SupportTicketSlaOlaPayload | undefined): SupportWorkspaceTimer[] | null {
  if (!slaOla) {
    return null;
  }
  return [
    buildCompactTimer("first_response", "Первый ответ", slaOla.first_response),
    buildCompactTimer("resolution", "Решение", slaOla.resolution),
    buildCompactTimer("ola_ack", "OLA подтверждение", slaOla.ola_ack),
    buildCompactTimer("ola_processing", "OLA обработка", slaOla.ola_processing),
  ];
}

export function mapNextAction(
  ticket: SupportTicketDetailPayload["ticket"],
  timers: SupportWorkspaceTimer[],
  now = new Date(),
): SupportWorkspaceNextAction {
  const owner = ticket.next_action_owner || getNextActionOwnerForStatus(ticket.status);
  const ownerLabel = getNextActionOwnerLabel(owner);
  const dueAt = ticket.next_action_due_at || ticket.first_response_due_at || ticket.resolution_due_at || null;
  const remainingSeconds = secondsUntil(dueAt, now);
  const status = timerStatus(remainingSeconds);
  const timerType = timers.some((timer) => timer.key.startsWith("ola") && timer.dueAt === dueAt) ? "ola" : dueAt ? "sla" : "none";
  const presentation = getTicketStatusPresentation({
    status: ticket.status,
    statusLabel: ticket.status_label,
    requesterStatusLabel: ticket.requester_status_label,
    nextActionOwner: owner,
    statusReason: ticket.status_reason,
  });
  return {
    owner,
    ownerLabel,
    label: owner === "support" ? "Ожидаем от вас" : `Ожидаем: ${ownerLabel}`,
    hint: presentation.operatorActionLabel,
    dueAt,
    remainingSeconds,
    remainingLabel: formatRemainingSeconds(remainingSeconds),
    timerType,
    tone: timerTone(status),
  };
}

export function mapWorkspaceTimeline(detail: SupportTicketDetailPayload | undefined): SupportWorkspaceTimelineItem[] {
  return (detail?.timeline ?? []).map((entry, index) => {
    const category = entry.event_category ?? null;
    const isInternal = category === "internal" || entry.visibility === "internal";
    const isDiagnostic = category === "diagnostics" || entry.event_type === "tool_call_started" || entry.event_type === "tool_call_result" || entry.event_type === "playbook_started";
    const kind = isDiagnostic ? "diagnostics" : isInternal ? "internal" : entry.event_type === "chat_message" ? "message" : "history";
    const operationStatus = entry.tool_status ?? "";
    const operationTone = operationStatus === "success" || operationStatus === "succeeded" ? "success" : operationStatus ? "warning" : "neutral";
    const historyTone =
      entry.event_type.includes("breached") || entry.event_type.includes("rejected")
        ? "danger"
        : entry.event_type.includes("warning") || category === "sla" || category === "ola"
          ? "warning"
          : category === "passport" || entry.event_type.includes("approved")
            ? "success"
            : "info";
    return {
      id: entry.message_id ?? String(entry.event_id ?? index),
      kind,
      title: entry.event_label ?? (isDiagnostic ? entry.tool_name ?? "Диагностика" : isInternal ? "Внутренняя заметка" : entry.visibility === "system" ? "Системное событие" : "Сообщение"),
      actor: entry.sender_display_name ?? entry.from_role,
      timestampLabel: formatDateTime(entry.ts),
      body: entry.text,
      visibility: entry.visibility,
      tone: isDiagnostic ? operationTone : isInternal ? "warning" : entry.visibility === "system" ? historyTone : "brand",
      operation: isDiagnostic
        ? {
            name: entry.tool_name ?? "operation",
            status: entry.tool_status ?? "unknown",
            summary: entry.result_summary ?? null,
            preview: entry.result_preview ?? null,
            steps: entry.operation_steps ?? [],
          }
        : undefined,
      attachments: entry.attachments,
    };
  });
}

export function mapWorkspaceContext(detail: SupportTicketDetailPayload | undefined): SupportWorkspaceContext | null {
  if (!detail) {
    return null;
  }
  const registry = detail.snapshot.registry;
  const device = detail.snapshot.device;
  return {
    requester: {
      name: detail.ticket.requester_display_name ?? registry?.person_display_name ?? "Не указан",
      department: registry?.department_name ?? "Не указан",
      phone: "Не указан",
      email: "Не указан",
      location: registry?.location_display_name ?? ([registry?.building, registry?.room].filter(Boolean).join(", ") || "Не указана"),
    },
    device: {
      id: device.device_id,
      hostname: device.hostname ?? registry?.asset_name ?? "Устройство не указано",
      os: device.os ?? "ОС не определена",
      online: device.online,
      onlineLabel: device.online ? "Онлайн" : "Офлайн",
      lastSeenLabel: formatDateTime(device.last_seen_at),
    },
    classification: {
      ticketType: detail.ticket.ticket_type ?? detail.request_form?.request_kind ?? "Не указан",
      category: detail.ticket.category_id ? String(detail.ticket.category_id) : "Не указана",
      service: registry?.service_name ?? (detail.ticket.service_id ? String(detail.ticket.service_id) : "Не указан"),
      source: detail.request_form?.form_title ?? detail.request_form?.form_key ?? "Не указан",
    },
  };
}

export function mapWorkspaceTools(tools: SupportTicketToolsPayload | undefined, deviceOnline = true): SupportWorkspaceToolItem[] {
  return (tools?.tools ?? []).map((tool) => ({
    id: tool.tool_name,
    title: tool.tool_name,
    subtitle: tool.description ?? tool.module_name ?? tool.source,
    riskLabel: tool.risk_level,
    enabled: deviceOnline && !tool.install_required,
    requiresConsent: tool.requires_consent,
  }));
}

export function mapWorkspacePlaybooks(playbooks: SupportTicketPlaybooksPayload | undefined): SupportWorkspaceToolItem[] {
  return (playbooks?.playbooks ?? []).map((playbook) => ({
    id: String(playbook.playbook_version_id),
    title: playbook.key,
    subtitle: playbook.name,
    riskLabel: playbook.readiness_label,
    enabled: playbook.can_run,
    requiresConsent: Boolean(playbooks?.diagnostic_policy?.requester_consent_required),
  }));
}

export function mapWorkspaceKnowledge(knowledge: SupportTicketKnowledgeSuggestionsPayload | undefined): SupportWorkspaceKnowledge {
  return {
    similarTickets: (knowledge?.similar_tickets ?? []).map((ticket) => ({
      id: ticket.id,
      code: ticket.number ?? ticket.id,
      subject: ticket.subject,
      summary: ticket.resolution_summary ?? "Р РµР·СЋРјРµ СЂРµС€РµРЅРёСЏ РЅРµ Р·Р°РїРѕР»РЅРµРЅРѕ",
    })),
    articles: (knowledge?.articles ?? []).map((article) => ({
      id: article.id,
      title: article.title,
      url: article.url ?? "#",
    })),
    aiSummary: knowledge?.ai_summary.text
      ? {
          text: knowledge.ai_summary.text,
          sources: knowledge.ai_summary.sources,
        }
      : null,
  };
}

export function mapWorkspacePassport(
  passport: SupportTicketPassportPayload | undefined,
  ticketId: string | null,
  readiness?: SupportTicketPassportReadinessPayload,
): SupportWorkspacePassport {
  if (readiness) {
    return {
      status: readiness.status,
      done: readiness.done,
      total: readiness.total,
      items: readiness.items.map((item) => ({
        key: item.key,
        label: item.label,
        done: item.status === "done",
      })),
      openUrl: ticketId ? `/app/tickets/${ticketId}/passport/print` : null,
    };
  }
  const missingFacts = passport?.requirements?.missing_facts ?? [];
  const total = Math.max((passport?.requirements?.required_sections ?? []).length || 4, missingFacts.length || 4);
  const done = Math.max(0, total - missingFacts.length);
  return {
    status: passport?.status ?? "missing",
    done,
    total,
    items: [
      { key: "problem_identified", label: "Проблема идентифицирована", done: missingFacts.every((fact) => fact.required_fact !== "problem") },
      { key: "cause_found", label: "Причина установлена", done: missingFacts.every((fact) => fact.required_fact !== "root_cause") },
      { key: "solution_applied", label: "Решение применено", done: missingFacts.every((fact) => fact.required_fact !== "solution") },
      { key: "verified_and_closed", label: "Проверка и закрытие", done: passport?.status === "ready" || passport?.status === "draft" },
    ],
    openUrl: ticketId ? `/app/tickets/${ticketId}/passport/print` : null,
  };
}

export function mapSupportWorkspaceViewModel({
  activeQueueId,
  activeSmartView,
  detail,
  knowledge,
  passport,
  passportReadiness,
  playbooks,
  queue,
  selectedTicketId,
  slaOla,
  tools,
  now = new Date(),
}: {
  activeQueueId: string | null;
  activeSmartView: string;
  detail?: SupportTicketDetailPayload;
  knowledge?: SupportTicketKnowledgeSuggestionsPayload;
  passport?: SupportTicketPassportPayload;
  passportReadiness?: SupportTicketPassportReadinessPayload;
  playbooks?: SupportTicketPlaybooksPayload;
  queue?: SupportQueuePayload;
  selectedTicketId: string | null;
  slaOla?: SupportTicketSlaOlaPayload;
  tools?: SupportTicketToolsPayload;
  now?: Date;
}): SupportWorkspaceViewModel {
  const timers = mapCompactTimers(slaOla) ?? (detail
    ? [
        buildTimer("first_response", "Первый ответ", detail.ticket.first_response_due_at, now),
        buildTimer("resolution", "Решение", detail.ticket.resolution_due_at, now),
      ]
    : []);
  const selectedTicket = detail
    ? (() => {
        const presentation = getTicketStatusPresentation({
          status: detail.ticket.status,
          statusLabel: detail.ticket.status_label,
          requesterStatusLabel: detail.ticket.requester_status_label,
          nextActionOwner: detail.ticket.next_action_owner,
          statusReason: detail.ticket.status_reason,
          evidenceRequired: detail.ticket.evidence_required,
          evidenceRef: detail.ticket.evidence_ref,
        });
        const priority = normalizePriority(detail.ticket.priority_class ?? detail.ticket.priority);
        return {
          id: detail.ticket.ticket_id,
          code: detail.ticket.ticket_code ?? detail.ticket.ticket_id,
          subject: detail.ticket.title,
          description: detail.ticket.description ?? "Описание не заполнено",
          priority,
          priorityTone: priorityTone(priority),
          statusLabel: presentation.statusLabel,
          statusTone: presentation.tone,
          queueLabel: detail.ticket.queue.name ?? detail.ticket.queue.code ?? "Без очереди",
          assigneeLabel: detail.ticket.assignee_id ?? "Не назначен",
          requesterLabel: detail.ticket.requester_display_name ?? "Не указан",
          createdLabel: formatDateTime(detail.ticket.created_at, true),
          updatedLabel: formatDateTime(detail.ticket.updated_at, true),
          nextAction: mapNextAction(detail.ticket, timers, now),
          timers,
          timeline: mapWorkspaceTimeline(detail),
          canSendInternalNote: detail.actions.can_send_internal_note,
        };
      })()
    : null;
  const context = mapWorkspaceContext(detail);
  return {
    theme: "dark",
    left: {
      slices: mapWorkspaceSlices(queue, activeSmartView),
      queues: mapWorkspaceQueues(queue, activeQueueId),
      tickets: mapWorkspaceTicketItems(queue, selectedTicketId, now),
      visibleCount: queue?.summary.visible_count ?? 0,
    },
    selectedTicket,
    right: {
      context,
      tools: mapWorkspaceTools(tools, context?.device.online ?? true),
      playbooks: mapWorkspacePlaybooks(playbooks),
      knowledge: mapWorkspaceKnowledge(knowledge),
      passport: mapWorkspacePassport(passport, detail?.ticket.ticket_id ?? selectedTicketId, passportReadiness),
    },
    raw: {
      queue,
      detail,
      knowledge,
      tools,
      playbooks,
      passport,
      slaOla,
      passportReadiness,
    },
  };
}
