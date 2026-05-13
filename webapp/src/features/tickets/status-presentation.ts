export type TicketBadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

export type TicketStatusPresentationInput = {
  status: string | null | undefined;
  statusLabel?: string | null;
  requesterStatusLabel?: string | null;
  nextActionOwner?: string | null;
  statusReason?: string | null;
  evidenceRequired?: boolean | null;
  evidenceRef?: string | null;
};

export type TicketStatusPresentation = {
  status: string;
  statusLabel: string;
  requesterStatusLabel: string;
  ownerLabel: string;
  stageLabel: string;
  tone: TicketBadgeTone;
  evidenceLabel: string;
  evidenceTone: TicketBadgeTone;
  operatorActionLabel: string;
  statusReasonLabel: string;
  waits: boolean;
  terminal: boolean;
};

const WAITING_STATUSES = new Set([
  "waiting_on_user",
  "waiting_on_internal_team",
  "waiting_on_vendor",
  "waiting_on_approval",
]);

const TERMINAL_STATUSES = new Set(["resolved", "closed", "canceled"]);

export function getTicketStatusTone(status: string | null | undefined): TicketBadgeTone {
  switch (status) {
    case "accepted":
    case "new":
    case "queued":
    case "assigned":
    case "sent":
    case "running":
      return "brand";
    case "in_progress":
    case "scheduled":
    case "resolved":
    case "success":
    case "succeeded":
      return "success";
    case "waiting_on_user":
    case "waiting_on_internal_team":
    case "waiting_on_vendor":
    case "waiting_on_approval":
      return "warning";
    case "failed":
    case "timed_out":
    case "canceled":
      return "danger";
    case "closed":
      return "neutral";
    default:
      return "neutral";
  }
}

export function getTicketStageLabel(statusOrStage: string | null | undefined): string {
  switch (statusOrStage) {
    case "intake":
    case "new":
      return "Приём";
    case "queue":
    case "queued":
      return "Очередь";
    case "assigned":
      return "Назначен";
    case "work":
    case "in_progress":
      return "В работе";
    case "scheduled":
      return "Запланирован";
    case "waiting":
    case "waiting_on_user":
    case "waiting_on_internal_team":
    case "waiting_on_vendor":
    case "waiting_on_approval":
      return "Ожидание";
    case "review":
    case "resolved":
      return "Решение";
    case "done":
    case "closed":
      return "Закрыт";
    case "terminal":
      return "Финал";
    case "canceled":
      return "Отменён";
    default:
      return "Другое";
  }
}

export function getTicketStageTone(statusOrStage: string | null | undefined): TicketBadgeTone {
  switch (statusOrStage) {
    case "waiting":
    case "waiting_on_user":
    case "waiting_on_internal_team":
    case "waiting_on_vendor":
    case "waiting_on_approval":
      return "warning";
    case "work":
    case "in_progress":
    case "scheduled":
    case "review":
    case "resolved":
      return "success";
    case "canceled":
      return "danger";
    case "done":
    case "closed":
    case "terminal":
      return "neutral";
    case "intake":
    case "queue":
    case "new":
    case "queued":
    case "assigned":
      return "brand";
    default:
      return "neutral";
  }
}

export function getNextActionOwnerLabel(owner: string | null | undefined): string {
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

export function getNextActionOwnerForStatus(status: string | null | undefined): string {
  switch (status) {
    case "waiting_on_user":
      return "requester";
    case "waiting_on_internal_team":
      return "internal_team";
    case "waiting_on_vendor":
      return "vendor";
    case "waiting_on_approval":
      return "approver";
    case "resolved":
      return "requester";
    case "closed":
    case "canceled":
      return "system";
    default:
      return "support";
  }
}

function getOperatorActionLabel(status: string, owner: string | null | undefined): string {
  if (status === "closed" || status === "canceled") {
    return "Контроль не требуется";
  }
  if (status === "resolved" && owner === "requester") {
    return "Ждать подтверждение результата";
  }

  switch (owner) {
    case "support":
      return "Ответить или продолжить диагностику";
    case "requester":
      return "Ждать ответ пользователя";
    case "internal_team":
      return "Ждать внутреннюю группу";
    case "vendor":
      return "Контролировать внешний ответ";
    case "approver":
      return "Ждать согласование";
    case "system":
      return "Проверить автоматизацию";
    default:
      return "Проверить карточку";
  }
}

export function getTicketStatusPresentation(input: TicketStatusPresentationInput): TicketStatusPresentation {
  const status = input.status || "";
  const normalizedStatus = status.trim();
  const statusLabel = input.statusLabel?.trim() || normalizedStatus || "Не указан";
  const requesterStatusLabel = input.requesterStatusLabel?.trim() || "Не указан";
  const evidenceRef = input.evidenceRef?.trim() || "";
  const evidenceRequired = Boolean(input.evidenceRequired);
  const terminal = TERMINAL_STATUSES.has(normalizedStatus);
  const waits = WAITING_STATUSES.has(normalizedStatus);
  const stageLabel = getTicketStageLabel(normalizedStatus);
  const nextActionOwner =
    input.nextActionOwner ?? (stageLabel !== "Другое" ? getNextActionOwnerForStatus(normalizedStatus) : undefined);

  let evidenceLabel = "Не требуется";
  let evidenceTone: TicketBadgeTone = "neutral";
  if (evidenceRef) {
    evidenceLabel = "Доказательство есть";
    evidenceTone = "success";
  } else if (evidenceRequired) {
    evidenceLabel = "Нужно доказательство";
    evidenceTone = "warning";
  }

  return {
    status: normalizedStatus,
    statusLabel,
    requesterStatusLabel,
    ownerLabel: getNextActionOwnerLabel(nextActionOwner),
    stageLabel,
    tone: getTicketStatusTone(normalizedStatus),
    evidenceLabel,
    evidenceTone,
    operatorActionLabel: getOperatorActionLabel(normalizedStatus, input.nextActionOwner),
    statusReasonLabel: input.statusReason?.trim() || "Не указана",
    waits,
    terminal,
  };
}
