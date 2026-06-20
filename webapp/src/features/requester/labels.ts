import type { AuthenticatedRequesterTicket, RequesterPendingRegistrationClaim } from "./types";

type DeviceLike = {
  agent_version?: string | null;
  asset_name?: string | null;
  device_id?: string | null;
  hostname?: string | null;
  online?: boolean | null;
  os?: string | null;
};

export function requesterErrorMessage(error: unknown, fallback: string): string {
  const code = requesterErrorCode(error);
  if (code && REQUESTER_SAFE_ERROR_MESSAGES[code]) {
    return REQUESTER_SAFE_ERROR_MESSAGES[code];
  }
  const status = requesterErrorStatus(error);
  if (status === 401) {
    return "Войдите в аккаунт, чтобы продолжить.";
  }
  if (status === 403) {
    return "Это действие недоступно для вашего аккаунта.";
  }
  if (status === 404) {
    return "Обращение не найдено или недоступно.";
  }
  if (status === 409) {
    return "Состояние обращения изменилось. Обновите страницу и попробуйте еще раз.";
  }
  if (status && status >= 500) {
    return "Сервис временно недоступен. Попробуйте позже.";
  }
  if (status && status >= 400) {
    return "Проверьте данные и попробуйте еще раз.";
  }
  return fallback;
}

const REQUESTER_SAFE_ERROR_MESSAGES: Record<string, string> = {
  INVALID_TICKET_STATUS: "Это действие сейчас недоступно для обращения.",
  NOT_FOUND: "Обращение не найдено или недоступно.",
  QUALITY_FEEDBACK_ERROR: "Оценку не удалось сохранить. Проверьте данные и попробуйте еще раз.",
  QUALITY_REOPEN_ERROR: "Обращение не удалось вернуть в работу. Проверьте данные и попробуйте еще раз.",
  REQUESTER_AGENT_REQUIRED: "Для этой формы нужно привязанное устройство. Привяжите устройство или выберите форму для ручной обработки.",
  REQUESTER_CONTACT_REQUIRED: "Укажите телефон или другой контакт для связи.",
  REQUESTER_DEVICE_FORBIDDEN: "Это устройство недоступно для вашего профиля.",
  REQUESTER_PROFILE_FORBIDDEN: "Профиль недоступен для вашего аккаунта.",
  REQUESTER_PROFILE_INCOMPLETE: "Заполните профиль, чтобы продолжить.",
  VALIDATION_ERROR: "Проверьте заполненные поля и попробуйте еще раз.",
  WORKFLOW_POLICY_ERROR: "Действие не выполнено из-за правил обработки обращения.",
};

function requesterErrorCode(error: unknown): string | null {
  if (!error || typeof error !== "object") {
    return null;
  }
  const value = (error as { code?: unknown; details?: unknown; errorCode?: unknown }).code;
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  const errorCode = (error as { errorCode?: unknown }).errorCode;
  if (typeof errorCode === "string" && errorCode.trim()) {
    return errorCode.trim();
  }
  const details = (error as { details?: unknown }).details;
  if (typeof details === "string" && /^[A-Z0-9_]+$/.test(details.trim())) {
    return details.trim();
  }
  return null;
}

function requesterErrorStatus(error: unknown): number | null {
  if (!error || typeof error !== "object") {
    return null;
  }
  const value = (error as { status?: unknown }).status;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function requesterSafeFieldLabel(label: string | null | undefined, fallback: string): string {
  return String(label || "").trim() || fallback;
}

export function requesterDeviceLabel(device: DeviceLike | null | undefined, fallback = "Устройство без имени"): string {
  const asset = String(device?.asset_name ?? "").trim();
  const hostname = String(device?.hostname ?? "").trim();
  if (asset && hostname) {
    return `${asset} · ${hostname}`;
  }
  return asset || hostname || fallback;
}

export function requesterDeviceSystemParts(device: DeviceLike | null | undefined): string[] {
  const parts = [device?.os, device?.agent_version ? `Агент ${device.agent_version}` : null];
  return parts.map((part) => String(part || "").trim()).filter(Boolean);
}

export function requesterDeviceSystemLabel(device: DeviceLike | null | undefined): string {
  return requesterDeviceSystemParts(device).join(" · ") || "Сведения уточняются";
}

export function requesterDeviceConnectionStatusLabel(device: DeviceLike | null | undefined): string {
  if (!device) {
    return "Устройство не привязано";
  }
  return requesterOnlineStatusLabel(device.online);
}

export function requesterOnlineStatusLabel(value?: boolean | null): string {
  if (value === true) return "Онлайн";
  if (value === false) return "Не в сети";
  return "Активность не определена";
}

export function requesterRelationshipLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    primary_user: "Основное устройство",
    responsible: "Ответственное устройство",
    shared_user: "Совместный доступ",
  };
  return labels[String(value || "").trim()] || "Доступное устройство";
}

export function requesterAccessStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    active: "Доступно",
    admin_confirmed: "Подтверждено",
    approved: "Подтверждено",
    confirmed: "Подтверждено",
    conflict: "Нужна проверка поддержки",
    pending_admin_review: "Ожидает проверки администратора",
    pending_user_confirmation: "Ожидает подтверждения",
    rejected: "Отклонено",
    revoked: "Отключено",
    user_confirmed: "Ожидает проверки администратора",
  };
  return labels[String(value || "").trim()] || "Статус уточняется";
}

export function requesterPendingDeviceStatusLabel(claim: RequesterPendingRegistrationClaim): string {
  return requesterAccessStatusLabel(claim.status);
}

export function requesterReadinessText(profileComplete: boolean, hasDeviceContext: boolean): string {
  if (!profileComplete) {
    return "Профиль нужно заполнить";
  }
  if (!hasDeviceContext) {
    return "Устройство не привязано";
  }
  return "Можно создавать обращения";
}

export function requesterTicketNextActionLabel(ticket: AuthenticatedRequesterTicket): string | null {
  const status = String(ticket.status ?? "").toLowerCase();
  if (status === "waiting_user") {
    return "Нужен ваш ответ";
  }
  if (status === "resolved") {
    return "Подтвердите решение";
  }
  return null;
}

export function requesterSafeAttachmentName(name?: string | null): string {
  return String(name || "").trim() || "Вложение";
}
