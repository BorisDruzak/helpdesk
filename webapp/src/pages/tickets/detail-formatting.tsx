import {
  type SupportTicketEvidenceCandidatePayload,
  type SupportTicketPassportPayload,
  type SupportTicketDetailPayload,
  type SupportTicketPlaybooksPayload,
  type SupportTicketToolsPayload,
} from "../../features/queues/api";
import {
  validateSupportToolParams,
} from "../../features/queues/tool-param-fields";
import {
  getTicketStatusPresentation,
} from "../../features/tickets/status-presentation";
export const SUPPORT_QUEUE_REFRESH_MS = 15_000;




export type NormalizedAttachment = {
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




export type CustomerHistoryEventForDetail = NonNullable<SupportTicketDetailPayload["customer_history"]>["events"][number];




export function formatDateTime(value: string | null | undefined) {
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




export function getRoleTone(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.from_role === "support" || entry.from_role === "agent") {
    return "agent" as const;
  }
  if (entry.from_role === "user" || entry.from_role === "client") {
    return "client" as const;
  }
  return "neutral" as const;
}




export function getRoleLabel(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.visibility === "internal") {
    return "Внутренняя заметка";
  }
  if (entry.event_type === "tool_call_started" || entry.event_type === "tool_call_result") {
    return "Инструмент";
  }
  if (entry.event_type === "playbook_started") {
    return "Автодиагностика";
  }
  if (entry.from_role === "support" || entry.from_role === "agent") {
    return "Агент";
  }
  if (entry.from_role === "user" || entry.from_role === "client") {
    return "Клиент";
  }
  return "Система";
}




export function getRoleBadgeTone(entry: SupportTicketDetailPayload["timeline"][number]) {
  if (entry.visibility === "internal") {
    return "warning" as const;
  }
  if (entry.event_type === "tool_call_started" || entry.event_type === "tool_call_result") {
    return "info" as const;
  }
  if (entry.event_type === "playbook_started") {
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




export function describePresence(value: boolean) {
  return value ? "онлайн" : "офлайн";
}




export function describeToolRiskLevel(value: string) {
  if (value === "safe_read") {
    return "Безопасное чтение";
  }
  if (value === "confirmation_required") {
    return "Нужно подтверждение";
  }
  return value.replaceAll("_", " ");
}




export function buildArtifactUrl(ticketId: string, attachment: Record<string, unknown>): string | null {
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




export function getAttachmentMediaType(attachment: Record<string, unknown>): "image" | "video" | "file" {
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




export function normalizeAttachment(
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




export function flattenAttachments(ticketId: string, timeline: SupportTicketDetailPayload["timeline"]) {
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




export function getOperationTitle(operation: SupportTicketDetailPayload["snapshot"]["latest_operations"][number]) {
  return operation.tool_name ?? operation.command_name ?? operation.kind;
}




export function getOperationScopeLabel(operation: SupportTicketDetailPayload["snapshot"]["latest_operations"][number]) {
  if (operation.scope === "playbook") {
    return "плейбук";
  }
  if (operation.scope === "device") {
    return "устройство";
  }
  return "тикет";
}




export function getOperationDisplayStatus(operation: SupportTicketDetailPayload["snapshot"]["latest_operations"][number]) {
  return operation.display_status || operation.status;
}




export function getOperationDisplayLabel(operation: SupportTicketDetailPayload["snapshot"]["latest_operations"][number]) {
  return operation.display_label || operation.status;
}




export function parseToolParams(
  selectedTool: SupportTicketToolsPayload["tools"][number] | null,
  selectedPresetId: string,
  toolParams: Record<string, unknown>,
) {
  return validateSupportToolParams(selectedTool, selectedPresetId, toolParams);
}




export function getTransitionGroupLabel(status: string): string {
  if (status.startsWith("waiting_on_")) {
    return "Ожидание";
  }
  if (status === "resolved") {
    return "Решение";
  }
  if (status === "closed" || status === "canceled") {
    return "Финал";
  }
  if (status === "scheduled") {
    return "План";
  }
  return getTicketStatusPresentation({ status }).stageLabel;
}




export type StatusTransitionOption = {
  value: string;
  label: string;
  available: boolean;
  blockedReason?: string;
};




export const COMMON_STATUS_TRANSITIONS: Array<{ value: string; label: string }> = [
  { value: "queued", label: "В очередь" },
  { value: "assigned", label: "Назначить" },
  { value: "in_progress", label: "Взять в работу" },
  { value: "waiting_on_user", label: "Ждём пользователя" },
  { value: "waiting_on_internal", label: "Ждём внутреннюю группу" },
  { value: "waiting_on_vendor", label: "Ждём внешнюю сторону" },
  { value: "waiting_on_approval", label: "Ждём согласование" },
  { value: "scheduled", label: "Запланировать" },
  { value: "resolved", label: "Решить" },
  { value: "closed", label: "Закрыть" },
  { value: "canceled", label: "Отменить" },
];




export function groupStatusOptions(statusOptions: StatusTransitionOption[]) {
  const groups = new Map<string, StatusTransitionOption[]>();
  statusOptions.forEach((option) => {
    const groupLabel = getTransitionGroupLabel(option.value);
    groups.set(groupLabel, [...(groups.get(groupLabel) ?? []), option]);
  });
  return Array.from(groups.entries()).map(([label, options]) => ({ label, options }));
}




export function buildTransitionOptions(
  statusOptions: Array<{ value: string; label: string }>,
  currentStatus: string,
): { allowed: StatusTransitionOption[]; blocked: StatusTransitionOption[] } {
  const allowedValues = new Set(statusOptions.map((option) => option.value));
  const allowed = statusOptions
    .filter((option) => option.value !== currentStatus)
    .map((option) => ({
      ...option,
      available: true,
    }));
  const blocked = COMMON_STATUS_TRANSITIONS.filter(
    (option) => option.value !== currentStatus && !allowedValues.has(option.value),
  ).map((option) => ({
    ...option,
    available: false,
    blockedReason: "Сервер не разрешил этот переход из текущего этапа.",
  }));

  return {
    allowed,
    blocked,
  };
}




export type TicketAutomationPlaybook = SupportTicketPlaybooksPayload["playbooks"][number];




export type TicketDiagnosticPolicy = NonNullable<SupportTicketPlaybooksPayload["diagnostic_policy"]>;




export type TicketDiagnosticTarget = NonNullable<SupportTicketPlaybooksPayload["diagnostic_target"]>;




export function formatDiagnosticPolicyList(items: string[], fallback: string) {
  return items.length ? items.join(", ") : fallback;
}




export function formatDiagnosticTarget(target: TicketDiagnosticTarget | null | undefined, fallbackDeviceId?: string | null) {
  const targetDeviceId = target?.target_device_id ?? fallbackDeviceId ?? null;
  const person = target?.affected_display_name ?? target?.affected_person_id ?? null;
  if (targetDeviceId && person) {
    return `${targetDeviceId} · ${person}`;
  }
  if (targetDeviceId) {
    return targetDeviceId;
  }
  if (target?.reason_code) {
    return `нет цели (${target.reason_code})`;
  }
  return "цель не определена";
}




export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}




export function textValue(value: unknown): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}




export function compactParts(parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" · ");
}




export function customerHistorySummary(event: CustomerHistoryEventForDetail): string {
  if (event.summary) {
    return event.summary;
  }
  const payload = asRecord(event.payload);
  for (const key of ["text", "title", "status", "result", "result_summary"]) {
    const value = payload?.[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return event.event_type;
}




export function personContextLabel(record: Record<string, unknown> | null, fallbackPersonId?: string | null): string {
  const label = compactParts([
    textValue(record?.display_name) ?? textValue(record?.full_name),
    textValue(record?.actor_id),
    textValue(record?.person_id) ?? fallbackPersonId ?? null,
  ]);
  return label || fallbackPersonId || "не указан";
}




export function onBehalfReason(ticket: Pick<SupportTicketDetailPayload["ticket"], "requester_account_context" | "ticket_context">): string {
  const ticketContext = asRecord(ticket.ticket_context);
  const accountContext = asRecord(ticket.requester_account_context);
  const declaredAccount = asRecord(accountContext?.declared_account);
  return (
    textValue(declaredAccount?.reason)
    ?? textValue(ticketContext?.on_behalf_reason)
    ?? textValue(accountContext?.reason)
    ?? "не указана"
  );
}




export function diagnosticPolicyBadges(policy: TicketDiagnosticPolicy) {
  const priorities = formatDiagnosticPolicyList(policy.auto_run_priorities, "все приоритеты");
  const badges = [
    policy.auto_run_enabled ? `Автозапуск: ${priorities}` : "Автозапуск выключен",
    policy.requester_consent_required ? "Нужно согласие пользователя" : "Согласие пользователя не требуется",
    policy.high_risk_consent_required ? "High-risk consent" : "High-risk tools без отдельного consent",
  ];
  if (policy.attach_to_timeline) {
    badges.push("В timeline");
  }
  if (policy.attach_to_passport) {
    badges.push("В паспорт");
  }
  if (policy.attach_as_evidence) {
    badges.push("Evidence");
  }
  return badges;
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




export const PASSPORT_REQUIREMENT_SOURCE_LABELS: Record<string, string> = {
  ticket_evidence_items: "доказательства тикета",
  "ticket.requester_resolution_summary": "публичный итог для пользователя",
  "ticket.resolution_summary": "внутренний итог решения",
  ticket_approvals: "согласования",
  ticket_worklogs: "worklog",
  operations: "операции тикета",
  observer_traces: "observer trace",
};




export const PASSPORT_STALE_REASON_LABELS: Record<string, string> = {
  evidence_changed: "Новые доказательства",
  events_changed: "Новые сообщения или события",
  operations_changed: "Новые операции",
  worklogs_changed: "Новый worklog",
  approvals_changed: "Новые согласования",
  related_objects_changed: "Новые связанные объекты",
};




export const PASSPORT_CANDIDATE_SOURCE_LABELS: Record<string, string> = {
  operation: "Операция",
  playbook_run: "Плейбук",
  playbook_step: "Шаг плейбука",
  artifact: "Файл",
  worklog: "Worklog",
  approval: "Согласование",
  chat_message: "Сообщение",
  observer_trace: "Observer trace",
  ticket: "Поле тикета",
};




export function asPassportText(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}




export function formatPassportRequirementSource(source: string | null | undefined): string {
  const raw = String(source || "").trim();
  if (!raw) {
    return "Источник не указан";
  }
  return `Источник: ${PASSPORT_REQUIREMENT_SOURCE_LABELS[raw] || raw}`;
}




export function formatPassportStaleReason(reason: string): string {
  return PASSPORT_STALE_REASON_LABELS[reason] || reason;
}




export function passportSourceCandidates(
  fact: NonNullable<SupportTicketPassportPayload["requirements"]>["missing_facts"][number],
): Array<Record<string, unknown>> {
  return Array.isArray(fact.source_candidates) ? fact.source_candidates : [];
}




export function passportEvidenceSourceLabel(item: SupportTicketPassportPayload["evidence"][number]): string {
  return item.source_ref || [item.source_kind, item.source_id].filter(Boolean).join(":") || "Источник не указан";
}




export function passportCandidateSourceLabel(candidate: SupportTicketEvidenceCandidatePayload): string {
  return PASSPORT_CANDIDATE_SOURCE_LABELS[candidate.source_kind] || candidate.source_kind;
}