const PERMISSION_LABELS: Record<string, string> = {
  "module.tool.run.high_risk": "запуск high-risk инструментов",
  "module.tool.run.low_risk": "запуск безопасных инструментов",
  "ticket.assign": "назначение исполнителя",
  "ticket.comment.internal": "внутренние заметки",
  "ticket.comment.public": "публичные ответы",
  "ticket.passport.manage": "паспорт решения",
  "ticket.playbook.run": "запуск playbook",
  "ticket.priority.change": "изменение приоритета",
  "ticket.queue.change": "смена очереди",
  "ticket.status.change": "смена статуса",
  "ticket.tool.run": "запуск инструментов",
};

const OPERATION_REASON_LABELS: Record<string, string> = {
  already_finished: "операция уже завершена",
  consent_required_for_retry: "для повтора нужно новое согласие пользователя",
  CONSENT_REQUIRED_FOR_RETRY: "для повтора нужно новое согласие пользователя",
  retry_endpoint_unavailable: "безопасный API повтора недоступен",
  retry_limit_reached: "лимит повторов исчерпан",
  retry_params_unavailable: "нет безопасно сохранённых параметров повтора",
  RETRY_PARAMS_UNAVAILABLE: "нет безопасно сохранённых параметров повтора",
  retry_policy_missing: "нет политики повтора",
  status_not_cancelable: "текущий статус нельзя отменить",
  status_not_retryable: "текущий статус нельзя повторить",
  status_unknown: "статус операции неизвестен",
};

const PROVIDER_STATUS_LABELS: Record<string, string> = {
  degraded: "работает с ограничениями",
  empty: "нет совпадений",
  error: "ошибка провайдера",
  ok: "готов",
  provider_unavailable: "провайдер недоступен",
  unavailable: "недоступен",
};

const EXTERNAL_PROVIDER_STATUS_LABELS: Record<string, string> = {
  configured: "подключена",
  disabled: "отключена",
  error: "ошибка подключения",
  not_configured: "не подключена",
  ok: "готова",
  provider_unavailable: "недоступна",
  unavailable: "недоступна",
};

const RISK_LEVEL_LABELS: Record<string, string> = {
  dangerous: "опасный",
  high: "высокий",
  low: "низкий",
  safe_read: "безопасное чтение",
  safe_readonly: "безопасное чтение",
  sensitive_read: "чувствительное чтение",
  system_write: "изменяет систему",
};

const TOOL_KIND_LABELS: Record<string, string> = {
  diagnostic: "диагностика",
  evidence: "сбор доказательств",
  inventory: "инвентаризация",
  remediation: "исправление",
};

const SOURCE_LABELS: Record<string, string> = {
  agent: "агент",
  catalog: "каталог",
  managed: "серверный модуль",
  server: "сервер",
};

function normalizeCode(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

function humanizeCode(value: string | null | undefined): string {
  const code = normalizeCode(value);
  if (!code) {
    return "не указано";
  }
  return code
    .replace(/[_:.-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

export function permissionLabel(code: string | null | undefined): string {
  const normalized = normalizeCode(code);
  return PERMISSION_LABELS[normalized] ?? humanizeCode(normalized);
}

export function permissionMetaLabel(code: string | null | undefined): string | null {
  const normalized = normalizeCode(code);
  if (!normalized) {
    return null;
  }
  return `Право: ${permissionLabel(normalized)}`;
}

export function roleListLabel(roles: string[] | null | undefined): string | null {
  const normalized = (roles ?? []).map((role) => normalizeCode(role)).filter(Boolean);
  if (!normalized.length) {
    return null;
  }
  return `Роли: ${normalized.join(", ")}`;
}

export function riskLevelLabel(value: string | null | undefined): string {
  const normalized = normalizeCode(value);
  return RISK_LEVEL_LABELS[normalized] ?? humanizeCode(normalized);
}

export function riskMetaLabel(value: string | null | undefined): string {
  return `Риск: ${riskLevelLabel(value)}`;
}

export function consentLabel(requiresConsent: boolean): string {
  return requiresConsent ? "Требуется согласие пользователя" : "Согласие не требуется";
}

export function sourceLabel(value: string | null | undefined): string {
  const normalized = normalizeCode(value);
  return SOURCE_LABELS[normalized] ?? humanizeCode(normalized);
}

export function toolKindLabel(value: string | null | undefined): string {
  const normalized = normalizeCode(value);
  return TOOL_KIND_LABELS[normalized] ?? humanizeCode(normalized);
}

export function providerStatusLabel(value: string | null | undefined): string {
  const normalized = normalizeCode(value);
  return PROVIDER_STATUS_LABELS[normalized] ?? humanizeCode(normalized);
}

export function externalProviderStatusLabel(value: string | null | undefined): string {
  const normalized = normalizeCode(value);
  return EXTERNAL_PROVIDER_STATUS_LABELS[normalized] ?? humanizeCode(normalized);
}

export function fallbackReasonLabel(value: string | null | undefined): string | null {
  const normalized = normalizeCode(value);
  if (!normalized) {
    return null;
  }
  if (normalized === "provider_unavailable") {
    return "основной провайдер недоступен";
  }
  if (normalized === "empty_provider_response") {
    return "провайдер не вернул совпадений";
  }
  if (normalized === "catalog_fallback") {
    return "использован локальный каталог";
  }
  return humanizeCode(normalized);
}

export function operationActionReasonLabel(reason: string | null | undefined): string {
  const normalized = normalizeCode(reason);
  if (!normalized) {
    return "действие недоступно";
  }
  return OPERATION_REASON_LABELS[normalized] ?? humanizeCode(normalized);
}

export function operationActionReasonSentence(reason: string | null | undefined): string {
  const label = operationActionReasonLabel(reason);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function operationPolicyLabel(raw: string | null | undefined): string | null {
  const value = normalizeCode(raw);
  if (!value) {
    return null;
  }
  const [kind, detail = ""] = value.split(":", 2);
  if (kind === "permission") {
    return permissionMetaLabel(detail);
  }
  if (kind === "roles") {
    return `Роли: ${detail || "не указаны"}`;
  }
  if (kind === "consent") {
    return detail === "not_required" ? "Согласие не требуется" : "Требуется согласие";
  }
  if (kind === "retry") {
    return detail === "available" ? "Повтор доступен" : `Повтор: ${operationActionReasonLabel(detail)}`;
  }
  if (kind === "cancel") {
    return detail === "available" ? "Отмена доступна" : `Отмена: ${operationActionReasonLabel(detail)}`;
  }
  if (kind === "install") {
    return detail === "required" ? "Нужна установка модуля" : `Установка: ${humanizeCode(detail)}`;
  }
  return humanizeCode(value);
}

