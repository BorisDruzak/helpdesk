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
  return error instanceof Error && error.message.trim() ? error.message : fallback;
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
