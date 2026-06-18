import { CheckCircle2, KeyRound, Link2, Monitor, Paperclip, RefreshCw, RotateCcw, Send, Star, X } from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  approveRequesterConsent,
  closeRequesterTicket,
  claimPublicRequesterTicket,
  createRequesterTicket,
  denyRequesterConsent,
  fetchPublicFormPack,
  fetchRequesterBootstrap,
  fetchRequesterConsents,
  fetchRequesterDevice,
  fetchRequesterProfile,
  fetchRequesterRegistryOptions,
  fetchRequesterTicket,
  fetchRequesterTickets,
  fetchServiceCatalogCurrent,
  previewRequesterTicket,
  recordKnowledgeFeedback,
  reopenRequesterTicket,
  RequesterApiError,
  searchRequesterOnBehalfPeople,
  sendRequesterTicketMessage,
  suggestKnowledge,
  submitRequesterTicketFeedback,
  updateRequesterProfile,
  uploadRequesterTicketAttachment,
} from "../../features/requester/api";
import {
  confirmDevicePairing,
  DevicePairingApiError,
  fetchDevicePairing,
  lookupDevicePairingCode,
  type DevicePairingPayload,
} from "../device-pairing/api";
import type {
  AuthenticatedRequesterTicket,
  KnowledgeAttempt,
  KnowledgeSuggestResult,
  KnowledgeSuggestionItem,
  RequestFormAvailabilityPolicy,
  RequestFormDefinition,
  RequestFormField,
  RequesterBootstrap,
  RequesterConsent,
  RequesterContextPreview,
  RequesterDevice,
  RequesterDeviceDetail,
  RequesterOnBehalfPerson,
  RequesterPendingRegistrationClaim,
  RequesterProfile,
  RequesterProfileDetail,
  RequesterProfileSchemaField,
  RequesterRegistryOption,
  RequesterTicketCreatePayload,
  RequesterTicketDetail,
  ServiceCatalogCurrent,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";

type FieldValues = Record<string, string | boolean>;
const ASK_TICKET_CONTEXT_STORAGE_KEY = "pc_client.knowledge_ask.ticket_context";
const ASK_TICKET_CONTEXT_MAX_AGE_MS = 30 * 60 * 1000;

type ProfileFormState = {
  full_name: string;
  department_id: string;
  location_id: string;
  phone: string;
  position: string;
  workplace_label: string;
  preferred_contact_method: string;
  custom_fields: Record<string, string | boolean>;
};

const EMPTY_PROFILE_FORM: ProfileFormState = {
  full_name: "",
  department_id: "",
  location_id: "",
  phone: "",
  position: "",
  workplace_label: "",
  preferred_contact_method: "",
  custom_fields: {},
};

type AskTicketContext = {
  source?: string;
  query?: string | null;
  created_at?: string | null;
  answer_status?: string | null;
  effective_mode?: string | null;
  ai_used?: boolean | null;
  audit_id?: string | null;
  primary_item?: {
    item_id?: string | null;
    version_id?: string | null;
    slug?: string | null;
    title?: string | null;
    chunk_id?: string | null;
    segment_id?: string | null;
    score?: number | null;
  } | null;
  retrieval_results?: Array<{
    item_id?: string | null;
    version_id?: string | null;
    slug?: string | null;
    title?: string | null;
    chunk_id?: string | null;
    segment_id?: string | null;
    score?: number | null;
  }>;
};

function profileFormFrom(profile?: RequesterProfile | null): ProfileFormState {
  return {
    full_name: profile?.full_name || profile?.display_name || "",
    department_id: profile?.department_id || "",
    location_id: profile?.location_id || "",
    phone: profile?.phone || "",
    position: profile?.position || "",
    workplace_label: profile?.workplace_label || "",
    preferred_contact_method: profile?.preferred_contact_method || "",
    custom_fields: Object.fromEntries(
      Object.entries(profile?.custom_fields ?? {}).map(([key, value]) => [key, typeof value === "boolean" ? value : String(value ?? "")]),
    ),
  };
}

type PendingAttachment = {
  artifact_id: string;
  name: string;
  url?: string | null;
  mime_type?: string | null;
  kind?: string | null;
};

function compactText(value: unknown, maxLength = 160): string {
  return String(value ?? "").trim().replace(/\s+/g, " ").slice(0, maxLength);
}

function readAskTicketContext(): AskTicketContext | null {
  if (typeof window === "undefined" || !window.location.pathname.endsWith("/requester/new")) {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    window.sessionStorage.removeItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
    const parsed = JSON.parse(raw) as AskTicketContext;
    const createdAt = parsed?.created_at ? Date.parse(parsed.created_at) : Number.NaN;
    const isFresh = Number.isNaN(createdAt) || Date.now() - createdAt <= ASK_TICKET_CONTEXT_MAX_AGE_MS;
    return parsed?.source === "knowledge_ask" && compactText(parsed.query) && isFresh ? parsed : null;
  } catch {
    window.sessionStorage.removeItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
    return null;
  }
}

function askContextTitle(context: AskTicketContext): string {
  return `Запрос из базы знаний: ${compactText(context.query, 80) || "без темы"}`;
}

function askAnswerStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    answered: "Ответ найден",
    ai_disabled: "AI отключен",
    no_answer: "Ответ не найден",
    partial: "Ответ требует проверки",
  };
  return labels[value || ""] || compactText(value, 80) || "Не указан";
}

function askSearchModeLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    hybrid: "Гибридный поиск",
    keyword_only: "Поиск по ключевым словам",
    vector: "Векторный поиск",
  };
  return labels[value || ""] || compactText(value, 80) || "Не указан";
}

function askContextDescription(context: AskTicketContext): string {
  const lines = [
    `Вопрос в базе знаний: ${compactText(context.query, 500)}`,
    context.answer_status ? `Статус ответа: ${askAnswerStatusLabel(context.answer_status)}` : null,
    context.effective_mode ? `Режим поиска: ${askSearchModeLabel(context.effective_mode)}` : null,
    context.primary_item?.title ? `Подобранная статья: ${compactText(context.primary_item.title, 240)}` : null,
  ].filter(Boolean);
  return lines.join("\n");
}

function askContextAttempts(context: AskTicketContext): KnowledgeAttempt[] {
  const now = new Date().toISOString();
  const sourceItems = context.primary_item?.item_id ? [context.primary_item, ...(context.retrieval_results ?? [])] : context.retrieval_results ?? [];
  const seen = new Set<string>();
  return sourceItems
    .map((item) => ({
      item_id: compactText(item?.item_id, 120),
      version_id: compactText(item?.version_id, 120) || null,
      result: "ticket_created_after_view" as const,
      surface: "requester_portal" as const,
      timestamp: now,
    }))
    .filter((attempt) => {
      if (!attempt.item_id || seen.has(attempt.item_id)) {
        return false;
      }
      seen.add(attempt.item_id);
      return true;
    })
    .slice(0, 5);
}

function deviceLabel(device: RequesterDevice): string {
  return device.hostname || device.asset_name || device.device_id;
}

function pairingDeviceLabel(pairing: DevicePairingPayload): string {
  return pairing.device?.hostname || pairing.device?.device_id || "Устройство";
}

function registrationStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    active: "Устройство привязано",
    admin_confirmed: "Устройство привязано",
    approved: "Устройство привязано",
    conflict: "Требуется проверка администратора",
    pending_admin_review: "Ожидает проверки администратора",
    pending_user_confirmation: "Ожидает подтверждения",
    pending_verification: "Ожидает проверки",
    rejected: "Отклонено администратором",
    user_confirmed: "Ожидает проверки администратора",
  };
  return labels[value || ""] || "Статус уточняется";
}

function pendingDeviceLinkStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    conflict: "Требуется проверка администратора",
    pending_admin_review: "Ожидает проверки администратора",
    pending_user_confirmation: "Ожидает подтверждения пользователя",
    self_reported: "Ожидает подтверждения",
    user_confirmed: "Ожидает проверки администратора",
  };
  return labels[value || ""] || "Статус уточняется";
}

function pendingDeviceLinkLabel(claim: RequesterPendingRegistrationClaim): string {
  const deviceId = compactText(claim.device_id, 80);
  return deviceId ? `Устройство ${deviceId}` : "Устройство";
}

function formatSubmittedAt(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return compactText(value, 80) || null;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function isSafeAppNextPath(value: string | null) {
  return Boolean(value && (value === "/app" || value.startsWith("/app/")) && !value.startsWith("//"));
}

function currentBrowserAppPath() {
  if (typeof window === "undefined") {
    return "/app/requester";
  }
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function profileSetupNextPath(fallbackPath = "/app/requester") {
  if (typeof window === "undefined") {
    return fallbackPath;
  }
  const nextParam = new URLSearchParams(window.location.search).get("next");
  return isSafeAppNextPath(nextParam) ? (nextParam as string) : fallbackPath;
}

function profileSetupRegisterPath() {
  const params = new URLSearchParams({
    switch_account: "1",
    next: profileSetupNextPath(currentBrowserAppPath()),
  });
  return `/app/register?${params.toString()}`;
}

function agentVersionLabel(value?: string | null): string {
  const version = String(value ?? "").trim();
  return version ? `Агент ${version}` : "Версия агента не указана";
}

function deviceSystemLabel(os?: string | null, agentVersion?: string | null): string {
  return `${os || "Система не указана"} · ${agentVersionLabel(agentVersion)}`;
}

function relationshipLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    primary_user: "Основной пользователь",
    responsible: "Ответственный",
    owner: "Владелец",
    shared_user: "Общий доступ",
    temporary_user: "Временный пользователь",
  };
  return labels[value || ""] || value || "Связь не указана";
}

function bindingStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    active: "Привязка активна",
    admin_confirmed: "Подтверждено администратором",
    approved: "Подтверждено",
    expired: "Истекла",
    pending: "Ожидает подтверждения",
    pending_admin_review: "Ожидает проверки администратора",
    pending_user_confirmation: "Ожидает подтверждения пользователя",
    rejected: "Отклонена",
    revoked: "Отозвана",
    transferred: "Передана",
    user_confirmed: "Подтверждена пользователем",
  };
  return labels[value || ""] || "Статус привязки уточняется";
}

function deviceOnlineLabel(value?: boolean | null): string {
  if (value === true) {
    return "В сети";
  }
  if (value === false) {
    return "Не в сети";
  }
  return "Статус сети не указан";
}

function ticketStatus(ticket: AuthenticatedRequesterTicket): string {
  return ticket.requester_status_label || ticket.status_label || ticket.requester_status || ticket.status || "open";
}

function consentRiskLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    diagnostic: "Диагностика",
    remote_view: "Просмотр экрана",
    remote_control: "Удаленное управление",
    remote_admin: "Административный доступ",
  };
  return labels[value || ""] || value || "Требуется решение";
}

function consentSubjectLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    diagnostic: "Диагностика",
    operation: "Операция",
    remote_assist: "Удаленная помощь",
    tool_run: "Запуск инструмента",
  };
  return labels[value || ""] || value || "Запрос согласия";
}

function formatConsentExpiresAt(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function isFieldVisible(field: RequestFormField, values: FieldValues): boolean {
  const rule = field.visible_when;
  if (!rule?.field) {
    return true;
  }
  const currentValue = values[rule.field];
  if (Object.prototype.hasOwnProperty.call(rule, "equals")) {
    return String(currentValue ?? "").trim() === String(rule.equals ?? "").trim();
  }
  if (Array.isArray(rule.in)) {
    return rule.in.map((item) => String(item ?? "").trim()).includes(String(currentValue ?? "").trim());
  }
  return true;
}

function compactPrefillValue(value: unknown): string | boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }
  const text = String(value ?? "").trim();
  return text ? text : undefined;
}

function requesterFormPrefillFromContext(
  context: RequesterContextPreview | null | undefined,
  profile: RequesterProfile | null | undefined,
  selectedDevice: RequesterDevice | null,
  selectedService: ServiceCatalogCurrent["services"][number] | null,
  selectedOffering: ServiceCatalogCurrent["services"][number]["offerings"][number] | null,
): FieldValues {
  const next: FieldValues = {};
  Object.entries(context?.form_prefill ?? {}).forEach(([key, value]) => {
    const normalized = compactPrefillValue(value);
    if (normalized !== undefined) {
      next[key] = normalized;
    }
  });
  const profileValues: Record<string, unknown> = {
    requester_name: profile?.full_name || profile?.display_name,
    full_name: profile?.full_name || profile?.display_name,
    email: profile?.email,
    phone: profile?.phone,
    department_id: profile?.department_id,
    location_id: profile?.location_id,
    position: profile?.position,
    workplace_label: profile?.workplace_label,
  };
  Object.entries(profileValues).forEach(([key, value]) => {
    const normalized = compactPrefillValue(value);
    if (normalized !== undefined) {
      next[key] = normalized;
    }
  });
  if (selectedDevice) {
    next.device_id = selectedDevice.device_id;
    next.device = deviceLabel(selectedDevice);
    if (selectedDevice.hostname) {
      next.hostname = selectedDevice.hostname;
      next.device_hostname = selectedDevice.hostname;
    }
    if (selectedDevice.asset_id) {
      next.asset_id = selectedDevice.asset_id;
    }
    if (selectedDevice.asset_name) {
      next.asset = selectedDevice.asset_name;
    }
    if (selectedDevice.asset_type) {
      next.asset_type = selectedDevice.asset_type;
    }
    if (selectedDevice.department_id) {
      next.device_department_id = selectedDevice.department_id;
    }
    if (selectedDevice.location_id) {
      next.device_location_id = selectedDevice.location_id;
    }
  }
  if (selectedService) {
    next.service_code = selectedService.service_code;
    next.service = selectedService.title || selectedService.service_code;
  }
  if (selectedOffering) {
    next.offering_code = selectedOffering.offering_code;
    next.offering_full_code = selectedOffering.full_code;
    next.offering = selectedOffering.title || selectedOffering.full_code;
    if (selectedOffering.request_template_key) {
      next.request_template_key = selectedOffering.request_template_key;
    }
  }
  return next;
}

function prefillKeysForField(field: RequestFormField): string[] {
  const key = field.key.toLowerCase();
  const candidates = [field.key];
  if (field.type === "department_picker" || key.includes("department")) {
    candidates.push(key.endsWith("_id") ? "department_id" : "department", "department_id", "department_code");
  }
  if (field.type === "location_picker" || key.includes("location") || key === "building" || key === "room") {
    candidates.push(field.key, key.endsWith("_id") ? "location_id" : "location", "location_id", "building", "room");
  }
  if (field.type === "device_picker" || key.includes("device") || key === "hostname") {
    candidates.push(key.endsWith("_id") ? "device_id" : "device", "device_id", "device_hostname", "hostname");
  }
  if (field.type === "service_picker" || key.includes("service") || key.includes("offering")) {
    candidates.push(key.includes("offering") ? "offering_full_code" : "service_code", "service", "offering");
  }
  if (key.includes("phone")) {
    candidates.push("phone");
  }
  if (key.includes("email")) {
    candidates.push("email");
  }
  if (key.includes("name") || key.includes("requester")) {
    candidates.push("requester_name", "full_name");
  }
  return Array.from(new Set(candidates));
}

function prefillValueForField(field: RequestFormField, prefill: FieldValues): string | boolean | undefined {
  for (const key of prefillKeysForField(field)) {
    const value = prefill[key];
    if (value !== undefined && value !== "") {
      return value;
    }
  }
  return undefined;
}

function buildDefaultFieldValues(form: RequestFormDefinition | null, prefill: FieldValues = {}): FieldValues {
  const nextValues: FieldValues = {};
  for (const field of form?.fields ?? []) {
    const prefilled = prefillValueForField(field, prefill);
    nextValues[field.key] = field.type === "checkbox" ? prefilled === true : typeof prefilled === "boolean" ? "" : prefilled ?? "";
  }
  return nextValues;
}

function mergeContextPrefillValues(
  form: RequestFormDefinition | null,
  current: FieldValues,
  previousPrefill: FieldValues,
  nextPrefill: FieldValues,
): FieldValues {
  const defaults = buildDefaultFieldValues(form, nextPrefill);
  const next: FieldValues = {};
  for (const field of form?.fields ?? []) {
    const currentValue = current[field.key];
    const previousValue = previousPrefill[field.key];
    const defaultValue = defaults[field.key] ?? (field.type === "checkbox" ? false : "");
    const isEmpty = field.type === "checkbox" ? currentValue === undefined : !String(currentValue ?? "").trim();
    const stillPrevious = currentValue !== undefined && String(currentValue) === String(previousValue ?? "");
    next[field.key] = isEmpty || stillPrevious ? defaultValue : currentValue;
  }
  return next;
}

function uniqueOptions(options: RequesterRegistryOption[]): RequesterRegistryOption[] {
  const seen = new Set<string>();
  const result: RequesterRegistryOption[] = [];
  for (const option of options) {
    const value = String(option.value || "").trim();
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    result.push({ value, label: option.label || value });
  }
  return result;
}

function fieldWithRequesterContextOptions(
  field: RequestFormField,
  context: {
  departments: RequesterRegistryOption[];
  locations: RequesterRegistryOption[];
  devices: RequesterDevice[];
  services: ServiceCatalogCurrent["services"];
  },
): RequestFormField {
  const { departments, devices, locations, services } = context;
  if (field.type === "department_picker") {
    return { ...field, options: uniqueOptions([...(field.options ?? []), ...departments]) };
  }
  if (field.type === "location_picker") {
    return { ...field, options: uniqueOptions([...(field.options ?? []), ...locations]) };
  }
  if (field.type === "device_picker") {
    return {
      ...field,
      options: uniqueOptions([
        ...(field.options ?? []),
        ...devices.map((device) => ({ value: device.device_id, label: deviceLabel(device) })),
      ]),
    };
  }
  if (field.type === "service_picker") {
    return {
      ...field,
      options: uniqueOptions([
        ...(field.options ?? []),
        ...services.map((service) => ({ value: service.service_code, label: service.title || service.service_code })),
      ]),
    };
  }
  return field;
}

function collectVisiblePayload(form: RequestFormDefinition | null, values: FieldValues): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of form?.fields ?? []) {
    if (isFieldVisible(field, values)) {
      payload[field.key] = values[field.key] ?? (field.type === "checkbox" ? false : "");
    }
  }
  return payload;
}

function onBehalfPersonLabel(person: RequesterOnBehalfPerson): string {
  return person.display_name || person.full_name || person.email || "Сотрудник";
}

function onBehalfPrimaryAgentMissing(person: RequesterOnBehalfPerson | null): boolean {
  const status = String(person?.primary_agent?.status || "").trim();
  return status === "missing" || status === "ambiguous";
}

function formAvailabilityPolicy(form: RequestFormDefinition | null | undefined): Required<RequestFormAvailabilityPolicy> {
  const raw = form?.availability_policy ?? {};
  return {
    available_without_completed_profile: Boolean(
      form?.available_without_completed_profile ?? raw.available_without_completed_profile,
    ),
    available_without_agent_binding: Boolean(form?.available_without_agent_binding ?? raw.available_without_agent_binding),
    requires_manual_triage: Boolean(form?.requires_manual_triage ?? raw.requires_manual_triage),
    contact_required: Boolean(form?.contact_required ?? raw.contact_required),
    allowed_for_anonymous: Boolean(form?.allowed_for_anonymous ?? raw.allowed_for_anonymous),
  };
}

function formVisibleForRequester(form: RequestFormDefinition, profileGateActive: boolean, hasAgentContext: boolean): boolean {
  const availability = formAvailabilityPolicy(form);
  if (profileGateActive && !availability.available_without_completed_profile) {
    return false;
  }
  if (!hasAgentContext && !availability.available_without_agent_binding && !form.on_behalf_policy?.allowed) {
    return false;
  }
  return true;
}

function missingRequiredFields(form: RequestFormDefinition | null, values: FieldValues): string[] {
  return (form?.fields ?? [])
    .filter((field) => field.required && isFieldVisible(field, values))
    .filter((field) => {
      const value = values[field.key];
      return field.type === "checkbox" ? value !== true : !String(value ?? "").trim();
    })
    .map((field) => field.label || field.key);
}

function visibleKnowledgeSuggestions(
  suggestions: KnowledgeSuggestionItem[],
  rollout?: KnowledgeSuggestResult["rollout"] | null,
): KnowledgeSuggestionItem[] {
  return suggestions
    .filter((item) => rollout?.show_known_errors !== false || item.type !== "known_error")
    .map((item) => {
      const next = { ...item };
      if (rollout?.show_quality_badge === false) {
        delete next.quality_label;
      }
      if (rollout?.show_review_freshness === false) {
        delete next.freshness_label;
      }
      return next;
    });
}

function RequestFormFieldControl({
  field,
  onChange,
  value,
}: {
  field: RequestFormField;
  onChange: (value: string | boolean) => void;
  value: string | boolean;
}) {
  const label = `${field.label || field.key}${field.required ? " *" : ""}`;
  const selectLike =
    field.type === "select" ||
    field.type === "radio" ||
    field.type === "department_picker" ||
    field.type === "location_picker" ||
    field.type === "device_picker" ||
    field.type === "service_picker" ||
    field.type === "user_picker";
  if (field.type === "textarea") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <textarea
          aria-label={`Поле формы обращения ${field.key}`}
          className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder={field.placeholder ?? ""}
          value={String(value ?? "")}
        />
      </label>
    );
  }
  if (selectLike) {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <select
          aria-label={`Поле формы обращения ${field.key}`}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          value={String(value ?? "")}
        >
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label || option.value}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
        <input
          aria-label={`Поле формы обращения ${field.key}`}
          checked={value === true}
          onChange={(event) => onChange(event.currentTarget.checked)}
          type="checkbox"
        />
        <span>{label}</span>
      </label>
    );
  }
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <input
        aria-label={`Поле формы обращения ${field.key}`}
        className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={field.placeholder ?? ""}
        type={
          field.type === "number" ? "number" :
          field.type === "date" ? "date" :
          field.type === "datetime" ? "datetime-local" :
          field.type === "email" ? "email" :
          field.type === "url" ? "url" :
          field.type === "phone" ? "tel" :
          "text"
        }
        value={String(value ?? "")}
      />
    </label>
  );
}

function schemaOptionValue(option: string | { value: string; label: string }): { label: string; value: string } {
  return typeof option === "string" ? { label: option, value: option } : option;
}

function ProfileCustomFieldControl({
  field,
  onChange,
  value,
}: {
  field: RequesterProfileSchemaField;
  onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
  value: string | boolean;
}) {
  const label = `${field.label || field.key}${field.required ? " *" : ""}`;
  const helpText = field.help_text ? <span className="mt-1 block text-xs font-normal text-slate-500">{field.help_text}</span> : null;
  if (field.type === "textarea") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <textarea
          aria-label={field.label || field.key}
          className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={onChange}
          value={String(value ?? "")}
        />
        {helpText}
      </label>
    );
  }
  if (field.type === "select") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <select
          aria-label={field.label || field.key}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={onChange}
          value={String(value ?? "")}
        >
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => {
            const normalized = schemaOptionValue(option);
            return <option key={normalized.value} value={normalized.value}>{normalized.label || normalized.value}</option>;
          })}
        </select>
        {helpText}
      </label>
    );
  }
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
        <input
          aria-label={field.label || field.key}
          checked={value === true}
          onChange={onChange}
          type="checkbox"
        />
        <span>{label}</span>
        {helpText}
      </label>
    );
  }
  const inputType =
    field.type === "number" ? "number" :
    field.type === "date" ? "date" :
    field.type === "email" ? "email" :
    field.type === "url" ? "url" :
    field.type === "phone" ? "tel" :
    "text";
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <input
        aria-label={field.label || field.key}
        className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
        onChange={onChange}
        type={inputType}
        value={String(value ?? "")}
      />
      {helpText}
    </label>
  );
}

export function RequesterWorkspacePage() {
  const [bootstrap, setBootstrap] = useState<RequesterBootstrap | null>(null);
  const [tickets, setTickets] = useState<AuthenticatedRequesterTicket[]>([]);
  const [consents, setConsents] = useState<RequesterConsent[]>([]);
  const [consentSubmittingId, setConsentSubmittingId] = useState<string | null>(null);
  const [consentNotice, setConsentNotice] = useState<string | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [title, setTitle] = useState("Проверка рабочего места");
  const [description, setDescription] = useState("");
  const [catalog, setCatalog] = useState<ServiceCatalogCurrent | null>(null);
  const [forms, setForms] = useState<RequestFormDefinition[]>([]);
  const [formPackMeta, setFormPackMeta] = useState<{ pack_key: string; version: string } | null>(null);
  const [selectedServiceCode, setSelectedServiceCode] = useState("");
  const [selectedOfferingFullCode, setSelectedOfferingFullCode] = useState("");
  const [selectedFormKey, setSelectedFormKey] = useState("");
  const [fieldValues, setFieldValues] = useState<FieldValues>({});
  const [onBehalfEnabled, setOnBehalfEnabled] = useState(false);
  const [onBehalfQuery, setOnBehalfQuery] = useState("");
  const [onBehalfPeople, setOnBehalfPeople] = useState<RequesterOnBehalfPerson[]>([]);
  const [onBehalfSelectedPersonId, setOnBehalfSelectedPersonId] = useState("");
  const [onBehalfReason, setOnBehalfReason] = useState("");
  const [onBehalfSearchLoading, setOnBehalfSearchLoading] = useState(false);
  const [onBehalfSearchError, setOnBehalfSearchError] = useState<string | null>(null);
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<ServiceCatalogSafePreview | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [previewSubmitting, setPreviewSubmitting] = useState(false);
  const [knowledgeResult, setKnowledgeResult] = useState<KnowledgeSuggestResult | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState(false);
  const [openedKnowledgeId, setOpenedKnowledgeId] = useState<string | null>(null);
  const [knowledgeAttempts, setKnowledgeAttempts] = useState<KnowledgeAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTicketId, setCreatedTicketId] = useState<string | null>(null);
  const [selectedDeviceDetail, setSelectedDeviceDetail] = useState<RequesterDeviceDetail | null>(null);
  const [deviceDetailLoading, setDeviceDetailLoading] = useState(false);
  const [deviceDetailError, setDeviceDetailError] = useState<string | null>(null);
  const [deviceLinkCode, setDeviceLinkCode] = useState("");
  const [deviceLinkPairing, setDeviceLinkPairing] = useState<DevicePairingPayload | null>(null);
  const [deviceLinkLoading, setDeviceLinkLoading] = useState(false);
  const [deviceLinkConfirming, setDeviceLinkConfirming] = useState(false);
  const [deviceLinkNotice, setDeviceLinkNotice] = useState<string | null>(null);
  const [deviceLinkError, setDeviceLinkError] = useState<string | null>(null);
  const [profileDetail, setProfileDetail] = useState<RequesterProfileDetail | null>(null);
  const [profileDetailLoading, setProfileDetailLoading] = useState(false);
  const [profileDetailError, setProfileDetailError] = useState<string | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileFormState>(EMPTY_PROFILE_FORM);
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [profileSetupNotice, setProfileSetupNotice] = useState<string | null>(null);
  const [profileOptionsLoading, setProfileOptionsLoading] = useState(false);
  const [profileOptionsError, setProfileOptionsError] = useState<string | null>(null);
  const [departmentOptions, setDepartmentOptions] = useState<RequesterRegistryOption[]>([]);
  const [locationOptions, setLocationOptions] = useState<RequesterRegistryOption[]>([]);
  const [claimTicketId, setClaimTicketId] = useState("");
  const [claimCode, setClaimCode] = useState("");
  const [claimSubmitting, setClaimSubmitting] = useState(false);
  const [claimNotice, setClaimNotice] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetail, setSelectedTicketDetail] = useState<RequesterTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messageText, setMessageText] = useState("");
  const [messageSending, setMessageSending] = useState(false);
  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [messageNotice, setMessageNotice] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(5);
  const [feedbackProblemResolved, setFeedbackProblemResolved] = useState(true);
  const [feedbackReason, setFeedbackReason] = useState("not_resolved");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackId, setFeedbackId] = useState<string | null>(null);
  const [reopenReason, setReopenReason] = useState("not_resolved");
  const [reopenComment, setReopenComment] = useState("");
  const [reopenAvailable, setReopenAvailable] = useState(false);
  const attachmentInputRef = useRef<HTMLInputElement | null>(null);
  const askPrefillAppliedRef = useRef(false);
  const directPairingLoadedRef = useRef(false);
  const previousContextPrefillRef = useRef<FieldValues>({});

  useEffect(() => {
    if (askPrefillAppliedRef.current) {
      return;
    }
    const context = readAskTicketContext();
    if (!context) {
      return;
    }
    askPrefillAppliedRef.current = true;
    setTitle((current) => (!current || current === "Проверка рабочего места" ? askContextTitle(context) : current));
    setDescription((current) => current || askContextDescription(context));
    setKnowledgeAttempts((current) => {
      const next = askContextAttempts(context);
      return next.length ? [...current, ...next] : current;
    });
    setCatalogNotice("Контекст из базы знаний добавлен в черновик обращения.");
  }, []);

  const devices = bootstrap?.devices ?? [];
  const visibleTickets = tickets.length ? tickets : bootstrap?.recent_tickets ?? [];
  const pendingConsents = consents.filter((consent) => consent.status === "pending");
  const actionCount = (bootstrap?.tickets_requiring_user_action_count ?? 0) + pendingConsents.length;
  const profileName = bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || bootstrap?.profile?.email || "Пользователь";
  const profileCompletion = bootstrap?.profile_completion;
  const profileBlocks = profileCompletion?.blocks;
  const profileGateActive = profileBlocks
    ? Boolean(profileBlocks.ticket_create || profileBlocks.ticket_preview)
    : profileCompletion?.complete === false;
  const deviceLinkBlocked = Boolean(profileBlocks?.device_binding_confirmation);
  const profileSetupRoute =
    typeof window !== "undefined" && window.location.pathname.endsWith("/requester/profile/setup");
  const profileSetupVisible = profileGateActive || profileSetupRoute;
  const profileSchema = profileDetail?.profile_schema ?? bootstrap?.profile_schema ?? null;
  const profileCustomFields = useMemo(
    () => (profileSchema?.fields ?? []).filter((field) => field.custom && field.visible !== false),
    [profileSchema?.fields],
  );
  const profileSchemaFieldsByKey = useMemo(
    () => new Map((profileSchema?.fields ?? []).map((field) => [field.key, field])),
    [profileSchema?.fields],
  );
  const isProfileFieldVisible = (fieldKey: string) => profileSchemaFieldsByKey.get(fieldKey)?.visible !== false;
  const directDevicePairingId =
    typeof window !== "undefined" && window.location.pathname.endsWith("/requester/devices")
      ? new URLSearchParams(window.location.search).get("pairing_id") || ""
      : "";
  const pendingRegistrationClaims = bootstrap?.pending_registration_claims ?? [];
  const profileDeviceStatus = devices.length
    ? `Привязано устройств: ${devices.length}`
    : pendingRegistrationClaims.length
      ? `Заявок на привязку: ${pendingRegistrationClaims.length}`
      : "Устройства не привязаны";
  const services = catalog?.services ?? [];
  const legacyNoDeviceCreateEnabled = !profileGateActive && bootstrap?.feature_flags?.requester_no_device_create === true;

  const selectedDevice = useMemo(
    () => devices.find((device) => device.device_id === selectedDeviceId) ?? devices[0] ?? null,
    [devices, selectedDeviceId],
  );

  useEffect(() => {
    if (!directDevicePairingId || directPairingLoadedRef.current || loading) {
      return;
    }
    if (deviceLinkBlocked) {
      directPairingLoadedRef.current = true;
      setDeviceLinkError("Сначала заполните профиль, затем привяжите устройство.");
      return;
    }
    directPairingLoadedRef.current = true;
    setDeviceLinkLoading(true);
    setDeviceLinkError(null);
    setDeviceLinkNotice(null);
    void fetchDevicePairing(directDevicePairingId)
      .then((pairing) => {
        if (pairing.purpose !== "registration") {
          setDeviceLinkError("Эта ссылка предназначена для входа на уже привязанном устройстве.");
          return;
        }
        setDeviceLinkPairing(pairing);
        setDeviceLinkNotice("Проверьте устройство и подтвердите привязку.");
      })
      .catch((exc) => {
        setDeviceLinkError(exc instanceof Error ? exc.message : "Не удалось загрузить привязку устройства.");
      })
      .finally(() => setDeviceLinkLoading(false));
  }, [deviceLinkBlocked, directDevicePairingId, loading]);

  const selectedService = useMemo(
    () => services.find((service) => service.service_code === selectedServiceCode) ?? services[0] ?? null,
    [selectedServiceCode, services],
  );
  const selectedOffering = useMemo(
    () =>
      selectedService?.offerings.find((offering) => offering.full_code === selectedOfferingFullCode) ??
      selectedService?.offerings[0] ??
      null,
    [selectedOfferingFullCode, selectedService],
  );
  const visibleForms = useMemo(
    () => forms.filter((form) => formVisibleForRequester(form, profileGateActive, devices.length > 0)),
    [devices.length, forms, profileGateActive],
  );
  const selectedForm = useMemo(
    () => visibleForms.find((form) => form.key === selectedFormKey) ?? visibleForms[0] ?? null,
    [selectedFormKey, visibleForms],
  );
  const selectedAvailability = formAvailabilityPolicy(selectedForm);
  const selectedFormProfileAllowed = !profileGateActive || selectedAvailability.available_without_completed_profile || !selectedForm;
  const selectedOnBehalfPolicy = selectedForm?.on_behalf_policy?.allowed ? selectedForm.on_behalf_policy : null;
  const onBehalfActive = Boolean(selectedOnBehalfPolicy?.allowed && onBehalfEnabled);
  const selectedFormNoAgentAllowed = selectedAvailability.available_without_agent_binding || Boolean(selectedOnBehalfPolicy?.allowed);
  const noDeviceCreateEnabled = selectedForm ? selectedFormNoAgentAllowed : legacyNoDeviceCreateEnabled;
  const selectedOnBehalfPerson = useMemo(
    () => onBehalfPeople.find((person) => person.person_id === onBehalfSelectedPersonId) ?? null,
    [onBehalfPeople, onBehalfSelectedPersonId],
  );
  const onBehalfTicketContext = useMemo(
    () => {
      if (!onBehalfActive || !selectedOnBehalfPerson) {
        return undefined;
      }
      const reason = onBehalfReason.trim();
      const lookup = onBehalfQuery.trim();
      return {
        affected_person_id: selectedOnBehalfPerson.person_id,
        ...(reason ? { on_behalf_reason: reason } : {}),
        ...(lookup ? { affected_person_lookup: lookup } : {}),
      };
    },
    [onBehalfActive, onBehalfQuery, onBehalfReason, selectedOnBehalfPerson],
  );
  const onBehalfMissingRequired = Boolean(
    onBehalfActive && (!selectedOnBehalfPerson || (selectedOnBehalfPolicy?.reason_required && !onBehalfReason.trim())),
  );
  const canCreateForCurrentScope = selectedFormProfileAllowed && (Boolean(selectedDevice) || noDeviceCreateEnabled || onBehalfActive);

  useEffect(() => {
    setOnBehalfEnabled(false);
    setOnBehalfQuery("");
    setOnBehalfPeople([]);
    setOnBehalfSelectedPersonId("");
    setOnBehalfReason("");
    setOnBehalfSearchError(null);
  }, [selectedForm?.key]);

  useEffect(() => {
    setPreviewKey("");
    setPreviewResult(null);
  }, [onBehalfEnabled, onBehalfReason, onBehalfSelectedPersonId]);

  const requestFormContextPrefill = useMemo(
    () =>
      requesterFormPrefillFromContext(
        bootstrap?.requester_context,
        bootstrap?.profile,
        selectedDevice,
        selectedService,
        selectedOffering,
      ),
    [bootstrap?.profile, bootstrap?.requester_context, selectedDevice, selectedOffering, selectedService],
  );
  const requestFormContextPrefillKey = useMemo(
    () => JSON.stringify(requestFormContextPrefill),
    [requestFormContextPrefill],
  );
  const requestFormNeedsRegistryOptions = useMemo(
    () =>
      (selectedForm?.fields ?? []).some((field) =>
        ["department_picker", "location_picker"].includes(field.type) ||
        ["department_id", "location_id", "department", "location"].includes(field.key),
      ),
    [selectedForm],
  );
  const visibleFields = useMemo(
    () => (selectedForm?.fields ?? []).filter((field) => isFieldVisible(field, fieldValues)),
    [fieldValues, selectedForm],
  );
  const contextualVisibleFields = useMemo(
    () =>
      visibleFields.map((field) =>
        fieldWithRequesterContextOptions(field, {
          departments: departmentOptions,
          locations: locationOptions,
          devices,
          services,
        }),
      ),
    [departmentOptions, devices, locationOptions, services, visibleFields],
  );
  const visiblePayload = useMemo(() => collectVisiblePayload(selectedForm, fieldValues), [fieldValues, selectedForm]);
  const knowledgeKey = useMemo(
    () =>
      JSON.stringify({
        service_code: selectedService?.service_code,
        offering_full_code: selectedOffering?.full_code,
        form_key: selectedForm?.key,
        form_payload: visiblePayload,
        device_id: selectedDevice?.device_id,
        description: description.slice(0, 240),
      }),
    [description, selectedDevice?.device_id, selectedForm?.key, selectedOffering?.full_code, selectedService?.service_code, visiblePayload],
  );
  const currentPreviewKey = useMemo(
    () =>
      JSON.stringify({
        device_id: selectedDevice?.device_id,
        service_code: selectedService?.service_code,
        offering_full_code: selectedOffering?.full_code,
        form_key: selectedForm?.key,
        form_payload: visiblePayload,
        ticket_context: onBehalfTicketContext,
        description,
      }),
    [
      description,
      onBehalfTicketContext,
      selectedDevice?.device_id,
      selectedForm?.key,
      selectedOffering?.full_code,
      selectedService?.service_code,
      visiblePayload,
    ],
  );
  const selectedTicket = selectedTicketDetail?.ticket ?? null;
  const selectedTicketStatus = selectedTicket?.status ?? "";
  const canCloseSelectedTicket = selectedTicketStatus === "resolved";
  const canRateSelectedTicket = selectedTicketStatus === "resolved" || selectedTicketStatus === "closed";
  const canReopenSelectedTicket = canRateSelectedTicket && (reopenAvailable || feedbackRating <= 3 || !feedbackProblemResolved);
  const previewIsFresh =
    Boolean(selectedOffering) &&
    previewKey === currentPreviewKey &&
    Boolean(previewResult?.ok) &&
    !(previewResult?.blockers ?? []).length;
  const knowledgeRollout = knowledgeResult?.rollout;
  const knowledgeVisible = Boolean(selectedOffering && knowledgeRollout?.enabled !== false && knowledgeRollout?.show_before_form !== false);
  const knowledgeSuggestions = useMemo(
    () => visibleKnowledgeSuggestions(knowledgeResult?.suggestions ?? [], knowledgeRollout),
    [knowledgeResult?.suggestions, knowledgeRollout],
  );
  const requesterContextSummary = useMemo(
    () =>
      [
        { label: "Профиль", value: profileName },
        { label: "Подразделение", value: bootstrap?.requester_context?.profile?.department },
        { label: "Локация", value: bootstrap?.requester_context?.profile?.location },
        { label: "Устройство", value: selectedDevice ? deviceLabel(selectedDevice) : noDeviceCreateEnabled ? "Без выбранного устройства" : null },
      ].filter((item) => item.value),
    [bootstrap?.requester_context?.profile?.department, bootstrap?.requester_context?.profile?.location, noDeviceCreateEnabled, profileName, selectedDevice],
  );

  async function load() {
    setLoading(true);
    setError(null);
    setCatalogNotice(null);
    try {
      const [nextBootstrap, nextTickets] = await Promise.all([fetchRequesterBootstrap(), fetchRequesterTickets()]);
      setBootstrap(nextBootstrap);
      setProfileForm(profileFormFrom(nextBootstrap.profile));
      setTickets(nextTickets);
      setSelectedDeviceId((current) => current || nextBootstrap.devices[0]?.device_id || "");
      try {
        setConsents(await fetchRequesterConsents());
      } catch {
        setConsents([]);
      }
      try {
        const [nextForms, nextCatalog] = await Promise.all([fetchPublicFormPack(), fetchServiceCatalogCurrent()]);
        setForms(nextForms.forms ?? []);
        setFormPackMeta({ pack_key: nextForms.pack_key, version: nextForms.version });
        setCatalog(nextCatalog);
      } catch {
        setCatalogNotice("Каталог услуг временно недоступен. Можно создать обращение по теме и описанию.");
      }
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить кабинет");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedTicket(ticketId: string) {
    const [nextDetail, nextTickets] = await Promise.all([
      fetchRequesterTicket(ticketId),
      fetchRequesterTickets(),
    ]);
    setSelectedTicketDetail(nextDetail);
    setTickets(nextTickets);
  }

  async function handleConsentDecision(consent: RequesterConsent, decision: "approved" | "denied") {
    setConsentSubmittingId(consent.consent_id);
    setConsentNotice(null);
    setError(null);
    try {
      if (decision === "approved") {
        await approveRequesterConsent(consent.consent_id);
      } else {
        await denyRequesterConsent(consent.consent_id, "requester_denied");
      }
      setConsentNotice(decision === "approved" ? "Согласие подтверждено" : "Согласие отклонено");
      const [nextBootstrap, nextTickets, nextConsents] = await Promise.all([
        fetchRequesterBootstrap(),
        fetchRequesterTickets(),
        fetchRequesterConsents(),
      ]);
      setBootstrap(nextBootstrap);
      setTickets(nextTickets);
      setConsents(nextConsents);
      if (selectedTicketId) {
        setSelectedTicketDetail(await fetchRequesterTicket(selectedTicketId));
      }
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось сохранить решение");
    } finally {
      setConsentSubmittingId(null);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!profileSetupVisible && !requestFormNeedsRegistryOptions) {
      return;
    }
    let canceled = false;
    setProfileOptionsLoading(true);
    setProfileOptionsError(null);
    void fetchRequesterRegistryOptions()
      .then((options) => {
        if (canceled) {
          return;
        }
        setDepartmentOptions(options.departments ?? []);
        setLocationOptions(options.locations ?? []);
      })
      .catch((exc) => {
        if (!canceled) {
          setProfileOptionsError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить справочники профиля");
        }
      })
      .finally(() => {
        if (!canceled) {
          setProfileOptionsLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [profileSetupVisible, requestFormNeedsRegistryOptions]);

  useEffect(() => {
    if (!selectedServiceCode && services[0]) {
      setSelectedServiceCode(services[0].service_code);
    }
  }, [selectedServiceCode, services]);

  useEffect(() => {
    if (selectedService?.offerings[0] && !selectedOfferingFullCode) {
      setSelectedOfferingFullCode(selectedService.offerings[0].full_code);
    }
  }, [selectedOfferingFullCode, selectedService]);

  useEffect(() => {
    if (selectedOffering?.request_template_key) {
      setSelectedFormKey(selectedOffering.request_template_key);
    }
  }, [selectedOffering?.request_template_key]);

  useEffect(() => {
    if (!visibleForms.length) {
      if (forms.length && selectedFormKey) {
        setSelectedFormKey("");
      }
      return;
    }
    if (!visibleForms.some((form) => form.key === selectedFormKey)) {
      setSelectedFormKey(visibleForms[0].key);
    }
  }, [forms.length, selectedFormKey, visibleForms]);

  useEffect(() => {
    setFieldValues((current) => {
      const nextValues = mergeContextPrefillValues(
        selectedForm,
        current,
        previousContextPrefillRef.current,
        requestFormContextPrefill,
      );
      previousContextPrefillRef.current = buildDefaultFieldValues(selectedForm, requestFormContextPrefill);
      return nextValues;
    });
  }, [requestFormContextPrefill, requestFormContextPrefillKey, selectedForm]);

  useEffect(() => {
    if (!selectedOffering) {
      setKnowledgeResult(null);
      setKnowledgeError(false);
      setKnowledgeLoading(false);
      return;
    }
    let canceled = false;
    setKnowledgeLoading(true);
    setKnowledgeError(false);
    void suggestKnowledge({
      service_code: selectedService?.service_code,
      offering_code: selectedOffering.full_code,
      request_template_key: selectedOffering.request_template_key ?? selectedForm?.key,
      query: description || selectedOffering.title || selectedService?.title || "",
      form_payload: visiblePayload,
      requester_context: bootstrap?.requester_context,
      device_metadata: selectedDevice
        ? {
            device_id: selectedDevice.device_id,
            hostname: selectedDevice.hostname,
            os: selectedDevice.os,
            agent_version: selectedDevice.agent_version,
            asset_id: selectedDevice.asset_id,
            asset_name: selectedDevice.asset_name,
          }
        : undefined,
      surface: "requester_portal",
      urgency: "normal",
      impact: "normal",
    })
      .then((result) => {
        if (!canceled) {
          setKnowledgeResult(result);
        }
      })
      .catch(() => {
        if (!canceled) {
          setKnowledgeResult(null);
          setKnowledgeError(true);
        }
      })
      .finally(() => {
        if (!canceled) {
          setKnowledgeLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [bootstrap?.requester_context, description, knowledgeKey, selectedDevice, selectedForm?.key, selectedOffering, selectedService?.service_code, selectedService?.title, visiblePayload]);

  function appendKnowledgeAttempt(item: KnowledgeSuggestionItem, result: KnowledgeAttempt["result"]) {
    const attempt: KnowledgeAttempt = {
      item_id: item.item_id,
      version_id: item.version_id ?? null,
      result,
      surface: "requester_portal",
      timestamp: new Date().toISOString(),
    };
    setKnowledgeAttempts((current) => [
      ...current.filter((entry) => entry.item_id !== item.item_id || entry.result !== result),
      attempt,
    ]);
    return attempt;
  }

  async function openDeviceDetail(deviceId: string) {
    setSelectedDeviceId(deviceId);
    setDeviceDetailLoading(true);
    setDeviceDetailError(null);
    try {
      setSelectedDeviceDetail(await fetchRequesterDevice(deviceId));
    } catch (exc) {
      setSelectedDeviceDetail(null);
      setDeviceDetailError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить устройство");
    } finally {
      setDeviceDetailLoading(false);
    }
  }

  async function handleDeviceLinkLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDeviceLinkNotice(null);
    setDeviceLinkError(null);
    setDeviceLinkPairing(null);
    if (deviceLinkBlocked) {
      setDeviceLinkError("Сначала заполните профиль, затем привяжите устройство.");
      return;
    }
    const code = deviceLinkCode.trim();
    if (!code) {
      setDeviceLinkError("Введите код привязки из агента.");
      return;
    }
    setDeviceLinkLoading(true);
    try {
      const lookup = await lookupDevicePairingCode(code);
      if (lookup.purpose !== "registration") {
        setDeviceLinkError("Этот код предназначен для входа на уже привязанном устройстве.");
        return;
      }
      const pairing = await fetchDevicePairing(lookup.pairing_id);
      setDeviceLinkPairing(pairing);
      setDeviceLinkNotice("Проверьте устройство и подтвердите привязку.");
    } catch (exc) {
      setDeviceLinkError(exc instanceof Error ? exc.message : "Код привязки не найден или истек.");
    } finally {
      setDeviceLinkLoading(false);
    }
  }

  async function handleDeviceLinkConfirm() {
    if (!deviceLinkPairing) {
      return;
    }
    setDeviceLinkNotice(null);
    setDeviceLinkError(null);
    if (deviceLinkBlocked) {
      setDeviceLinkError("Сначала заполните профиль, затем привяжите устройство.");
      return;
    }
    setDeviceLinkConfirming(true);
    try {
      const result = await confirmDevicePairing(deviceLinkPairing.pairing_id, "registration");
      setDeviceLinkPairing(result);
      setDeviceLinkCode("");
      setDeviceLinkNotice(
        result.registration?.status
          ? registrationStatusLabel(result.registration.status)
          : "Привязка устройства подтверждена.",
      );
      await load();
    } catch (exc) {
      if (exc instanceof DevicePairingApiError && exc.errorCode === "REQUESTER_PROFILE_INCOMPLETE") {
        setDeviceLinkError("Сначала заполните профиль, затем привяжите устройство.");
      } else {
        setDeviceLinkError(exc instanceof Error ? exc.message : "Не удалось подтвердить устройство.");
      }
    } finally {
      setDeviceLinkConfirming(false);
    }
  }

  async function openProfileDetail() {
    setProfileDetailLoading(true);
    setProfileDetailError(null);
    try {
      setProfileDetail(await fetchRequesterProfile());
    } catch (exc) {
      setProfileDetail(null);
      setProfileDetailError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить профиль");
    } finally {
      setProfileDetailLoading(false);
    }
  }

  function recordKnowledgeAttempt(item: KnowledgeSuggestionItem, result: KnowledgeAttempt["result"]) {
    appendKnowledgeAttempt(item, result);
    void recordKnowledgeFeedback({
      item_id: item.item_id,
      version_id: item.version_id,
      event_type: result === "deflected" ? "deflected" : result === "not_helpful" ? "not_helpful" : result === "helpful" ? "helpful" : "viewed",
      service_code: selectedService?.service_code,
      offering_code: selectedOffering?.full_code,
      request_template_key: selectedOffering?.request_template_key ?? selectedForm?.key,
      surface: "requester_portal",
    });
  }

  async function handleOnBehalfSearch() {
    const query = onBehalfQuery.trim();
    if (!selectedForm || query.length < 2) {
      setOnBehalfPeople([]);
      setOnBehalfSelectedPersonId("");
      setOnBehalfSearchError("Введите минимум 2 символа для поиска сотрудника.");
      return;
    }
    setOnBehalfSearchLoading(true);
    setOnBehalfSearchError(null);
    try {
      const result = await searchRequesterOnBehalfPeople({
        form_key: selectedForm.key,
        request_template_key: selectedOffering?.request_template_key ?? selectedForm.key,
        form_pack_key: formPackMeta?.pack_key,
        form_pack_version: formPackMeta?.version,
        q: query,
      });
      const people = result.people ?? [];
      setOnBehalfPeople(people);
      setOnBehalfSelectedPersonId((current) =>
        people.some((person) => person.person_id === current) ? current : "",
      );
      if (!people.length) {
        setOnBehalfSearchError("Подходящих сотрудников в доступной области не найдено.");
      }
    } catch (exc) {
      setOnBehalfPeople([]);
      setOnBehalfSelectedPersonId("");
      setOnBehalfSearchError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось найти сотрудника.");
    } finally {
      setOnBehalfSearchLoading(false);
    }
  }

  function buildCreatePayload(): RequesterTicketCreatePayload {
    if (!selectedFormProfileAllowed) {
      throw new Error("Заполните профиль, чтобы продолжить работу в кабинете пользователя.");
    }
    if (!canCreateForCurrentScope) {
      throw new Error("Выберите устройство или доступную форму обращения.");
    }
    if (!description.trim()) {
      throw new Error("Заполните описание");
    }
    const missing = missingRequiredFields(selectedForm, fieldValues);
    if (missing.length) {
      throw new Error(`Заполните обязательные поля: ${missing.join(", ")}`);
    }
    if (onBehalfActive && !selectedOnBehalfPerson) {
      throw new Error("Выберите сотрудника, у которого проблема");
    }
    if (onBehalfActive && selectedOnBehalfPolicy?.reason_required && !onBehalfReason.trim()) {
      throw new Error("Укажите причину обращения за другого сотрудника");
    }
    const payload: RequesterTicketCreatePayload = {
      title: title.trim() || selectedForm?.title || selectedOffering?.title || "Проверка рабочего места",
      description: description.trim(),
      user_display_name: profileName,
      urgency: false,
      importance: false,
      urgency_reason: "Создано из кабинета заявителя",
      importance_reason: "Создано из кабинета заявителя",
      ...(selectedForm && formPackMeta
        ? {
            form_key: selectedForm.key,
            form_pack_key: formPackMeta.pack_key,
            form_pack_version: formPackMeta.version,
            form_payload: visiblePayload,
            ticket_type: selectedForm.request_kind || selectedForm.key,
            request_template_key: selectedOffering?.request_template_key ?? selectedForm.key,
            service_code: selectedService?.service_code,
            offering_code: selectedOffering?.offering_code,
            offering_full_code: selectedOffering?.full_code,
          }
        : {}),
    };
    if (selectedDevice?.device_id) {
      payload.device_id = selectedDevice.device_id;
    }
    if (onBehalfTicketContext) {
      payload.ticket_context = onBehalfTicketContext;
    }
    if (knowledgeAttempts.length) {
      payload.knowledge_attempts = knowledgeAttempts;
    }
    return payload;
  }

  function handleProfileFieldChange(
    field: Exclude<keyof ProfileFormState, "custom_fields">,
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) {
    const { value } = event.currentTarget;
    setProfileForm((current) => ({ ...current, [field]: value }));
  }

  function handleProfileCustomFieldChange(
    fieldKey: string,
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) {
    const { currentTarget } = event;
    const value = currentTarget instanceof HTMLInputElement && currentTarget.type === "checkbox"
      ? currentTarget.checked
      : currentTarget.value;
    setProfileForm((current) => ({
      ...current,
      custom_fields: {
        ...current.custom_fields,
        [fieldKey]: value,
      },
    }));
  }

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileSetupNotice(null);
    setError(null);
    const nextProfile = {
      person_id: bootstrap?.profile?.person_id,
      full_name: profileForm.full_name.trim(),
      department_id: profileForm.department_id,
      location_id: profileForm.location_id,
      phone: profileForm.phone.trim(),
      position: profileForm.position.trim(),
      workplace_label: profileForm.workplace_label.trim(),
      preferred_contact_method: profileForm.preferred_contact_method.trim(),
      custom_fields: Object.fromEntries(
        Object.entries(profileForm.custom_fields).map(([key, value]) => [
          key,
          typeof value === "string" ? value.trim() : value,
        ]),
      ),
    };
    if (!nextProfile.full_name || !nextProfile.department_id || !nextProfile.location_id || !nextProfile.phone) {
      setError("Заполните обязательные поля профиля.");
      return;
    }
    const missingCustomFields = profileCustomFields
      .filter((field) => field.required)
      .filter((field) => {
        const value = profileForm.custom_fields[field.key];
        return field.type === "checkbox" ? value !== true : !String(value ?? "").trim();
      })
      .map((field) => field.label || field.key);
    if (missingCustomFields.length) {
      setError(`Заполните обязательные поля профиля: ${missingCustomFields.join(", ")}.`);
      return;
    }

    setProfileSubmitting(true);
    try {
      const result = await updateRequesterProfile(nextProfile);
      setProfileForm(profileFormFrom(result.profile));
      setProfileDetail((current) =>
        current
          ? {
              ...current,
              profile: result.profile,
              profile_completion: result.profile_completion,
              profile_policy: result.profile_policy,
              profile_schema: result.profile_schema ?? current.profile_schema,
            }
          : current,
      );
      setBootstrap((current) =>
        current
          ? {
              ...current,
              profile: result.profile,
              profile_completion: result.profile_completion,
              profile_schema: result.profile_schema ?? current.profile_schema,
              feature_flags: {
                ...(current.feature_flags ?? {}),
                requester_ticket_create: result.profile_completion.complete,
                requester_owned_device_create: result.profile_completion.complete,
                requester_no_device_create: result.profile_completion.complete,
              },
            }
          : current,
      );
      if (typeof window !== "undefined" && window.location.pathname.endsWith("/requester/profile/setup")) {
        const nextPath = profileSetupNextPath();
        window.history.pushState({}, "", isSafeAppNextPath(nextPath) ? nextPath : "/app/requester");
      }
      setProfileSetupNotice("Профиль сохранен. Теперь можно продолжить работу в кабинете пользователя.");
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось сохранить профиль");
    } finally {
      setProfileSubmitting(false);
    }
  }

  async function handlePreview() {
    if (!selectedFormProfileAllowed) {
      setError("Заполните профиль, чтобы продолжить работу в кабинете пользователя.");
      return;
    }
    setPreviewSubmitting(true);
    setError(null);
    setPreviewResult(null);
    try {
      const createPayload = buildCreatePayload();
      const result = await previewRequesterTicket({
        ...(createPayload.device_id ? { device_id: createPayload.device_id } : {}),
        service_code: createPayload.service_code,
        offering_code: createPayload.offering_code,
        offering_full_code: createPayload.offering_full_code,
        request_template_key: createPayload.request_template_key,
        form_key: createPayload.form_key,
        form_pack_key: createPayload.form_pack_key,
        form_pack_version: createPayload.form_pack_version,
        form_payload: createPayload.form_payload,
        ticket_context: createPayload.ticket_context,
        description: createPayload.description,
        requester_context: {
          requester_profile: {
            full_name: profileName,
            email: bootstrap?.profile?.email,
            phone: bootstrap?.profile?.phone,
          },
        },
        ...(selectedDevice
          ? {
              device_metadata: {
                device_id: selectedDevice.device_id,
                hostname: selectedDevice.hostname,
                os: selectedDevice.os,
              },
            }
          : {}),
      });
      setPreviewResult(result);
      setPreviewKey(currentPreviewKey);
      if ((result.blockers ?? []).length) {
        setError(result.blockers.join(" "));
      } else {
        setCatalogNotice((result.warnings ?? []).length ? `Preview рассчитан: ${result.warnings.join(" ")}` : "Preview рассчитан");
      }
    } catch (exc) {
      setPreviewKey("");
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось проверить обращение");
    } finally {
      setPreviewSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFormProfileAllowed) {
      setError("Заполните профиль, чтобы продолжить работу в кабинете пользователя.");
      return;
    }
    if (!canCreateForCurrentScope || !description.trim()) {
      setError(canCreateForCurrentScope ? "Заполните описание" : "Выберите доступную форму и заполните описание");
      return;
    }
    if (selectedOffering && !previewIsFresh) {
      setError("Сначала выполните безопасный preview заявки");
      return;
    }
    setSubmitting(true);
    setError(null);
    setCreatedTicketId(null);
    try {
      const result = await createRequesterTicket(buildCreatePayload());
      setCreatedTicketId(result.ticket_id);
      setDescription("");
      setPreviewKey("");
      setPreviewResult(null);
      setTickets(await fetchRequesterTickets());
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось создать обращение");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleClaimPublicTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTicketId = claimTicketId.trim();
    const nextCode = claimCode.trim();
    if (!nextTicketId || !nextCode) {
      setClaimNotice(null);
      setError("Укажите номер заявки и код доступа");
      return;
    }
    setClaimSubmitting(true);
    setClaimNotice(null);
    setError(null);
    try {
      const result = await claimPublicRequesterTicket(nextTicketId, nextCode);
      setClaimTicketId("");
      setClaimCode("");
      setClaimNotice("Обращение привязано");
      setTickets(await fetchRequesterTickets());
      await openTicket(result.ticket_id);
    } catch (exc) {
      if (exc instanceof RequesterApiError && exc.details === "REQUESTER_IDENTITY_REQUIRED") {
        setError("Для привязки обращения нужен связанный профиль пользователя. Обратитесь к администратору для привязки учетной записи.");
      } else {
        setError(exc instanceof RequesterApiError ? exc.message : "Не удалось привязать обращение");
      }
    } finally {
      setClaimSubmitting(false);
    }
  }

  async function openTicket(ticketId: string) {
    setSelectedTicketId(ticketId);
    setSelectedTicketDetail(null);
    setDetailLoading(true);
    setMessageNotice(null);
    setActionNotice(null);
    setPendingAttachments([]);
    setMessageText("");
    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = "";
    }
    setFeedbackId(null);
    setReopenAvailable(false);
    setError(null);
    try {
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить обращение");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ticketId = selectedTicketId;
    const text = messageText.trim();
    const attachmentRefs = pendingAttachments.map((attachment) => attachment.artifact_id);
    if (!ticketId || (!text && !attachmentRefs.length)) {
      return;
    }
    setMessageSending(true);
    setMessageNotice(null);
    setError(null);
    try {
      await sendRequesterTicketMessage(ticketId, text, attachmentRefs);
      setMessageText("");
      setPendingAttachments([]);
      if (attachmentInputRef.current) {
        attachmentInputRef.current.value = "";
      }
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
      setMessageNotice("Сообщение отправлено");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось отправить сообщение");
    } finally {
      setMessageSending(false);
    }
  }

  async function handleAttachmentChange(event: ChangeEvent<HTMLInputElement>) {
    const ticketId = selectedTicketId;
    const input = event.currentTarget;
    const files = Array.from(input.files ?? []);
    if (!ticketId || !files.length) {
      return;
    }
    setAttachmentUploading(true);
    setMessageNotice(null);
    setError(null);
    try {
      const uploaded = await Promise.all(files.map((file) => uploadRequesterTicketAttachment(ticketId, file)));
      setPendingAttachments((current) => [
        ...current,
        ...uploaded.map((item, index) => ({
          artifact_id: item.artifact_id,
          name: files[index]?.name || item.filename || item.artifact_id,
          url: item.url,
          mime_type: item.mime_type,
          kind: item.kind,
        })),
      ]);
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить вложение");
    } finally {
      setAttachmentUploading(false);
      input.value = "";
    }
  }

  async function handleCloseSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await closeRequesterTicket(ticketId);
      await refreshSelectedTicket(ticketId);
      setActionNotice("Решение подтверждено, обращение закрыто");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось закрыть обращение");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleFeedbackSubmit() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      const result = await submitRequesterTicketFeedback(ticketId, {
        rating: feedbackRating,
        problem_resolved: feedbackProblemResolved,
        resolution_confirmed: feedbackProblemResolved,
        reason_codes: feedbackRating <= 3 || !feedbackProblemResolved ? [feedbackReason] : [],
        comment: feedbackComment.trim() || null,
        source_surface: "requester_portal",
      });
      setFeedbackId(result.feedback_id);
      setReopenAvailable(result.reopen_available);
      await refreshSelectedTicket(ticketId);
      setActionNotice(result.message || "Оценка сохранена");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось сохранить оценку");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleReopenSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await reopenRequesterTicket(ticketId, {
        reason_code: reopenReason,
        reason_comment: reopenComment.trim() || feedbackComment.trim() || null,
        linked_feedback_id: feedbackId,
      });
      await refreshSelectedTicket(ticketId);
      setActionNotice("Обращение вернулось в работу");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось вернуть обращение в работу");
    } finally {
      setActionSubmitting(false);
    }
  }

  if (loading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загружаем кабинет заявителя...</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Кабинет заявителя</p>
          <h1>Мои обращения</h1>
          <p>Профиль {profileName}. Доступны только устройства и обращения, связанные с вашей учетной записью.</p>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Устройства</dt>
            <dd>{devices.length}</dd>
          </div>
          <div>
            <dt>Открытые</dt>
            <dd>{bootstrap?.open_ticket_count ?? visibleTickets.length}</dd>
          </div>
          <div>
            <dt>Действия</dt>
            <dd>{actionCount}</dd>
          </div>
        </dl>
      </header>

      {error ? <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {consentNotice ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {consentNotice}
        </div>
      ) : null}
      {createdTicketId ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Создано обращение {createdTicketId}
        </div>
      ) : null}
      {profileSetupNotice ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {profileSetupNotice}
        </div>
      ) : null}

      {profileSetupVisible ? (
        <section aria-label="Заполнение профиля заявителя" className="support-workspace__panel space-y-4">
          <div className="support-workspace__panel-head">
            <div>
              <p className="workspace-boot__eyebrow">Профиль пользователя</p>
              <h2 className="text-lg font-semibold text-slate-950">Заполните профиль</h2>
              <p className="mt-1 text-sm text-slate-600">
              Эти данные нужны для маршрутизации обращений, доступа к базе знаний и поддержки рабочих устройств.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <a
                  className="inline-flex items-center justify-center rounded-panel border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-100"
                  href={profileSetupRegisterPath()}
                >
                  Создать аккаунт
                </a>
              </div>
            </div>
            {profileGateActive ? (
              <span className="rounded-panel bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
                Требуется
              </span>
            ) : null}
          </div>
          {profileCompletion?.missing_fields?.length ? (
            <div className="flex flex-wrap gap-2 text-xs font-semibold text-amber-800">
              {profileCompletion.missing_fields.map((field) => (
                <span className="rounded-panel bg-amber-50 px-3 py-1" key={field.key}>
                  {field.label}
                </span>
              ))}
            </div>
          ) : null}
          {profileOptionsError ? <p className="text-sm text-rose-700">{profileOptionsError}</p> : null}
          <form className="grid gap-3 lg:grid-cols-2" onSubmit={(event) => void handleProfileSubmit(event)}>
            <label className="block text-sm font-semibold text-slate-700">
              ФИО
              <input
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => handleProfileFieldChange("full_name", event)}
                value={profileForm.full_name}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Телефон или внутренний номер
              <input
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => handleProfileFieldChange("phone", event)}
                value={profileForm.phone}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Подразделение
              <select
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                disabled={profileOptionsLoading || !departmentOptions.length}
                onChange={(event) => handleProfileFieldChange("department_id", event)}
                value={profileForm.department_id}
              >
                <option value="">{profileOptionsLoading ? "Загружаем..." : "Выберите подразделение"}</option>
                {departmentOptions.map((department) => (
                  <option key={department.value} value={department.value}>
                    {department.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Локация
              <select
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                disabled={profileOptionsLoading || !locationOptions.length}
                onChange={(event) => handleProfileFieldChange("location_id", event)}
                value={profileForm.location_id}
              >
                <option value="">{profileOptionsLoading ? "Загружаем..." : "Выберите локацию"}</option>
                {locationOptions.map((location) => (
                  <option key={location.value} value={location.value}>
                    {location.label}
                  </option>
                ))}
              </select>
            </label>
            {isProfileFieldVisible("position") ? (
              <label className="block text-sm font-semibold text-slate-700">
                Должность
                <input
                  className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                  onChange={(event) => handleProfileFieldChange("position", event)}
                  value={profileForm.position}
                />
              </label>
            ) : null}
            {isProfileFieldVisible("workplace_label") ? (
              <label className="block text-sm font-semibold text-slate-700">
                Кабинет или рабочее место
                <input
                  className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                  onChange={(event) => handleProfileFieldChange("workplace_label", event)}
                  value={profileForm.workplace_label}
                />
              </label>
            ) : null}
            {isProfileFieldVisible("preferred_contact_method") ? (
              <label className="block text-sm font-semibold text-slate-700 lg:col-span-2">
                Предпочтительный способ связи
                <select
                  className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                  onChange={(event) => handleProfileFieldChange("preferred_contact_method", event)}
                  value={profileForm.preferred_contact_method}
                >
                  <option value="">Не выбран</option>
                  <option value="phone">Телефон</option>
                  <option value="chat">Чат в обращении</option>
                  <option value="email">Email</option>
                </select>
              </label>
            ) : null}
            {profileCustomFields.map((field) => (
              <ProfileCustomFieldControl
                field={field}
                key={field.key}
                onChange={(event) => handleProfileCustomFieldChange(field.key, event)}
                value={profileForm.custom_fields[field.key] ?? (field.type === "checkbox" ? false : "")}
              />
            ))}
            <button
              className="inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 lg:col-span-2"
              disabled={profileSubmitting || profileOptionsLoading || !departmentOptions.length || !locationOptions.length}
              type="submit"
            >
              {profileSubmitting ? "Сохраняем..." : "Сохранить профиль"}
            </button>
          </form>
        </section>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          {pendingConsents.length ? (
            <section aria-label="Ожидающие согласия заявителя" className="support-workspace__panel">
              <div className="support-workspace__panel-head">
                <div>
                  <p className="support-workspace__eyebrow">Согласие пользователя</p>
                  <h2>Ожидают вашего подтверждения</h2>
                </div>
                <span className="rounded-panel bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
                  {pendingConsents.length}
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {pendingConsents.map((consent) => {
                  const expiresAt = formatConsentExpiresAt(consent.expires_at);
                  return (
                    <article className="rounded-panel border border-amber-200 bg-amber-50 px-4 py-3" key={consent.consent_id}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase text-amber-700">
                            {consentSubjectLabel(consent.subject_type)} · {consentRiskLabel(consent.risk_level)}
                          </p>
                          <h3 className="mt-1 break-words text-sm font-semibold text-slate-950">
                            {consent.title || "Требуется ваше согласие"}
                          </h3>
                          {consent.description ? (
                            <p className="mt-1 break-words text-sm text-slate-700">{consent.description}</p>
                          ) : null}
                          <p className="mt-2 text-xs text-slate-600">
                            {consent.ticket_id ? `Обращение: ${consent.ticket_id}` : "Обращение не указано"}
                            {consent.device_id ? ` · Устройство: ${consent.device_id}` : ""}
                            {expiresAt ? ` · До: ${expiresAt}` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <button
                            aria-label={`Отклонить согласие ${consent.consent_id}`}
                            className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={consentSubmittingId === consent.consent_id}
                            onClick={() => void handleConsentDecision(consent, "denied")}
                            type="button"
                          >
                            <X className="h-4 w-4" />
                            Отклонить
                          </button>
                          <button
                            aria-label={`Подтвердить согласие ${consent.consent_id}`}
                            className="inline-flex items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                            disabled={consentSubmittingId === consent.consent_id}
                            onClick={() => void handleConsentDecision(consent, "approved")}
                            type="button"
                          >
                            <CheckCircle2 className="h-4 w-4" />
                            Разрешить
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : null}
        <section className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <div>
              <p className="workspace-boot__eyebrow">Обращения</p>
              <h2 className="text-lg font-semibold text-slate-950">Последние заявки</h2>
            </div>
            <button className="inline-flex items-center gap-2 rounded-panel border px-3 py-2 text-sm font-semibold" onClick={() => void load()} type="button">
              <RefreshCw className="h-4 w-4" />
              Обновить
            </button>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {visibleTickets.length ? (
              visibleTickets.map((ticket) => (
                <button
                  aria-label={`Открыть обращение ${ticket.ticket_id}`}
                  className={`block w-full py-3 text-left ${selectedTicketId === ticket.ticket_id ? "bg-slate-50" : ""}`}
                  key={ticket.ticket_id}
                  onClick={() => void openTicket(ticket.ticket_id)}
                  type="button"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-950">{ticket.ticket_id}</span>
                    <span className="rounded-panel bg-slate-100 px-2 py-1 text-xs text-slate-600">{ticketStatus(ticket)}</span>
                  </div>
                  <h3 className="mt-1 text-sm font-semibold text-slate-800">{ticket.title || "Без темы"}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-500">{ticket.description || "Описание не указано"}</p>
                </button>
              ))
            ) : (
              <p className="py-6 text-sm text-slate-500">Обращений пока нет.</p>
            )}
          </div>
        </section>

          {selectedTicketId ? (
            <section className="support-workspace__panel">
              <div className="support-workspace__panel-head">
                <div>
                  <p className="workspace-boot__eyebrow">Диалог</p>
                  <h2 className="text-lg font-semibold text-slate-950">
                    {selectedTicketDetail?.ticket.title || selectedTicketId}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedTicketDetail?.ticket.description || (detailLoading ? "Загружаем обращение..." : "Описание не указано")}
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {detailLoading ? (
                  <p className="text-sm text-slate-500">Загружаем историю...</p>
                ) : selectedTicketDetail?.messages?.length ? (
                  selectedTicketDetail.messages.map((message) => (
                    <div className="rounded-panel border border-slate-200 p-3" key={message.message_id || message.event_id || message.ts}>
                      <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                        <span>{message.from_role === "support" ? "Поддержка" : "Заявитель"}</span>
                        <span>{message.ts || message.created_at || ""}</span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{message.text || ""}</p>
                      {message.attachments?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.attachments.map((attachment) => (
                            <a
                              className="inline-flex items-center gap-2 rounded-panel border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-brand-700"
                              href={attachment.url || `/api/artifacts/${encodeURIComponent(attachment.artifact_id)}/download`}
                              key={attachment.artifact_id}
                              rel="noreferrer"
                              target="_blank"
                            >
                              <Paperclip className="h-3.5 w-3.5" />
                              {attachment.name || attachment.artifact_id}
                            </a>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Сообщений пока нет.</p>
                )}
              </div>

              {selectedTicket ? (
                <div className="mt-4 grid gap-3 rounded-panel border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Действия по обращению</p>
                      <p className="text-xs text-slate-500">
                        Статус: {selectedTicket.requester_status_label || selectedTicket.status_label || selectedTicket.status}
                      </p>
                    </div>
                    {canCloseSelectedTicket ? (
                      <button
                        aria-label="Закрыть обращение заявителя"
                        className="inline-flex items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                        disabled={actionSubmitting}
                        onClick={() => void handleCloseSelectedTicket()}
                        type="button"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Подтвердить и закрыть
                      </button>
                    ) : null}
                  </div>

                  {canRateSelectedTicket ? (
                    <div className="grid gap-3 border-t border-slate-200 pt-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block text-sm font-semibold text-slate-700">
                          Оценка
                          <select
                            aria-label="Оценка обращения"
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setFeedbackRating(Number(event.target.value))}
                            value={feedbackRating}
                          >
                            {[5, 4, 3, 2, 1].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="flex items-center gap-2 self-end text-sm font-semibold text-slate-700">
                          <input
                            aria-label="Проблема решена"
                            checked={feedbackProblemResolved}
                            onChange={(event) => {
                              setFeedbackProblemResolved(event.target.checked);
                              if (!event.target.checked) {
                                setReopenAvailable(true);
                              }
                            }}
                            type="checkbox"
                          />
                          Проблема решена
                        </label>
                      </div>
                      {feedbackRating <= 3 || !feedbackProblemResolved ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Причина
                          <select
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => {
                              setFeedbackReason(event.target.value);
                              setReopenReason(event.target.value);
                            }}
                            value={feedbackReason}
                          >
                            <option value="not_resolved">Не решено</option>
                            <option value="problem_returned">Проблема вернулась</option>
                            <option value="slow_resolution">Долгое решение</option>
                            <option value="poor_communication">Недостаточно коммуникации</option>
                            <option value="other">Другое</option>
                          </select>
                        </label>
                      ) : null}
                      <label className="block text-sm font-semibold text-slate-700">
                        Комментарий
                        <textarea
                          className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                          onChange={(event) => setFeedbackComment(event.target.value)}
                          value={feedbackComment}
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Отправить оценку обращения"
                          className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                          disabled={actionSubmitting || (feedbackReason === "other" && !feedbackComment.trim())}
                          onClick={() => void handleFeedbackSubmit()}
                          type="button"
                        >
                          <Star className="h-4 w-4" />
                          Отправить оценку
                        </button>
                        {canReopenSelectedTicket ? (
                          <button
                            aria-label="Вернуть обращение в работу"
                            className="inline-flex items-center justify-center gap-2 rounded-panel border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 disabled:cursor-not-allowed disabled:bg-slate-100"
                            disabled={actionSubmitting || (reopenReason === "other" && !reopenComment.trim() && !feedbackComment.trim())}
                            onClick={() => void handleReopenSelectedTicket()}
                            type="button"
                          >
                            <RotateCcw className="h-4 w-4" />
                            Вернуть в работу
                          </button>
                        ) : null}
                      </div>
                      {canReopenSelectedTicket ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Комментарий для повторного открытия
                          <textarea
                            className="mt-1 min-h-16 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setReopenComment(event.target.value)}
                            value={reopenComment}
                          />
                        </label>
                      ) : null}
                    </div>
                  ) : null}
                  {actionNotice ? <p className="text-sm text-emerald-700">{actionNotice}</p> : null}
                </div>
              ) : null}

              <form className="mt-4 space-y-3" onSubmit={(event) => void handleMessageSubmit(event)}>
                <label className="block text-sm font-semibold text-slate-700">
                  Ответ
                  <textarea
                    aria-label="Ответ заявителя"
                    className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => setMessageText(event.target.value)}
                    value={messageText}
                  />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    aria-label="Прикрепить файл к ответу"
                    className="sr-only"
                    disabled={attachmentUploading || messageSending || !selectedTicketId}
                    multiple
                    onChange={(event) => void handleAttachmentChange(event)}
                    ref={attachmentInputRef}
                    type="file"
                  />
                  <button
                    aria-label="Выбрать файл для ответа"
                    className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                    disabled={attachmentUploading || messageSending || !selectedTicketId}
                    onClick={() => attachmentInputRef.current?.click()}
                    type="button"
                  >
                    <Paperclip className="h-4 w-4" />
                    {attachmentUploading ? "Загружаем..." : "Вложить файл"}
                  </button>
                </div>
                {pendingAttachments.length ? (
                  <div className="flex flex-wrap gap-2">
                    {pendingAttachments.map((attachment) => (
                      <span
                        className="inline-flex items-center gap-2 rounded-panel border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700"
                        key={attachment.artifact_id}
                      >
                        <Paperclip className="h-3.5 w-3.5" />
                        {attachment.name}
                        <button
                          aria-label={`Удалить вложение ${attachment.name}`}
                          className="inline-flex h-5 w-5 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200"
                          onClick={() =>
                            setPendingAttachments((current) =>
                              current.filter((item) => item.artifact_id !== attachment.artifact_id),
                            )
                          }
                          type="button"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}
                {messageNotice ? <p className="text-sm text-emerald-700">{messageNotice}</p> : null}
                <button
                  aria-label="Отправить ответ заявителя"
                  className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={
                    messageSending ||
                    attachmentUploading ||
                    !selectedTicketId ||
                    (!messageText.trim() && !pendingAttachments.length)
                  }
                  type="submit"
                >
                  <Send className="h-4 w-4" />
                  {messageSending ? "Отправляем..." : "Отправить"}
                </button>
              </form>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          <section className="support-workspace__panel">
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Профиль</p>
                <h2 className="text-lg font-semibold text-slate-950">Мой профиль</h2>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-slate-700">
              <div>
                <p className="break-words font-semibold text-slate-950">{profileName}</p>
                {bootstrap?.profile?.email ? <p className="break-words text-slate-500">{bootstrap.profile.email}</p> : null}
                <p className="mt-2 rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
                  {profileDeviceStatus}
                </p>
              </div>
              <button
                aria-label="Открыть профиль заявителя"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={profileDetailLoading}
                onClick={() => void openProfileDetail()}
                type="button"
              >
                <Link2 className="h-4 w-4" />
                {profileDetailLoading ? "Загружаем..." : "Подробнее"}
              </button>
            </div>
            {profileDetailError ? <p className="mt-3 text-sm text-rose-700">{profileDetailError}</p> : null}
            {profileDetail ? (
              <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <p className="font-semibold text-slate-950">Профиль заявителя</p>
                <dl className="mt-3 grid gap-2">
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Имя</dt>
                    <dd className="break-words font-semibold text-slate-900">
                      {profileDetail.profile?.full_name || profileDetail.profile?.display_name || profileName}
                    </dd>
                  </div>
                  {profileDetail.profile?.email ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Email</dt>
                      <dd className="break-words">{profileDetail.profile.email}</dd>
                    </div>
                  ) : null}
                  {profileDetail.profile?.phone ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Телефон</dt>
                      <dd className="break-words">{profileDetail.profile.phone}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Статус</dt>
                    <dd>{profileDetail.profile?.status || "profile not linked"}</dd>
                  </div>
                </dl>
                <p className="mt-3 rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                  Данные профиля доступны только для чтения.
                </p>
                {profileDetail.identities.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Идентификаторы</p>
                    <div className="mt-2 grid gap-2">
                      {profileDetail.identities.map((identity) => (
                        <div
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                          key={identity.identity_id || `${identity.provider}:${identity.identifier}`}
                        >
                          <span className="block font-semibold text-slate-900">{identity.provider}</span>
                          <span className="block break-words">{identity.identifier}</span>
                          <span className="block text-slate-500">{identity.verified ? "verified" : "not verified"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {profileDetail.devices.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Устройства профиля</p>
                    <div className="mt-2 grid gap-2">
                      {profileDetail.devices.map((device) => (
                        <span
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900"
                          key={device.device_id}
                        >
                          {deviceLabel(device)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className="support-workspace__panel">
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Устройства</p>
                <h2 className="text-lg font-semibold text-slate-950">Мои устройства</h2>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {devices.length ? (
                devices.map((device) => (
                  <div className="rounded-panel border border-slate-200 p-3 text-sm" key={device.device_id}>
                    <label className="flex cursor-pointer items-start gap-3">
                      <input
                        checked={(selectedDevice?.device_id ?? "") === device.device_id}
                        className="mt-1"
                        name="requester-device"
                        onChange={() => setSelectedDeviceId(device.device_id)}
                        type="radio"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block break-words font-semibold text-slate-900">{deviceLabel(device)}</span>
                        <span className="block break-words text-xs text-slate-500">{deviceSystemLabel(device.os, device.agent_version)}</span>
                      </span>
                    </label>
                    <button
                      aria-label={`Открыть сведения об устройстве ${device.device_id}`}
                      className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                      disabled={deviceDetailLoading}
                      onClick={() => void openDeviceDetail(device.device_id)}
                      type="button"
                    >
                      {deviceDetailLoading && selectedDeviceId === device.device_id ? "Загружаем..." : "Подробнее"}
                    </button>
                  </div>
                ))
                ) : (
                  <p className="text-sm text-slate-500">
                    <span className="block">Зарегистрированных устройств пока нет.</span>
                    <span className="block">Можно создать общее обращение без привязки к устройству.</span>
                  </p>
                )}
              {pendingRegistrationClaims.length ? (
                <div className="rounded-panel border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                  <p className="font-semibold">Заявки на привязку</p>
                  <ul className="mt-2 space-y-2">
                    {pendingRegistrationClaims.map((claim, index) => {
                      const submittedAt = formatSubmittedAt(claim.submitted_at);
                      return (
                        <li className="flex flex-col gap-1 border-t border-amber-200 pt-2 first:border-t-0 first:pt-0" key={claim.claim_id || `${claim.device_id || "device"}-${index}`}>
                          <span className="break-words font-semibold">{pendingDeviceLinkLabel(claim)}</span>
                          <span>{pendingDeviceLinkStatusLabel(claim.status)}</span>
                          {submittedAt ? <span className="text-xs text-amber-800">Отправлено: {submittedAt}</span> : null}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : null}
            </div>
            <form className="mt-4 grid gap-3 border-t border-slate-200 pt-4" onSubmit={(event) => void handleDeviceLinkLookup(event)}>
              <div>
                <p className="text-sm font-semibold text-slate-950">Привязать устройство</p>
                <p className="mt-1 text-xs text-slate-500">
                  Введите код из локального агента. Перед отправкой заявки вы увидите имя устройства и версию агента.
                </p>
              </div>
              {deviceLinkBlocked ? (
                <a className="rounded-panel border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900" href="/app/requester/profile/setup">
                  Сначала заполните профиль
                </a>
              ) : null}
              <label className="block text-sm font-semibold text-slate-700">
                Код привязки
                <input
                  autoComplete="one-time-code"
                  className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-mono font-semibold uppercase"
                  disabled={deviceLinkBlocked || deviceLinkLoading || deviceLinkConfirming}
                  maxLength={16}
                  onChange={(event) => setDeviceLinkCode(event.target.value.toUpperCase())}
                  placeholder="ABCD-1234"
                  value={deviceLinkCode}
                />
              </label>
              <button
                aria-label="Проверить код привязки"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={deviceLinkBlocked || deviceLinkLoading || deviceLinkConfirming}
                type="submit"
              >
                <KeyRound className="h-4 w-4" />
                {deviceLinkLoading ? "Проверяем..." : "Проверить код"}
              </button>
            </form>
            {deviceLinkPairing ? (
              <div className="mt-3 rounded-panel border border-brand-100 bg-brand-50 p-3 text-sm text-slate-700">
                <div className="flex items-start gap-3">
                  <Monitor className="mt-0.5 h-5 w-5 text-brand-700" />
                  <div className="min-w-0 flex-1">
                    <p className="break-words font-semibold text-slate-950">{pairingDeviceLabel(deviceLinkPairing)}</p>
                    <p className="mt-1 break-words text-xs text-slate-600">
                      {deviceSystemLabel(deviceLinkPairing.device?.os, deviceLinkPairing.device?.agent_version)}
                    </p>
                    {deviceLinkPairing.registration?.status ? (
                      <p className="mt-2 text-xs font-semibold text-brand-800">
                        {registrationStatusLabel(deviceLinkPairing.registration.status)}
                      </p>
                    ) : null}
                  </div>
                </div>
                <button
                  aria-label="Подтвердить привязку устройства"
                  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={deviceLinkConfirming || deviceLinkPairing.status === "confirmed"}
                  onClick={() => void handleDeviceLinkConfirm()}
                  type="button"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {deviceLinkConfirming ? "Подтверждаем..." : "Подтвердить привязку"}
                </button>
              </div>
            ) : null}
            {deviceLinkNotice ? <p className="mt-3 text-sm text-emerald-700">{deviceLinkNotice}</p> : null}
            {deviceLinkError ? <p className="mt-3 text-sm text-rose-700">{deviceLinkError}</p> : null}
            {deviceDetailError ? <p className="mt-3 text-sm text-rose-700">{deviceDetailError}</p> : null}
            {selectedDeviceDetail ? (
              <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <p className="font-semibold text-slate-950">Сведения об устройстве</p>
                <dl className="mt-3 grid gap-2">
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Имя</dt>
                    <dd className="break-words font-semibold text-slate-900">{deviceLabel(selectedDeviceDetail.device)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Система</dt>
                    <dd className="break-words">{deviceSystemLabel(selectedDeviceDetail.device.os, selectedDeviceDetail.device.agent_version)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Связь</dt>
                    <dd>{relationshipLabel(selectedDeviceDetail.device.relationship_type)} · {bindingStatusLabel(selectedDeviceDetail.device.binding_status)}</dd>
                  </div>
                  {selectedDeviceDetail.device.asset_name ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Актив</dt>
                      <dd className="break-words">{selectedDeviceDetail.device.asset_name}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Активность</dt>
                    <dd>{deviceOnlineLabel(selectedDeviceDetail.device.online)} · Открытые обращения: {selectedDeviceDetail.device.open_ticket_count ?? 0}</dd>
                  </div>
                </dl>
                {selectedDeviceDetail.recent_tickets?.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Последние обращения</p>
                    <div className="mt-2 grid gap-2">
                      {selectedDeviceDetail.recent_tickets.map((ticket) => (
                        <button
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-700 hover:border-brand-300"
                          key={ticket.ticket_id}
                          onClick={() => void openTicket(ticket.ticket_id)}
                          type="button"
                        >
                          <span className="block break-words font-semibold text-slate-900">{ticket.title || ticket.ticket_code || ticket.ticket_id}</span>
                          <span className="block text-slate-500">{ticketStatus(ticket)}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <form className="support-workspace__panel space-y-3" onSubmit={(event) => void handleClaimPublicTicket(event)}>
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Публичный доступ</p>
                <h2 className="text-lg font-semibold text-slate-950">Привязать обращение</h2>
              </div>
            </div>
            <label className="block text-sm font-semibold text-slate-700">
              Номер заявки
              <input
                aria-label="Номер обращения для привязки"
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setClaimTicketId(event.currentTarget.value)}
                value={claimTicketId}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Код доступа
              <input
                aria-label="Код доступа для привязки обращения"
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setClaimCode(event.currentTarget.value)}
                value={claimCode}
              />
            </label>
            {claimNotice ? <p className="text-sm text-emerald-700">{claimNotice}</p> : null}
            <button
              aria-label="Привязать публичное обращение"
              className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={claimSubmitting || !claimTicketId.trim() || !claimCode.trim()}
              type="submit"
            >
              <Link2 className="h-4 w-4" />
              {claimSubmitting ? "Привязываем..." : "Привязать"}
            </button>
          </form>

          <form className="support-workspace__panel space-y-3" onSubmit={(event) => void handleSubmit(event)}>
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Новая заявка</p>
                <h2 className="text-lg font-semibold text-slate-950">Создать обращение</h2>
              </div>
            </div>
            {catalogNotice ? (
              <div
                className={
                  catalogNotice.startsWith("Каталог услуг временно")
                    ? "rounded-panel border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                    : "rounded-panel border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"
                }
              >
                {catalogNotice}
              </div>
            ) : null}
            {requesterContextSummary.length ? (
              <dl aria-label="Контекст формы обращения" className="grid gap-2 rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:grid-cols-2">
                {requesterContextSummary.map((item) => (
                  <div key={item.label}>
                    <dt className="font-semibold text-slate-500">{item.label}</dt>
                    <dd className="mt-0.5 break-words text-slate-900">{item.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {services.length ? (
              <div className="grid gap-3">
                <label className="block text-sm font-semibold text-slate-700">
                  Услуга
                  <select
                    aria-label="Услуга обращения"
                    className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => {
                      const nextCode = event.currentTarget.value;
                      setSelectedServiceCode(nextCode);
                      const nextService = services.find((service) => service.service_code === nextCode);
                      setSelectedOfferingFullCode(nextService?.offerings[0]?.full_code ?? "");
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={selectedService?.service_code ?? ""}
                  >
                    {services.map((service) => (
                      <option key={service.service_code} value={service.service_code}>
                        {service.title || service.service_code}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedService?.offerings.length ? (
                  <label className="block text-sm font-semibold text-slate-700">
                    Тип обращения
                    <select
                      aria-label="Вариант услуги"
                      className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                      onChange={(event) => {
                        setSelectedOfferingFullCode(event.currentTarget.value);
                        setPreviewKey("");
                        setPreviewResult(null);
                      }}
                      value={selectedOffering?.full_code ?? ""}
                    >
                      {selectedService.offerings.map((offering) => (
                        <option key={offering.full_code} value={offering.full_code}>
                          {offering.title || offering.offering_code}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {selectedOffering ? (
                  <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    <p className="font-semibold text-slate-900">{selectedOffering.title}</p>
                    {selectedOffering.description ? <p className="mt-1">{selectedOffering.description}</p> : null}
                    <p className="mt-1 text-xs">
                      {[
                        selectedOffering.expected_response ? `Ответ: ${selectedOffering.expected_response}` : null,
                        selectedOffering.expected_resolution ? `Решение: ${selectedOffering.expected_resolution}` : null,
                        selectedOffering.approval_required ? "Потребуется согласование" : null,
                        selectedOffering.diagnostic_consent_required ? "Потребуется согласие на диагностику" : null,
                      ]
                        .filter(Boolean)
                      .join(" · ")}
                    </p>
                  </div>
                ) : null}
                {knowledgeVisible ? (
                  <div className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">Возможно, поможет</p>
                      {knowledgeLoading ? <span className="text-xs text-slate-500">Ищем...</span> : null}
                    </div>
                    {knowledgeError ? (
                      <p className="mt-2 text-xs text-amber-700">Инструкции временно недоступны.</p>
                    ) : null}
                    {knowledgeSuggestions.length ? (
                      <div className="mt-2 grid gap-2">
                        {knowledgeSuggestions.map((item) => (
                          <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2" key={item.item_id}>
                            <p className="font-semibold text-slate-900">{item.title}</p>
                            {item.summary ? <p className="mt-1 text-xs text-slate-600">{item.summary}</p> : null}
                            {item.quality_label || item.freshness_label ? (
                              <p className="mt-1 text-[11px] font-semibold text-slate-500">
                                {[item.quality_label, item.freshness_label].filter(Boolean).join(" · ")}
                              </p>
                            ) : null}
                            {openedKnowledgeId === item.item_id && item.snippet ? (
                              <p className="mt-2 rounded-panel bg-white px-3 py-2 text-xs text-slate-700">{item.snippet}</p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                aria-label="Открыть рекомендацию из базы знаний"
                                className="rounded-panel border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                                onClick={() => {
                                  setOpenedKnowledgeId((current) => (current === item.item_id ? null : item.item_id));
                                  recordKnowledgeAttempt(item, "viewed");
                                }}
                                type="button"
                              >
                                {openedKnowledgeId === item.item_id ? "Скрыть" : "Открыть"}
                              </button>
                              <button
                                aria-label="Отметить рекомендацию полезной"
                                className="rounded-panel border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800"
                                onClick={() => recordKnowledgeAttempt(item, "deflected")}
                                type="button"
                              >
                                Помогло
                              </button>
                              <button
                                aria-label="Отметить рекомендацию бесполезной"
                                className="rounded-panel border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                                onClick={() => recordKnowledgeAttempt(item, "not_helpful")}
                                type="button"
                              >
                                Не помогло
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : !knowledgeLoading && !knowledgeError ? (
                      <p className="mt-2 text-xs text-slate-500">Подходящих опубликованных инструкций пока нет.</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
            {visibleForms.length ? (
              <div className="grid gap-3">
                <label className="block text-sm font-semibold text-slate-700">
                  Форма обращения
                  <select
                    aria-label="Форма обращения заявителя"
                    className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => {
                      setSelectedFormKey(event.currentTarget.value);
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={selectedForm?.key ?? ""}
                  >
                    {visibleForms.map((form) => (
                      <option key={form.key} value={form.key}>
                        {form.title || form.key}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedAvailability.available_without_completed_profile || selectedAvailability.available_without_agent_binding ? (
                  <div className="rounded-panel border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    <p>Диагностика может быть недоступна, пока поддержка не уточнит профиль и основное устройство.</p>
                    {selectedAvailability.requires_manual_triage ? (
                      <p className="mt-1">Обращение попадет на ручную обработку поддержки.</p>
                    ) : null}
                  </div>
                ) : null}
                {selectedOnBehalfPolicy?.allowed ? (
                  <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
                    <label className="flex items-center gap-2 font-semibold text-slate-800">
                      <input
                        aria-label="Проблема у другого сотрудника"
                        checked={onBehalfEnabled}
                        onChange={(event) => {
                          setOnBehalfEnabled(event.currentTarget.checked);
                          if (!event.currentTarget.checked) {
                            setOnBehalfSelectedPersonId("");
                            setOnBehalfReason("");
                          }
                        }}
                        type="checkbox"
                      />
                      <span>{selectedOnBehalfPolicy.label || "Проблема у другого сотрудника"}</span>
                    </label>
                    {onBehalfActive ? (
                      <div className="mt-3 grid gap-3">
                        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                          <label className="block text-sm font-semibold text-slate-700">
                            Поиск сотрудника, у которого проблема
                            <input
                              aria-label="Поиск сотрудника, у которого проблема"
                              className="mt-1 w-full rounded-panel border border-slate-200 bg-white px-3 py-2 font-normal"
                              onChange={(event) => {
                                setOnBehalfQuery(event.currentTarget.value);
                                setOnBehalfSelectedPersonId("");
                                setOnBehalfSearchError(null);
                              }}
                              value={onBehalfQuery}
                            />
                          </label>
                          <button
                            className="self-end rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                            disabled={onBehalfSearchLoading}
                            onClick={() => void handleOnBehalfSearch()}
                            type="button"
                          >
                            {onBehalfSearchLoading ? "Ищем..." : "Найти сотрудника"}
                          </button>
                        </div>
                        {onBehalfPeople.length ? (
                          <label className="block text-sm font-semibold text-slate-700">
                            Сотрудник, у которого проблема
                            <select
                              aria-label="Сотрудник, у которого проблема"
                              className="mt-1 w-full rounded-panel border border-slate-200 bg-white px-3 py-2 font-normal"
                              onChange={(event) => setOnBehalfSelectedPersonId(event.currentTarget.value)}
                              value={onBehalfSelectedPersonId}
                            >
                              <option value="">Выберите сотрудника...</option>
                              {onBehalfPeople.map((person) => (
                                <option key={person.person_id} value={person.person_id}>
                                  {onBehalfPersonLabel(person)}
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : null}
                        {selectedOnBehalfPolicy.reason_required ? (
                          <label className="block text-sm font-semibold text-slate-700">
                            Причина обращения за другого сотрудника
                            <textarea
                              aria-label="Причина обращения за другого сотрудника"
                              className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 bg-white px-3 py-2 font-normal"
                              onChange={(event) => setOnBehalfReason(event.currentTarget.value)}
                              value={onBehalfReason}
                            />
                          </label>
                        ) : null}
                        {onBehalfSearchError ? <p className="text-xs text-amber-700">{onBehalfSearchError}</p> : null}
                        {selectedOnBehalfPerson ? (
                          <div
                            aria-label="Контекст обращения за другого сотрудника"
                            className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                          >
                            <dl className="grid gap-2 sm:grid-cols-2">
                              <div>
                                <dt className="font-semibold text-slate-500">Заявитель</dt>
                                <dd className="text-slate-900">{profileName}</dd>
                              </div>
                              <div>
                                <dt className="font-semibold text-slate-500">Сотрудник</dt>
                                <dd className="text-slate-900">{onBehalfPersonLabel(selectedOnBehalfPerson)}</dd>
                              </div>
                              {selectedOnBehalfPerson.department?.name ? (
                                <div>
                                  <dt className="font-semibold text-slate-500">Подразделение</dt>
                                  <dd className="text-slate-900">{selectedOnBehalfPerson.department.name}</dd>
                                </div>
                              ) : null}
                              {selectedOnBehalfPerson.location?.display_name ? (
                                <div>
                                  <dt className="font-semibold text-slate-500">Локация</dt>
                                  <dd className="text-slate-900">{selectedOnBehalfPerson.location.display_name}</dd>
                                </div>
                              ) : null}
                            </dl>
                            <p className="mt-2 text-slate-800">
                              Диагностика будет выполняться по основному устройству выбранного сотрудника.
                            </p>
                            {onBehalfPrimaryAgentMissing(selectedOnBehalfPerson) ? (
                              <p className="mt-1 text-amber-700">
                                У выбранного сотрудника нет привязанного устройства. Диагностика агента недоступна.
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {contextualVisibleFields.map((field) => (
                  <RequestFormFieldControl
                    field={field}
                    key={field.key}
                    onChange={(value) => {
                      setFieldValues((current) => ({ ...current, [field.key]: value }));
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={fieldValues[field.key] ?? (field.type === "checkbox" ? false : "")}
                  />
                ))}
              </div>
            ) : null}
            <label className="block text-sm font-semibold text-slate-700">
              Тема
              <input className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal" onChange={(event) => setTitle(event.target.value)} value={title} />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Описание
              <textarea
                className="mt-1 min-h-32 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setDescription(event.target.value)}
                value={description}
              />
            </label>
            {previewResult ? (
              <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                <p className="font-semibold text-slate-900">Безопасный preview</p>
                <p>{[previewResult.service?.title, previewResult.offering?.title].filter(Boolean).join(" / ")}</p>
                {previewResult.request_type_label ? <p>Тип: {previewResult.request_type_label}</p> : null}
                {previewResult.expected_first_response ? <p>Ответ: {previewResult.expected_first_response}</p> : null}
                {previewResult.expected_resolution ? <p>Решение: {previewResult.expected_resolution}</p> : null}
                {previewResult.approval?.text ? <p>{previewResult.approval.text}</p> : null}
                {previewResult.diagnostics?.text ? <p>{previewResult.diagnostics.text}</p> : null}
                {previewResult.ticket_context?.summary?.affected ? <p>Для: {previewResult.ticket_context.summary.affected}</p> : null}
                {previewResult.ticket_context?.diagnostic_target?.text ? (
                  <p>
                    Устройство для диагностики:{" "}
                    {[previewResult.ticket_context.diagnostic_target.label, previewResult.ticket_context.diagnostic_target.text]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                ) : null}
                {previewResult.requester_context?.summary?.length ? (
                  <p>
                    Контекст:{" "}
                    {previewResult.requester_context.summary
                      .map((item) => item.value)
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                ) : null}
                {previewResult.blockers?.length ? <p className="text-rose-700">{previewResult.blockers.join(" ")}</p> : null}
              </div>
            ) : null}
            <div className="grid gap-2">
              <button
                aria-label="Проверить обращение перед отправкой"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={previewSubmitting || !canCreateForCurrentScope || !description.trim() || !selectedOffering || onBehalfMissingRequired}
                onClick={() => void handlePreview()}
                type="button"
              >
                {previewSubmitting ? "Проверяем..." : "Проверить заявку"}
              </button>
              <button
                aria-label="Создать обращение в кабинете пользователя"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={
                  submitting ||
                  !canCreateForCurrentScope ||
                  !description.trim() ||
                  onBehalfMissingRequired ||
                  Boolean(selectedOffering && !previewIsFresh)
                }
                type="submit"
              >
                <Send className="h-4 w-4" />
                {submitting ? "Создаем..." : "Создать обращение"}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </section>
  );
}
