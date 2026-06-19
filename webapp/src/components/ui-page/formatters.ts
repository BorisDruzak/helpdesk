import type { BadgeTone } from "../ui/badge";

type DateFormatterOptions = {
  emptyText?: string;
  timeZone?: string;
};

type HumanIdentifierOptions = {
  emptyText?: string;
  uuidPrefix?: string;
};

const STATUS_LABELS: Record<string, string> = {
  active: "Активно",
  approved: "Согласовано",
  archived: "В архиве",
  canceled: "Отменена",
  closed: "Закрыта",
  denied: "Отклонено",
  expired: "Истекла",
  inactive: "Неактивно",
  in_progress: "В работе",
  new: "Новая",
  offline: "Нет связи",
  online: "В сети",
  open: "Открыта",
  pending: "Ожидает",
  pending_admin_review: "Ждет администратора",
  pending_user_confirmation: "Ждет подтверждения",
  rejected: "Отклонено",
  resolved: "Решена",
  superseded: "Заменена",
  user_confirmed: "Подтверждена",
  waiting_support: "Ждет поддержку",
  waiting_user: "Ждет пользователя",
};

const STATUS_TONES: Record<string, BadgeTone> = {
  active: "success",
  approved: "success",
  archived: "neutral",
  canceled: "danger",
  closed: "neutral",
  denied: "danger",
  expired: "neutral",
  inactive: "danger",
  in_progress: "brand",
  new: "info",
  offline: "warning",
  online: "success",
  open: "info",
  pending: "warning",
  pending_admin_review: "warning",
  pending_user_confirmation: "warning",
  rejected: "danger",
  resolved: "success",
  superseded: "neutral",
  user_confirmed: "success",
  waiting_support: "warning",
  waiting_user: "warning",
};

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function coerceDate(value: Date | number | string | null | undefined): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dateParts(
  value: Date | number | string | null | undefined,
  options: DateFormatterOptions,
): Record<string, string> | null {
  const date = coerceDate(value);
  if (!date) {
    return null;
  }
  const formatter = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    timeZone: options.timeZone,
    year: "numeric",
  });
  return Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
}

export function formatRussianDate(
  value: Date | number | string | null | undefined,
  options: DateFormatterOptions = {},
): string {
  const parts = dateParts(value, options);
  if (!parts) {
    return options.emptyText ?? "Не указано";
  }
  return `${parts.day}.${parts.month}.${parts.year}`;
}

export function formatRussianDateTime(
  value: Date | number | string | null | undefined,
  options: DateFormatterOptions = {},
): string {
  const parts = dateParts(value, options);
  if (!parts) {
    return options.emptyText ?? "Не указано";
  }
  return `${parts.day}.${parts.month}.${parts.year}, ${parts.hour}:${parts.minute}`;
}

export function formatStatusLabel(status: string | null | undefined): string {
  const key = String(status ?? "").trim().toLowerCase();
  if (!key) {
    return "Не указано";
  }
  return STATUS_LABELS[key] ?? key.replace(/[_-]+/g, " ");
}

export function statusBadgeTone(status: string | null | undefined): BadgeTone {
  const key = String(status ?? "").trim().toLowerCase();
  return STATUS_TONES[key] ?? "neutral";
}

export function isRawUuid(value: string | null | undefined): boolean {
  return UUID_PATTERN.test(String(value ?? "").trim());
}

export function formatHumanIdentifier(
  value: string | number | null | undefined,
  options: HumanIdentifierOptions = {},
): string {
  const text = String(value ?? "").trim();
  if (!text) {
    return options.emptyText ?? "Не назначено";
  }
  if (isRawUuid(text)) {
    return `${options.uuidPrefix ?? "ID"} ${text.slice(0, 8)}`;
  }
  return text;
}
