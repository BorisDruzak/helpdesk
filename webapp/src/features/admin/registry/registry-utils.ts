import type { AdminRegistryPayload } from "../api";

export type RegistryTabKey =
  | "overview"
  | "devices"
  | "people"
  | "bindings"
  | "requests"
  | "account_sessions"
  | "quality"
  | "locations"
  | "departments"
  | "access_groups"
  | "audience_groups"
  | "policies";

export type RegistrySelection =
  | { kind: "device"; id: string }
  | { kind: "person"; id: string }
  | { kind: "binding"; id: string }
  | { kind: "session"; id: string }
  | { kind: "claim"; id: string }
  | null;

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function statusTone(value: string | null | undefined): "brand" | "danger" | "info" | "neutral" | "success" | "warning" {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (["active", "verified", "admin_confirmed", "approved"].includes(normalized)) {
    return "success";
  }
  if (["pending", "self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "pending_verification"].includes(normalized)) {
    return "warning";
  }
  if (["conflict", "rejected", "revoked", "expired", "stale"].includes(normalized)) {
    return "danger";
  }
  if (normalized === "agent") {
    return "brand";
  }
  if (normalized) {
    return "info";
  }
  return "neutral";
}

const STATUS_LABELS: Record<string, string> = {
  active: "Активно",
  admin_confirmed: "Подтверждено администратором",
  approved: "Одобрено",
  conflict: "Конфликт",
  disabled: "Отключено",
  expired: "Истекло",
  inactive: "Неактивно",
  pending: "Ожидает",
  pending_admin_review: "На проверке администратора",
  pending_user_confirmation: "Ждет подтверждения пользователя",
  pending_verification: "Ждет проверки",
  rejected: "Отклонено",
  revoked: "Отозвано",
  self_reported: "Заявлено пользователем",
  stale: "Устарело",
  superseded: "Заменено",
  transferred: "Передано",
  unregistered: "Не зарегистрировано",
  user_confirmed: "Подтверждено пользователем",
  verified: "Проверено",
};

const RELATIONSHIP_LABELS: Record<string, string> = {
  primary_user: "Основной пользователь",
  shared_user: "Совместный пользователь",
  responsible: "Ответственный",
  temporary_user: "Временный пользователь",
};

const ACCOUNT_MODE_LABELS: Record<string, string> = {
  confirmed_binding: "Подтвержденная привязка",
  other_account: "Другой аккаунт",
  registration_pending: "Ожидание регистрации",
  verified_other_account: "Проверенный другой аккаунт",
};

const VERIFICATION_METHOD_LABELS: Record<string, string> = {
  admin: "Администратор",
  admin_review: "Проверка администратором",
  agent_profile: "Профиль агента",
  confirmed_binding: "Подтвержденная привязка",
  registration_claim: "Заявка регистрации",
  user_confirmed: "Подтверждение пользователя",
};

const SOURCE_LABELS: Record<string, string> = {
  account: "Аккаунт",
  ad: "Active Directory",
  admin: "Администратор",
  agent: "Агент",
  email: "Email",
  import: "Импорт",
  manual: "Вручную",
  phone: "Телефон",
  registry_admin: "Администратор реестра",
  registration: "Регистрация",
  registration_claim: "Заявка регистрации",
  sync: "Синхронизация",
  ui_login: "UI-аккаунт",
  windows_login: "Windows-логин",
};

const ACTOR_ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  agent: "Агент",
  auditor: "Аудитор",
  support: "Поддержка",
  system: "Система",
  user: "Пользователь",
};

export function registryStatusLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return STATUS_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

export function relationshipTypeLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return RELATIONSHIP_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

export function accountModeLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return ACCOUNT_MODE_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

export function verificationMethodLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return VERIFICATION_METHOD_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

export function registrySourceLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return SOURCE_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

export function actorRoleLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "Не указано";
  }
  return ACTOR_ROLE_LABELS[normalized] ?? normalized.replaceAll("_", " ");
}

const QUALITY_ISSUE_LABELS: Record<string, string> = {
  asset_missing_location: "ПК без локации",
  asset_missing_confirmed_user: "ПК без подтвержденного пользователя",
  registration_pending_confirmation: "Регистрация ожидает подтверждения",
  registration_conflict: "Конфликт регистрации",
  binding_stale: "Привязка регистрации устарела",
  binding_inactive_person: "Активная привязка ведет к неактивному пользователю",
  presence_user_mismatch: "Пользователь ОС отличается от активной привязки",
  location_pending_confirmation: "Локация ожидает подтверждения",
  person_archived_department: "Пользователь привязан к архивному подразделению",
  person_archived_location: "Пользователь привязан к архивной локации",
  ui_user_unlinked_registry_person: "UI-пользователь не связан с персоной реестра",
  missing_identity: "У персоны нет идентификатора",
  duplicate_person: "Возможные дубликаты персон",
  audience_group_empty: "Аудиторная группа без участников",
  knowledge_audience_rule_invalid_target: "Правило видимости Knowledge с недействительной целью",
  knowledge_audience_zero_users: "Статья Knowledge доступна нулю пользователей",
};

const QUALITY_SUGGESTION_LABELS: Record<string, string> = {
  hostname_person_link: "Найдена связь ПК и пользователя",
};

function issueObjectLabel(issue: AdminRegistryPayload["data_quality"][number]): string {
  const extra = issue as Record<string, unknown>;
  const details = typeof extra.details === "string" ? extra.details : undefined;
  const value = issue.description ?? details ?? issue.device_id ?? issue.person_id ?? issue.binding_id ?? issue.claim_id ?? issue.object_id;
  if (!value) {
    return "Связанный объект не указан";
  }
  if (issue.device_id) {
    return `Устройство: ${value}`;
  }
  if (issue.person_id) {
    return `Пользователь: ${value}`;
  }
  if (issue.binding_id) {
    return `Привязка: ${value}`;
  }
  if (issue.claim_id) {
    return `Заявка: ${value}`;
  }
  if (issue.object_type === "ui_user") {
    return `UI-аккаунт: ${value}`;
  }
  if (issue.object_type === "audience_group") {
    return `Аудиторная группа: ${value}`;
  }
  if (issue.object_type === "knowledge_audience_rule") {
    return `Правило: ${value}`;
  }
  if (issue.object_type === "knowledge_item") {
    return `Материал: ${value}`;
  }
  return String(value);
}

export function qualityIssueTitle(issue: AdminRegistryPayload["data_quality"][number]): string {
  return QUALITY_ISSUE_LABELS[String(issue.kind ?? "").trim()] ?? issue.kind.replaceAll("_", " ");
}

export function qualityIssueDescription(issue: AdminRegistryPayload["data_quality"][number]): string {
  return issueObjectLabel(issue);
}

export function qualitySuggestionTitle(suggestion: AdminRegistryPayload["suggestions"][number]): string {
  return QUALITY_SUGGESTION_LABELS[String(suggestion.kind ?? "").trim()] ?? suggestion.kind.replaceAll("_", " ");
}

export function qualitySuggestionDescription(suggestion: AdminRegistryPayload["suggestions"][number]): string {
  const extra = suggestion as Record<string, unknown>;
  const details = typeof extra.details === "string" ? extra.details : undefined;
  return String(suggestion.description ?? details ?? suggestion.object_id ?? "Связанный объект не указан");
}

export function filterRegistryPayload(value: AdminRegistryPayload, query: string): AdminRegistryPayload {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return value;
  }
  const includes = (...parts: Array<string | number | null | undefined>) =>
    parts.filter((part) => part !== null && part !== undefined).join(" ").toLowerCase().includes(normalized);
  return {
    ...value,
    assets: value.assets.filter((asset) =>
      includes(asset.name, asset.hostname, asset.device_id, asset.owner_name, asset.active_person_name, asset.department_name, asset.location_name, asset.active_binding_id)
    ),
    people: value.people.filter((person) =>
      includes(person.display_name, person.full_name, person.login, person.phone, person.email, person.department_name, person.location_name, person.person_id)
      || (value.ui_users ?? []).some((user) => user.linked_person_id === person.person_id && includes(user.user_login, user.actor_role))
    ),
    registration_claims: value.registration_claims.filter((claim) =>
      includes(claim.claim_id, claim.device_id, claim.person_name, claim.person_id, claim.status, claim.relationship_type, claim.conflict_reason)
    ),
    active_bindings: value.active_bindings.filter((binding) =>
      includes(binding.binding_id, binding.device_id, binding.hostname, binding.person_id, binding.person_name, binding.relationship_type, binding.status)
    ),
    bindings: (value.bindings ?? value.active_bindings).filter((binding) =>
      includes(binding.binding_id, binding.device_id, binding.hostname, binding.person_id, binding.person_name, binding.relationship_type, binding.status)
    ),
    account_sessions: (value.account_sessions ?? []).filter((session) =>
      includes(session.session_id, session.device_id, session.person_id, session.display_name, session.login, session.account_mode, session.verification_status, session.base_binding_id)
    ),
    account_login_requests: (value.account_login_requests ?? []).filter((request) =>
      includes(request.request_id, request.device_id, request.matched_person_id, request.base_binding_id, request.status, String(request.requested_account?.login ?? ""))
    ),
    ui_users: (value.ui_users ?? []).filter((user) =>
      includes(user.user_login, user.actor_role, user.linked_person_id, user.linked_person_name)
    ),
    locations: value.locations.filter((location) => includes(location.display_name, location.building, location.floor, location.room)),
    departments: value.departments.filter((department) => includes(department.name, department.code)),
    services: value.services.filter((service) => includes(service.name, service.code, service.support_queue)),
    vendors: value.vendors.filter((vendor) => includes(vendor.name, vendor.code, vendor.contact_name, vendor.phone, vendor.email)),
    data_quality: value.data_quality.filter((issue) =>
      includes(issue.kind, issue.title, issue.description, issue.object_id, issue.device_id, issue.person_id, issue.binding_id, issue.claim_id)
    ),
  };
}
