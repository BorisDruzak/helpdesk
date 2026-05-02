import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BellRing,
  CheckCircle2,
  ClipboardList,
  Eye,
  FileClock,
  FileCheck2,
  FilePenLine,
  FolderClock,
  Gauge,
  Plus,
  RefreshCcw,
  Route,
  Save,
  Settings2,
  Star,
  Stethoscope,
  Trash2,
  UserCheck,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { requirePermission, type PermissionDecision } from "../auth/permissions";
import { fetchWebSettingsPayload } from "../settings/api";
import { cn } from "../../shared/ui/cn";
import {
  type AdminFormsFieldItem,
  type AdminFormsFieldOption,
  type AdminFormsFieldType,
  type AdminFormsPayload,
  type AdminFormsPlaybookTrigger,
  type AdminFormsRoutePreviewResult,
  type AdminFormsSaveRequest,
  type AdminHelpdeskPolicyDiffResult,
  type AdminHelpdeskPolicyItem,
  type AdminHelpdeskModelPayload,
  deactivateHelpdeskPolicyVersion,
  diffHelpdeskPolicyVersions,
  fetchHelpdeskModelRegistry,
  fetchAdminFormsCatalog,
  publishHelpdeskPolicy,
  publishHelpdeskSmartView,
  publishHelpdeskTemplateFromForm,
  previewAdminFormRoute,
  rollbackHelpdeskPolicyVersion,
  saveAdminFormsCatalog,
} from "./api";
import {
  fetchTicketFormsPackList,
  fetchTicketFormsPackVersion,
  setTicketFormsPackPreferred,
  type TicketFormsPackSummary,
} from "./catalog-api";

type ActionFeedback =
  | {
      tone: "success" | "error";
      text: string;
    }
  | null;

type DraftField = {
  key: string;
  label: string;
  type: AdminFormsFieldType;
  required: boolean;
  placeholder: string;
  help_text: string;
  options: AdminFormsFieldOption[];
  validation?: Record<string, unknown>;
  process_mapping?: Record<string, unknown>;
  visible_when: {
    field: string;
    equals: string;
    values: string[];
  };
};

type DraftForm = {
  key: string;
  request_kind: string;
  ticket_type: string;
  title: string;
  description: string;
  category_id: string;
  service_id: string;
  subcategory_id: string;
  default_queue_id: string;
  sla_policy_id: string;
  suggested_playbook_id: string;
  priority_impact_field: string;
  priority_urgency_field: string;
  priority_importance_field: string;
  field_roles_json: string;
  routing_policy_json: string;
  approval_policy_json: string;
  diagnostic_policy_json: string;
  ola_policy_json: string;
  closure_policy_json: string;
  visibility_policy_json: string;
  notification_policy_json: string;
  reporting_policy_json: string;
  playbook_triggers: AdminFormsPlaybookTrigger[];
  fields: DraftField[];
};

type DraftCatalog = {
  title: string;
  description: string;
  forms: DraftForm[];
};

type PreviewFormValues = Record<string, string | boolean>;

type DraftValidationIssue = {
  key: string;
  severity: "error" | "warning";
  message: string;
};

type PreviewValidationIssue = {
  key: string;
  message: string;
};

type TemplateStepKey =
  | "template"
  | "form"
  | "workflow"
  | "priority"
  | "deadlines"
  | "routing"
  | "approvals"
  | "diagnostics"
  | "closure"
  | "visibility"
  | "notifications"
  | "reporting";

const WORKFLOW_PROFILE_OPTIONS = [
  { value: "incident", label: "Инцидент" },
  { value: "service_request", label: "Запрос услуги" },
  { value: "access_request", label: "Запрос доступа" },
  { value: "change_request", label: "Запрос на изменение" },
  { value: "consultation", label: "Консультация" },
] as const;

const FIELD_ROLE_OPTIONS = [
  { value: "routing_field", label: "Влияет на очередь" },
  { value: "priority_field", label: "Влияет на приоритет" },
  { value: "sla_field", label: "Влияет на срок ответа" },
  { value: "approval_field", label: "Влияет на согласование" },
  { value: "diagnostic_input", label: "Передаётся в диагностику" },
  { value: "closure_evidence", label: "Нужно для закрытия" },
  { value: "display_only", label: "Только отображается" },
] as const;

const PRIORITY_QUESTION_FIELDS: DraftField[] = [
  {
    key: "impact_scope",
    label: "Кого затронула проблема?",
    type: "radio",
    required: true,
    placeholder: "",
    help_text: "Пользователь отвечает фактами, система считает приоритет.",
    options: [
      { value: "single_user", label: "Только меня" },
      { value: "group", label: "Несколько человек" },
      { value: "department", label: "Весь отдел" },
      { value: "building_or_org", label: "Здание / организация / критичная система" },
    ],
    visible_when: { field: "", equals: "", values: [] },
  },
  {
    key: "work_continuity",
    label: "Можно ли продолжать работу?",
    type: "radio",
    required: true,
    placeholder: "",
    help_text: "Это поле определяет urgency.",
    options: [
      { value: "work_stopped_no_workaround", label: "Нет, работа остановлена" },
      { value: "partial_work", label: "Можно работать частично" },
      { value: "workaround_available", label: "Есть обходной путь" },
      { value: "inconvenience_only", label: "Неудобно, но не блокирует" },
    ],
    visible_when: { field: "", equals: "", values: [] },
  },
  {
    key: "business_importance",
    label: "Есть важный срок или критичный процесс?",
    type: "radio",
    required: false,
    placeholder: "",
    help_text: "Это поле определяет importance / criticality.",
    options: [
      { value: "normal", label: "Нет, обычная рабочая ситуация" },
      { value: "deadline", label: "Есть важный срок" },
      { value: "deadline_today", label: "Сегодня / завтра крайний срок" },
      { value: "security", label: "ИБ / публичная услуга / критичный процесс" },
    ],
    visible_when: { field: "", equals: "", values: [] },
  },
  {
    key: "critical_service",
    label: "Затронута критичная система",
    type: "checkbox",
    required: false,
    placeholder: "Да",
    help_text: "Модификатор: может повысить приоритет.",
    options: [],
    visible_when: { field: "", equals: "", values: [] },
  },
  {
    key: "public_service",
    label: "Затронут прием граждан / публичная услуга",
    type: "checkbox",
    required: false,
    placeholder: "Да",
    help_text: "Модификатор: может повысить приоритет.",
    options: [],
    visible_when: { field: "", equals: "", values: [] },
  },
];

const TICKET_TYPE_BY_FORM_KIND: Record<string, string> = {
  breakage: "incident",
  printer: "incident",
  network: "incident",
  site_system: "incident",
  mail_issue: "incident",
  access: "access_request",
  new_account: "access_request",
  software_install: "service_request",
  hardware_replacement: "service_request",
};

function inferTicketType(formKey: string, requestKind: string): string {
  return TICKET_TYPE_BY_FORM_KIND[requestKind.trim().toLowerCase()]
    ?? TICKET_TYPE_BY_FORM_KIND[formKey.trim().toLowerCase()]
    ?? "service_request";
}

function normalizeTicketType(value: unknown, formKey: string, requestKind: string): string {
  const raw = typeof value === "string" ? value.trim() : "";
  return raw || inferTicketType(formKey, requestKind);
}

function jsonDraft(value: unknown): string {
  if (!value || (typeof value === "object" && Object.keys(value as Record<string, unknown>).length === 0)) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

function parseJsonDraft(value: string, fallback: Record<string, unknown> = {}): Record<string, unknown> {
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : fallback;
  } catch {
    return fallback;
  }
}

function parseFieldRolesDraft(value: string): Record<string, string[]> {
  const parsed = parseJsonDraft(value);
  return Object.fromEntries(
    Object.entries(parsed)
      .map(([key, roles]): [string, string[]] => [
        key,
        Array.isArray(roles) ? roles.map((role) => String(role ?? "").trim()).filter(Boolean) : [],
      ])
      .filter(([key, roles]) => key.trim() && roles.length)
  );
}

function parseOptionalInt(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDateTime(value: string | null | undefined): string {
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

function getPlaybookTriggerReadiness(trigger: AdminFormsPlaybookTrigger | undefined) {
  if (!trigger?.enabled) {
    return {
      tone: "neutral" as const,
      label: "Запуск выключен",
      detail: "Форма только создаёт тикет и передаёт данные в маршрутизацию.",
    };
  }

  if (!trigger.playbook_key.trim()) {
    return {
      tone: "warning" as const,
      label: "Нужен ключ плейбука",
      detail: "Укажите опубликованный playbook key, иначе автодиагностика не стартует.",
    };
  }

  return {
    tone: "success" as const,
    label: "Готов к запуску после создания тикета",
    detail: "После сбора данных форма создаст тикет, маршрутизация выберет очередь, затем запустится диагностический сценарий.",
  };
}

function describeRouteCondition(condition: Record<string, unknown> | null): string {
  if (!condition) {
    return "Условие не задано";
  }

  const field = typeof condition.field === "string" ? condition.field : "";
  const op = typeof condition.op === "string" ? condition.op : "";
  const value = condition.value;
  const values = Array.isArray(condition.values) ? condition.values : null;
  const displayValue = values
    ? values.map((item) => String(item)).join(", ")
    : typeof value === "boolean"
      ? (value ? "true" : "false")
      : value === null || value === undefined
        ? ""
        : String(value);

  if (field && op) {
    const operatorLabel = op === "eq" ? "=" : op === "neq" ? "!=" : op === "in" ? "в списке" : op;
    return `${field} ${operatorLabel} ${displayValue}`.trim();
  }

  if (Array.isArray(condition.all) || Array.isArray(condition.any)) {
    return "Составное условие из нескольких правил";
  }

  return "Сложное условие правила";
}

function hydrateDraft(payload: Pick<AdminFormsPayload, "summary" | "forms">): DraftCatalog {
  return {
    title: payload.summary.title,
    description: payload.summary.description ?? "",
    forms: payload.forms.map((form) => ({
      key: form.key,
      request_kind: form.request_kind,
      ticket_type: normalizeTicketType(form.ticket_type, form.key, form.request_kind),
      title: form.title,
      description: form.description ?? "",
      category_id: form.category_id != null ? String(form.category_id) : "",
      service_id: form.service_id != null ? String(form.service_id) : "",
      subcategory_id: form.subcategory_id != null ? String(form.subcategory_id) : "",
      default_queue_id: form.default_queue_id != null ? String(form.default_queue_id) : "",
      sla_policy_id: form.sla_policy_id != null ? String(form.sla_policy_id) : "",
      suggested_playbook_id: form.suggested_playbook_id ?? "",
      priority_impact_field:
        typeof form.priority_policy?.impact_field === "string" ? form.priority_policy.impact_field : "",
      priority_urgency_field:
        typeof form.priority_policy?.urgency_field === "string" ? form.priority_policy.urgency_field : "",
      priority_importance_field:
        typeof form.priority_policy?.importance_field === "string" ? form.priority_policy.importance_field : "",
      field_roles_json: jsonDraft(form.field_roles),
      routing_policy_json: jsonDraft(form.routing_policy),
      approval_policy_json: jsonDraft(form.approval_policy),
      diagnostic_policy_json: jsonDraft(form.diagnostic_policy),
      ola_policy_json: jsonDraft(form.ola_policy),
      closure_policy_json: jsonDraft(form.closure_policy),
      visibility_policy_json: jsonDraft(form.visibility_policy),
      notification_policy_json: jsonDraft(form.notification_policy),
      reporting_policy_json: jsonDraft(form.reporting_policy),
      playbook_triggers: form.playbook_triggers ?? [],
      fields: form.fields.map((field) => ({
        key: field.key,
        label: field.label,
        type: field.type,
        required: field.required,
        placeholder: field.placeholder ?? "",
        help_text: field.help_text ?? "",
        options: field.options.map((option) => ({
          value: option.value,
          label: option.label,
        })),
        validation: field.validation ?? {},
        process_mapping: field.process_mapping ?? {},
        visible_when: {
          field: field.visible_when?.field ?? "",
          equals: field.visible_when?.equals ?? "",
          values: [...(field.visible_when?.values ?? [])],
        },
      })),
    })),
  };
}

function hydrateDraftFromPack(pack: Record<string, unknown>): DraftCatalog {
  const formsRaw = Array.isArray(pack.forms) ? pack.forms : [];
  return {
    title: String(pack.title ?? "Каталог заявок"),
    description: String(pack.description ?? ""),
    forms: formsRaw.map((formRaw, formIndex) => {
      const form = typeof formRaw === "object" && formRaw !== null ? formRaw : {};
      const fieldsRaw = Array.isArray((form as { fields?: unknown[] }).fields)
        ? ((form as { fields: unknown[] }).fields ?? [])
        : [];
      const formKey = String((form as { key?: unknown }).key ?? `form_${formIndex + 1}`);
      const requestKind = String((form as { request_kind?: unknown }).request_kind ?? formKey);

      return {
        key: formKey,
        request_kind: requestKind,
        title: String((form as { title?: unknown }).title ?? "Новая форма"),
        description: String((form as { description?: unknown }).description ?? ""),
        ticket_type: normalizeTicketType((form as { ticket_type?: unknown }).ticket_type, formKey, requestKind),
        category_id: String((form as { category_id?: unknown }).category_id ?? ""),
        service_id: String((form as { service_id?: unknown }).service_id ?? ""),
        subcategory_id: String((form as { subcategory_id?: unknown }).subcategory_id ?? ""),
        default_queue_id: String((form as { default_queue_id?: unknown }).default_queue_id ?? ""),
        sla_policy_id: String((form as { sla_policy_id?: unknown }).sla_policy_id ?? ""),
        suggested_playbook_id: String((form as { suggested_playbook_id?: unknown }).suggested_playbook_id ?? ""),
        priority_impact_field: String(
          ((form as { priority_policy?: Record<string, unknown> }).priority_policy ?? {}).impact_field ?? ""
        ),
        priority_urgency_field: String(
          ((form as { priority_policy?: Record<string, unknown> }).priority_policy ?? {}).urgency_field ?? ""
        ),
        priority_importance_field: String(
          ((form as { priority_policy?: Record<string, unknown> }).priority_policy ?? {}).importance_field ?? ""
        ),
        field_roles_json: jsonDraft((form as { field_roles?: unknown }).field_roles),
        routing_policy_json: jsonDraft((form as { routing_policy?: unknown }).routing_policy),
        approval_policy_json: jsonDraft((form as { approval_policy?: unknown }).approval_policy),
        diagnostic_policy_json: jsonDraft((form as { diagnostic_policy?: unknown }).diagnostic_policy),
        ola_policy_json: jsonDraft((form as { ola_policy?: unknown }).ola_policy),
        closure_policy_json: jsonDraft((form as { closure_policy?: unknown }).closure_policy),
        visibility_policy_json: jsonDraft((form as { visibility_policy?: unknown }).visibility_policy),
        notification_policy_json: jsonDraft((form as { notification_policy?: unknown }).notification_policy),
        reporting_policy_json: jsonDraft((form as { reporting_policy?: unknown }).reporting_policy),
        playbook_triggers: Array.isArray((form as { playbook_triggers?: unknown[] }).playbook_triggers)
          ? ((form as { playbook_triggers: unknown[] }).playbook_triggers ?? [])
              .map((triggerRaw) => {
                const trigger = typeof triggerRaw === "object" && triggerRaw !== null ? triggerRaw : {};
                const moduleKind: AdminFormsPlaybookTrigger["module_kind"] =
                  String((trigger as { module_kind?: unknown }).module_kind ?? "diagnostic") === "remediation"
                    ? "remediation"
                    : "diagnostic";
                return {
                  event: "ticket_created" as const,
                  playbook_key: String((trigger as { playbook_key?: unknown }).playbook_key ?? ""),
                  module_kind: moduleKind,
                  enabled: Boolean((trigger as { enabled?: unknown }).enabled ?? true),
                };
              })
              .filter((trigger) => trigger.playbook_key.trim())
          : [],
        fields: fieldsRaw.map((fieldRaw, fieldIndex) => {
          const field = typeof fieldRaw === "object" && fieldRaw !== null ? fieldRaw : {};
          const optionsRaw = Array.isArray((field as { options?: unknown[] }).options)
            ? ((field as { options: unknown[] }).options ?? [])
            : [];
          const visibleWhen =
            typeof (field as { visible_when?: unknown }).visible_when === "object" &&
            (field as { visible_when?: unknown }).visible_when !== null
              ? ((field as { visible_when: Record<string, unknown> }).visible_when ?? {})
              : {};
          return {
            key: String((field as { key?: unknown }).key ?? `field_${fieldIndex + 1}`),
            label: String((field as { label?: unknown }).label ?? "Поле"),
            type: String((field as { type?: unknown }).type ?? "text") as AdminFormsFieldType,
            required: Boolean((field as { required?: unknown }).required),
            placeholder: String((field as { placeholder?: unknown }).placeholder ?? ""),
            help_text: String((field as { help_text?: unknown }).help_text ?? ""),
            options: optionsRaw
              .map((optionRaw) => {
                const option = typeof optionRaw === "object" && optionRaw !== null ? optionRaw : {};
                return {
                  value: String((option as { value?: unknown }).value ?? ""),
                  label: String((option as { label?: unknown }).label ?? ""),
                };
              })
              .filter((option) => option.value.trim() && option.label.trim()),
            visible_when: {
              field: String(visibleWhen.field ?? ""),
              equals: String(visibleWhen.equals ?? ""),
              values: Array.isArray(visibleWhen.values)
                ? visibleWhen.values.map((item) => String(item ?? ""))
                : Array.isArray(visibleWhen.in)
                  ? visibleWhen.in.map((item) => String(item ?? ""))
                  : [],
            },
          };
        }),
      };
    }),
  };
}

function serializeDraft(catalog: DraftCatalog): AdminFormsSaveRequest {
  return {
    title: catalog.title,
    description: catalog.description,
    forms: catalog.forms.map((form) => ({
      key: form.key,
      request_kind: form.request_kind,
      ticket_type: form.ticket_type,
      title: form.title,
      description: form.description,
      category_id: parseOptionalInt(form.category_id),
      service_id: parseOptionalInt(form.service_id),
      subcategory_id: parseOptionalInt(form.subcategory_id),
      default_queue_id: parseOptionalInt(form.default_queue_id),
      sla_policy_id: parseOptionalInt(form.sla_policy_id),
      suggested_playbook_id: form.suggested_playbook_id.trim() || undefined,
      field_roles: parseFieldRolesDraft(form.field_roles_json),
      priority_policy: {
        ...(form.priority_impact_field.trim() ? { impact_field: form.priority_impact_field.trim() } : {}),
        ...(form.priority_urgency_field.trim() ? { urgency_field: form.priority_urgency_field.trim() } : {}),
        ...(form.priority_importance_field.trim()
          ? { importance_field: form.priority_importance_field.trim() }
          : {}),
        modifier_fields: {
          critical_service: "critical_service",
          public_service: "public_service",
        },
      },
      routing_policy: parseJsonDraft(form.routing_policy_json),
      approval_policy: parseJsonDraft(form.approval_policy_json),
      diagnostic_policy: parseJsonDraft(form.diagnostic_policy_json),
      ola_policy: parseJsonDraft(form.ola_policy_json),
      closure_policy: parseJsonDraft(form.closure_policy_json),
      visibility_policy: parseJsonDraft(form.visibility_policy_json),
      notification_policy: parseJsonDraft(form.notification_policy_json),
      reporting_policy: parseJsonDraft(form.reporting_policy_json),
      playbook_triggers: form.playbook_triggers,
      fields: form.fields.map((field) => {
        const options = field.options.filter((option) => option.value.trim() && option.label.trim());
        const values = field.visible_when.values.filter((item) => item.trim());
        const visibleWhen =
          field.visible_when.field.trim() && (field.visible_when.equals.trim() || values.length)
            ? {
                field: field.visible_when.field.trim(),
                ...(field.visible_when.equals.trim()
                  ? {
                      equals: field.visible_when.equals.trim(),
                    }
                  : {}),
                ...(values.length
                  ? {
                      values,
                    }
                  : {}),
              }
            : undefined;

        return {
          key: field.key,
          label: field.label,
          type: field.type,
          required: field.required,
          ...(field.placeholder.trim()
            ? {
                placeholder: field.placeholder.trim(),
              }
            : {}),
          ...(field.help_text.trim()
            ? {
                help_text: field.help_text.trim(),
              }
            : {}),
          options,
          ...(Object.keys(field.validation ?? {}).length
            ? {
                validation: field.validation ?? {},
              }
            : {}),
          ...(Object.keys(field.process_mapping ?? {}).length
            ? {
                process_mapping: field.process_mapping ?? {},
              }
            : {}),
          ...(visibleWhen
            ? {
                visible_when: visibleWhen,
              }
            : {}),
        };
      }),
    })),
  };
}


function serializeDraftForm(form: DraftForm): AdminFormsSaveRequest["forms"][number] {
  return serializeDraft({
    title: "Preview",
    description: "",
    forms: [form],
  }).forms[0];
}

function buildDraftFingerprint(catalog: DraftCatalog | null): string {
  return JSON.stringify(catalog ? serializeDraft(catalog) : null);
}

function createEmptyField(type: AdminFormsFieldType, index: number): DraftField {
  const baseKey = type === "checkbox" ? "confirmed" : "field";
  return {
    key: `${baseKey}_${index}`,
    label: "Новое поле",
    type,
    required: false,
    placeholder: "",
    help_text: "",
    options:
      type === "select" || type === "radio"
        ? [
            { value: "option_1", label: "Вариант 1" },
            { value: "option_2", label: "Вариант 2" },
          ]
        : [],
    visible_when: {
      field: "",
      equals: "",
      values: [],
    },
  };
}

function createEmptyForm(index: number): DraftForm {
  const key = `new_form_${index}`;
  return {
    key,
    request_kind: key,
    title: "Новая форма",
    description: "",
    ticket_type: "service_request",
    category_id: "",
    service_id: "",
    subcategory_id: "",
    default_queue_id: "",
    sla_policy_id: "",
    suggested_playbook_id: "",
    priority_impact_field: "",
    priority_urgency_field: "",
    priority_importance_field: "",
    field_roles_json: "",
    routing_policy_json: "",
    approval_policy_json: "",
    diagnostic_policy_json: "",
    ola_policy_json: "",
    closure_policy_json: "",
    visibility_policy_json: "",
    notification_policy_json: "",
    reporting_policy_json: "",
    playbook_triggers: [],
    fields: [createEmptyField("text", 1)],
  };
}

function getFieldRoles(form: DraftForm, fieldKey: string): string[] {
  return parseFieldRolesDraft(form.field_roles_json)[fieldKey] ?? [];
}

function updateFieldRoles(form: DraftForm, fieldKey: string, role: string, enabled: boolean): DraftForm {
  const roles = parseFieldRolesDraft(form.field_roles_json);
  const current = new Set(roles[fieldKey] ?? []);
  if (enabled) {
    current.add(role);
  } else {
    current.delete(role);
  }
  if (current.size) {
    roles[fieldKey] = Array.from(current);
  } else {
    delete roles[fieldKey];
  }
  return {
    ...form,
    field_roles_json: jsonDraft(roles),
  };
}

function applyPriorityQuestionTemplate(form: DraftForm): DraftForm {
  const existingKeys = new Set(form.fields.map((field) => field.key));
  const fields = [
    ...form.fields,
    ...PRIORITY_QUESTION_FIELDS.filter((field) => !existingKeys.has(field.key)).map((field) => ({
      ...field,
      options: field.options.map((option) => ({ ...option })),
      visible_when: { ...field.visible_when, values: [...field.visible_when.values] },
    })),
  ];
  const roles = parseFieldRolesDraft(form.field_roles_json);
  for (const field of PRIORITY_QUESTION_FIELDS) {
    roles[field.key] = field.key === "critical_service" || field.key === "public_service"
      ? ["priority_field", "sla_field"]
      : ["priority_field"];
  }
  return {
    ...form,
    fields,
    priority_impact_field: "impact_scope",
    priority_urgency_field: "work_continuity",
    priority_importance_field: "business_importance",
    field_roles_json: jsonDraft(roles),
  };
}

function nextFormIndex(forms: DraftForm[]): number {
  return forms.length + 1;
}

function nextFieldIndex(fields: DraftField[]): number {
  return fields.length + 1;
}

function updateFieldOption(field: DraftField, index: number, patch: Partial<AdminFormsFieldOption>): DraftField {
  return {
    ...field,
    options: field.options.map((option, optionIndex) =>
      optionIndex === index
        ? {
            ...option,
            ...patch,
          }
        : option
    ),
  };
}

function addFieldOption(field: DraftField): DraftField {
  const nextIndex = field.options.length + 1;
  return {
    ...field,
    options: [
      ...field.options,
      {
        value: `option_${nextIndex}`,
        label: `Вариант ${nextIndex}`,
      },
    ],
  };
}

function removeFieldOption(field: DraftField, index: number): DraftField {
  return {
    ...field,
    options: field.options.filter((_, optionIndex) => optionIndex !== index),
  };
}

function isPreviewFieldVisible(field: DraftField, values: PreviewFormValues): boolean {
  const dependencyKey = field.visible_when.field.trim();
  if (!dependencyKey) {
    return true;
  }
  const currentValue = values[dependencyKey];
  if (field.visible_when.equals.trim()) {
    return String(currentValue ?? "").trim() === field.visible_when.equals.trim();
  }
  const allowed = field.visible_when.values.map((item) => item.trim()).filter(Boolean);
  if (allowed.length === 0) {
    return true;
  }
  return allowed.includes(String(currentValue ?? "").trim());
}


function buildPreviewValues(form: DraftForm | null, current: PreviewFormValues = {}): PreviewFormValues {
  if (!form) {
    return {};
  }
  return Object.fromEntries(
    form.fields.map((field) => {
      const existing = current[field.key];
      return [
        field.key,
        typeof existing !== "undefined" ? existing : field.type === "checkbox" ? false : "",
      ];
    })
  );
}

function validatePreviewValues(form: DraftForm | null, values: PreviewFormValues): PreviewValidationIssue[] {
  if (!form) {
    return [];
  }

  return form.fields
    .filter((field) => field.required && isPreviewFieldVisible(field, values))
    .filter((field) => {
      const value = values[field.key];
      return field.type === "checkbox" ? value !== true : !String(value ?? "").trim();
    })
    .map((field) => ({
      key: field.key,
      message: `Заполните поле «${field.label}».`,
    }));
}

function validateDraftCatalog(catalog: DraftCatalog | null): DraftValidationIssue[] {
  if (!catalog) {
    return [];
  }

  const issues: DraftValidationIssue[] = [];
  const formKeys = new Set<string>();

  catalog.forms.forEach((form, formIndex) => {
    const formLabel = form.title.trim() || form.key.trim() || `Форма ${formIndex + 1}`;
    const formKey = form.key.trim();

    if (!formKey) {
      issues.push({
        key: `form-${formIndex}-key`,
        severity: "error",
        message: `У формы «${formLabel}» нужен ключ формы.`,
      });
    } else if (formKeys.has(formKey)) {
      issues.push({
        key: `form-${formIndex}-duplicate`,
        severity: "error",
        message: `Ключ формы «${formKey}» используется повторно.`,
      });
    }
    formKeys.add(formKey);

    if (!form.request_kind.trim()) {
      issues.push({
        key: `form-${formIndex}-request-kind`,
        severity: "error",
        message: `У формы «${formLabel}» нужен request_kind.`,
      });
    }

    const enabledTrigger = form.playbook_triggers.find((trigger) => trigger.enabled);
    if (enabledTrigger && !enabledTrigger.playbook_key.trim()) {
      issues.push({
        key: `form-${formIndex}-playbook-key`,
        severity: "error",
        message: "Укажите ключ плейбука или выключите автозапуск.",
      });
    }

    const fieldKeys = new Set<string>();
    form.fields.forEach((field, fieldIndex) => {
      const fieldLabel = field.label.trim() || field.key.trim() || `Поле ${fieldIndex + 1}`;
      const fieldKey = field.key.trim();

      if (!fieldKey) {
        issues.push({
          key: `form-${formIndex}-field-${fieldIndex}-key`,
          severity: "error",
          message: `У поля «${fieldLabel}» нужен ключ.`,
        });
      } else if (fieldKeys.has(fieldKey)) {
        issues.push({
          key: `form-${formIndex}-field-${fieldIndex}-duplicate`,
          severity: "error",
          message: `Ключ поля «${fieldKey}» используется повторно в форме «${formLabel}».`,
        });
      }
      fieldKeys.add(fieldKey);

      if (!field.label.trim()) {
        issues.push({
          key: `form-${formIndex}-field-${fieldIndex}-label`,
          severity: "error",
          message: `У поля «${fieldKey || fieldIndex + 1}» нужно название.`,
        });
      }

      if ((field.type === "select" || field.type === "radio") && field.options.length === 0) {
        issues.push({
          key: `form-${formIndex}-field-${fieldIndex}-options`,
          severity: "error",
          message: `У поля «${fieldLabel}» нужны варианты ответа.`,
        });
      }

      if (field.visible_when.field && !fieldKeys.has(field.visible_when.field)) {
        const dependencyExists = form.fields.some((item) => item.key === field.visible_when.field);
        if (!dependencyExists) {
          issues.push({
            key: `form-${formIndex}-field-${fieldIndex}-visible-when`,
            severity: "warning",
            message: `Условие показа поля «${fieldLabel}» ссылается на неизвестное поле.`,
          });
        }
      }
    });
  });

  return issues;
}

function updateFormInCatalog(
  catalog: DraftCatalog,
  formKey: string,
  updater: (form: DraftForm) => DraftForm
): DraftCatalog {
  return {
    ...catalog,
    forms: catalog.forms.map((form) => (form.key === formKey ? updater(form) : form)),
  };
}

function updateFieldInCatalog(
  catalog: DraftCatalog,
  formKey: string,
  fieldKey: string,
  updater: (field: DraftField) => DraftField
): DraftCatalog {
  return updateFormInCatalog(catalog, formKey, (form) => ({
    ...form,
    fields: form.fields.map((field) => (field.key === fieldKey ? updater(field) : field)),
  }));
}


function clearVisibleWhenConfig(field: DraftField): DraftField {
  return {
    ...field,
    visible_when: {
      field: "",
      equals: "",
      values: [],
    },
  };
}


function renameFieldInForm(form: DraftForm, fromKey: string, toKey: string): DraftForm {
  return {
    ...form,
    fields: form.fields.map((field) => {
      if (field.key === fromKey) {
        return {
          ...field,
          key: toKey,
        };
      }
      if (field.visible_when.field !== fromKey) {
        return field;
      }
      return {
        ...field,
        visible_when: {
          ...field.visible_when,
          field: toKey,
        },
      };
    }),
  };
}


function removeFieldFromForm(form: DraftForm, fieldKey: string): DraftForm {
  return {
    ...form,
    fields: form.fields
      .filter((field) => field.key !== fieldKey)
      .map((field) => (field.visible_when.field === fieldKey ? clearVisibleWhenConfig(field) : field)),
  };
}

function fieldTypeRequiresOptions(field: AdminFormsFieldItem | DraftField | null): boolean {
  return field?.type === "select" || field?.type === "radio";
}

function fieldTypeLabel(type: AdminFormsFieldType): string {
  switch (type) {
    case "textarea":
      return "Многострочное";
    case "select":
      return "Список";
    case "radio":
      return "Переключатель";
    case "checkbox":
      return "Флажок";
    default:
      return "Текст";
  }
}

function getVisibilityMode(field: DraftField): "always" | "equals" | "values" {
  if (!field.visible_when.field.trim()) {
    return "always";
  }
  if (field.visible_when.values.length > 0) {
    return "values";
  }
  return "equals";
}

function getDependencyFields(form: DraftForm, fieldKey: string): DraftField[] {
  return form.fields.filter((field) => field.key !== fieldKey);
}

function getDependencyValueOptions(field: DraftField | null | undefined): AdminFormsFieldOption[] {
  if (!field) {
    return [];
  }
  if (field.type === "checkbox") {
    return [
      { value: "true", label: "Да" },
      { value: "false", label: "Нет" },
    ];
  }
  if (field.type === "select" || field.type === "radio") {
    return field.options;
  }
  return [];
}

function versionMatchesSearch(item: TicketFormsPackSummary, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    item.version,
    item.title,
    item.description ?? "",
    item.created_by ?? "",
    item.notes ?? "",
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function resolveOptionalAccess(permissions: string[] | undefined, permission: string): PermissionDecision {
  return permissions === undefined ? { allowed: true, reason: null } : requirePermission({ permissions }, permission);
}

const TEMPLATE_STEPS: Array<{
  key: TemplateStepKey;
  title: string;
  shortTitle: string;
  description: string;
  icon: typeof ClipboardList;
}> = [
  {
    key: "template",
    title: "Шаблон обращения",
    shortTitle: "Шаблон",
    description: "Название, код и публичный сценарий",
    icon: ClipboardList,
  },
  {
    key: "form",
    title: "Форма сбора данных",
    shortTitle: "Форма",
    description: "Поля, обязательность и условия показа",
    icon: FilePenLine,
  },
  {
    key: "workflow",
    title: "Процесс",
    shortTitle: "Процесс",
    description: "Тип процесса и профиль workflow",
    icon: Settings2,
  },
  {
    key: "priority",
    title: "Приоритет",
    shortTitle: "Приоритет",
    description: "Поля impact, urgency и importance",
    icon: Gauge,
  },
  {
    key: "deadlines",
    title: "Сроки ответа",
    shortTitle: "Сроки",
    description: "SLA/OLA без технического языка для пользователя",
    icon: FileClock,
  },
  {
    key: "routing",
    title: "Роутинг",
    shortTitle: "Роутинг",
    description: "Очередь, правила и fallback",
    icon: Route,
  },
  {
    key: "approvals",
    title: "Согласования",
    shortTitle: "Согласования",
    description: "Кто согласует и что делать при отказе",
    icon: UserCheck,
  },
  {
    key: "diagnostics",
    title: "Диагностика",
    shortTitle: "Диагностика",
    description: "Playbook, consent и доказательства",
    icon: Stethoscope,
  },
  {
    key: "closure",
    title: "Закрытие",
    shortTitle: "Закрытие",
    description: "Коды решения, итог и evidence",
    icon: FileCheck2,
  },
  {
    key: "visibility",
    title: "Видимость",
    shortTitle: "Видимость",
    description: "Что видит пользователь и support",
    icon: Eye,
  },
  {
    key: "notifications",
    title: "Уведомления",
    shortTitle: "Уведомления",
    description: "Кому писать при событиях",
    icon: BellRing,
  },
  {
    key: "reporting",
    title: "Паспорт решения",
    shortTitle: "Паспорт",
    description: "Разделы, evidence package и экспорт",
    icon: FileCheck2,
  },
];

type PolicyJsonField =
  | "routing_policy_json"
  | "approval_policy_json"
  | "diagnostic_policy_json"
  | "ola_policy_json"
  | "closure_policy_json"
  | "visibility_policy_json"
  | "notification_policy_json"
  | "reporting_policy_json";

function policyObject(form: DraftForm, field: PolicyJsonField): Record<string, unknown> {
  return parseJsonDraft(form[field]);
}

function policySize(form: DraftForm, field: PolicyJsonField): number {
  return Object.keys(policyObject(form, field)).length;
}

function prettyJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function buildRoutingPreset(form: DraftForm): string {
  return prettyJson({
    default_queue: form.default_queue_id.trim() || "servicedesk_l1",
    rules: [
      {
        priority_order: 10,
        when: {
          field: "request_form_data.affected_scope",
          op: "in",
          values: ["department", "whole_building"],
        },
        then: {
          queue: "networks",
          priority_boost: 1,
          suggested_playbook: form.suggested_playbook_id.trim() || "diagnose.network.basic",
        },
      },
    ],
    fallback: {
      queue: form.default_queue_id.trim() || "servicedesk_l1",
    },
    max_auto_reroutes: 3,
    do_not_reroute_if_assignee_locked: true,
  });
}

function buildPriorityPreset(form: DraftForm): string {
  return prettyJson({
    impact_field: form.priority_impact_field.trim() || "impact_scope",
    urgency_field: form.priority_urgency_field.trim() || "work_continuity",
    importance_field: form.priority_importance_field.trim() || "business_importance",
    modifier_fields: {
      critical_service: "critical_service",
      public_service: "public_service",
    },
    manual_override: {
      allowed_roles: ["support", "queue_lead", "admin"],
      require_reason: true,
      log_event: true,
    },
  });
}

function buildSlaPreset(form: DraftForm): string {
  return prettyJson({
    sla_policy_id: form.sla_policy_id.trim() ? Number(form.sla_policy_id.trim()) : null,
    calendar_id: "work_hours_5x8",
    targets: {
      first_response: { P0: "15m", P1: "1h", P2: "4h", P3: "1d" },
      resolution: { P0: "4h", P1: "1d", P2: "3d", P3: "5d" },
    },
    pause_conditions: ["waiting_user", "waiting_approval"],
    stop_conditions: {
      first_response: ["first_public_support_reply_sent"],
      resolution: ["resolved", "closed"],
    },
    breach_actions: {
      notify: ["assignee", "queue_lead"],
      warning_before: { first_response: "30m", resolution: "4h" },
    },
  });
}

function buildOlaPreset(): string {
  return prettyJson({
    targets: {
      ack: { P0: "10m", P1: "30m", P2: "2h", P3: "1d" },
      processing: { P0: "2h", P1: "4h", P2: "2d", P3: "5d" },
    },
    pause_conditions: ["waiting_user", "waiting_approval"],
    breach_actions: {
      notify_queue_lead: true,
      create_internal_event: true,
    },
  });
}

function buildApprovalPreset(): string {
  return prettyJson({
    required: true,
    approver_source: { type: "service_owner", fallback: "requester_manager" },
    approval_mode: "any_one",
    statuses: {
      waiting_status: "waiting_approval",
      approved_transition: "in_progress",
      rejected_transition: "canceled",
    },
    require_comment_on_reject: true,
    log_to_passport: true,
  });
}

function buildDiagnosticPreset(form: DraftForm): string {
  return prettyJson({
    suggested_playbooks: [form.suggested_playbook_id.trim() || "diagnose.website"],
    auto_run: { enabled: false, only_if_agent_online: true, only_for_priorities: ["P0", "P1", "P2"] },
    consent: { required_for_requester_device: true, required_for_high_risk_tools: true },
    attach_results: { to_timeline: true, to_passport: true, as_evidence: true },
    reroute_by_result: {
      DNS_FAIL: "networks",
      HTTP_500: "information_systems",
      TLS_CERT_INVALID: "security_or_servers",
    },
  });
}

function buildClosurePreset(): string {
  return prettyJson({
    before_resolved: {
      require_resolution_code: true,
      require_public_summary: true,
      require_internal_summary: false,
    },
    evidence: {
      require_evidence_for_priorities: ["P0", "P1"],
      require_operation_log_if_module_used: true,
      require_approval_if_approval_policy_used: true,
    },
    requester_confirmation: {
      required: true,
      auto_close_after_days: 3,
      reopen_on_negative_feedback: true,
    },
    allowed_resolution_codes: ["fixed_remote", "workaround_provided", "external_issue", "user_error"],
  });
}

function buildVisibilityPreset(): string {
  return prettyJson({
    public_status_mapping: {
      new: "Заявка принята",
      queued: "Заявка принята",
      assigned: "Заявка в работе",
      in_progress: "Заявка в работе",
      waiting_user: "Нужен ваш ответ",
      waiting_approval: "Ожидает согласование",
      resolved: "Проверьте решение",
      closed: "Закрыта",
      canceled: "Отменена",
    },
    hide_from_requester: ["internal_notes", "ola_details", "raw_diagnostics", "internal_queue_comments"],
    show_to_requester: ["public_messages", "public_status", "attachments_public", "expected_due_at"],
  });
}

function buildNotificationPreset(): string {
  return prettyJson({
    on_created: { requester: true, queue: true },
    on_assigned: { assignee: true },
    on_waiting_user: { requester: true },
    on_requester_replied: { assignee: true, queue_if_no_assignee: true },
    on_sla_warning: { assignee: true, queue_lead: true },
    on_sla_breach: { assignee: true, queue_lead: true },
    on_resolved: { requester: true },
    channels: { email: true, web: true, telegram: false },
  });
}

function buildReportingPreset(): string {
  return prettyJson({
    required_sections: ["requester", "problem", "affected_object", "automated_checks", "evidence", "user_result"],
    evidence_package: {
      include_action_log: true,
      include_related_objects: true,
    },
    action_package: {
      include_worklog: true,
      include_approvals: true,
    },
    export_visibility: {
      hide_sections: ["internal_result"],
    },
    report_tags: ["standard_passport"],
    require_official_passport: false,
    knowledge_draft_hints: {
      enabled: false,
    },
  });
}

function policyBadgeTone(count: number): "success" | "warning" | "neutral" {
  if (count > 0) {
    return "success";
  }
  return "warning";
}

function PolicyJsonEditor({
  title,
  description,
  value,
  presetLabel,
  presetValue,
  onChange,
}: {
  title: string;
  description: string;
  value: string;
  presetLabel: string;
  presetValue: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">{title}</p>
          <p className="mt-1 text-xs text-slate-500">{description}</p>
        </div>
        <Button onClick={() => onChange(presetValue)} size="sm" variant="outline">
          {presetLabel}
        </Button>
      </div>
      <textarea
        className="field-base mt-4 min-h-[180px] w-full resize-y px-4 py-3 font-mono text-xs leading-5"
        onChange={(event) => onChange(event.currentTarget.value)}
        spellCheck={false}
        value={value}
      />
    </div>
  );
}

type PolicyEditorKind =
  | "priority"
  | "sla"
  | "ola"
  | "routing"
  | "approval"
  | "closure"
  | "diagnostic"
  | "notification"
  | "visibility"
  | "reporting";

type PolicyEditorDraft = {
  kind: PolicyEditorKind;
  code: string;
  title: string;
  description: string;
  scope_level: "system" | "ticket_type" | "category" | "request_template";
  scope_ref: string;
  jsonText: string;
};

const POLICY_EDITOR_ITEMS: Array<{ kind: PolicyEditorKind; label: string; description: string }> = [
  { kind: "priority", label: "Приоритет", description: "Поля влияния, срочности и override" },
  { kind: "sla", label: "Срок ответа", description: "Когда вам должны ответить и решить" },
  { kind: "ola", label: "Внутренний срок", description: "Срок принятия и обработки очередью" },
  { kind: "routing", label: "Роутинг", description: "Очереди, fallback и защита от перекидывания" },
  { kind: "approval", label: "Согласования", description: "Кто согласует, сроки и отказ" },
  { kind: "closure", label: "Закрытие", description: "Коды решения, итог и доказательства" },
  { kind: "diagnostic", label: "Диагностика", description: "Playbook, consent и evidence" },
  { kind: "notification", label: "Уведомления", description: "Получатели и каналы событий" },
  { kind: "visibility", label: "Видимость", description: "Публичные статусы и скрытые поля" },
  { kind: "reporting", label: "Паспорт решения", description: "Разделы паспорта, evidence package и теги отчёта" },
];

function parseEditorJson(text: string): Record<string, unknown> {
  const parsed = JSON.parse(text || "{}") as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Политика должна быть JSON-объектом.");
  }
  return parsed as Record<string, unknown>;
}

function policyEditorPreset(kind: PolicyEditorKind, form: DraftForm): Record<string, unknown> {
  if (kind === "priority") {
    const existing = {
      ...(form.priority_impact_field.trim() ? { impact_field: form.priority_impact_field.trim() } : {}),
      ...(form.priority_urgency_field.trim() ? { urgency_field: form.priority_urgency_field.trim() } : {}),
      ...(form.priority_importance_field.trim() ? { importance_field: form.priority_importance_field.trim() } : {}),
    };
    return Object.keys(existing).length ? existing : parseJsonDraft(buildPriorityPreset(form));
  }
  if (kind === "sla") {
    return parseJsonDraft(buildSlaPreset(form));
  }
  const fieldByKind: Partial<Record<Exclude<PolicyEditorKind, "priority" | "sla">, PolicyJsonField>> = {
    ola: "ola_policy_json",
    routing: "routing_policy_json",
    approval: "approval_policy_json",
    closure: "closure_policy_json",
    diagnostic: "diagnostic_policy_json",
    notification: "notification_policy_json",
    visibility: "visibility_policy_json",
    reporting: "reporting_policy_json",
  };
  const fieldName = fieldByKind[kind];
  const existing = fieldName ? parseJsonDraft(form[fieldName]) : {};
  if (Object.keys(existing).length) {
    return existing;
  }
  const presetText =
    kind === "ola"
      ? buildOlaPreset()
      : kind === "routing"
      ? buildRoutingPreset(form)
      : kind === "approval"
        ? buildApprovalPreset()
        : kind === "closure"
          ? buildClosurePreset()
          : kind === "diagnostic"
            ? buildDiagnosticPreset(form)
            : kind === "notification"
              ? buildNotificationPreset()
              : kind === "reporting"
                ? buildReportingPreset()
              : buildVisibilityPreset();
  return parseJsonDraft(presetText);
}

function buildPolicyEditorDraft(kind: PolicyEditorKind, form: DraftForm | null): PolicyEditorDraft {
  const codeBase = form?.key?.trim() || "request_template";
  const titleBase = form?.title?.trim() || codeBase;
  const item = POLICY_EDITOR_ITEMS.find((entry) => entry.kind === kind);
  return {
    kind,
    code: `${codeBase}_${kind}_policy`,
    title: `${titleBase}: ${item?.label ?? kind}`,
    description: `Политика опубликована из редактора целевой модели для шаблона ${codeBase}.`,
    scope_level: "request_template",
    scope_ref: codeBase,
    jsonText: prettyJson(form ? policyEditorPreset(kind, form) : {}),
  };
}

function getFirstRule(config: Record<string, unknown>): Record<string, unknown> {
  const rules = Array.isArray(config.rules) ? config.rules : [];
  const first = rules[0];
  return first && typeof first === "object" && !Array.isArray(first) ? (first as Record<string, unknown>) : {};
}

function updateFirstRule(
  config: Record<string, unknown>,
  patch: (rule: Record<string, unknown>) => Record<string, unknown>
): Record<string, unknown> {
  const rules = Array.isArray(config.rules) ? [...config.rules] : [];
  rules[0] = patch(getFirstRule(config));
  return { ...config, rules };
}

function routingValuesText(values: unknown, fallback: unknown): string {
  return Array.isArray(values) ? values.map((item) => String(item)).join(", ") : String(fallback ?? "");
}

function RoutingPolicyControls({
  config,
  form,
  onChange,
}: {
  config: Record<string, unknown>;
  form: DraftForm | null;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const rule = getFirstRule(config);
  const when = typeof rule.when === "object" && rule.when ? (rule.when as Record<string, unknown>) : {};
  const then = typeof rule.then === "object" && rule.then ? (rule.then as Record<string, unknown>) : {};
  const fallback = typeof config.fallback === "object" && config.fallback ? (config.fallback as Record<string, unknown>) : {};
  const currentDefaultQueue = String(config.default_queue ?? config.default_queue_id ?? "");
  const updateDefaultQueue = (queue: string) => {
    const shouldSyncFallback = !fallback.queue || String(fallback.queue) === currentDefaultQueue;
    onChange({
      ...config,
      default_queue: queue,
      fallback: shouldSyncFallback ? { ...fallback, queue } : fallback,
    });
  };
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Очередь по умолчанию</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => updateDefaultQueue(event.currentTarget.value)}
          value={currentDefaultQueue}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Поле условия роутинга</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) =>
            onChange(updateFirstRule(config, (current) => ({ ...current, when: { ...when, field: event.currentTarget.value } })))
          }
          placeholder="request_form_data.affected_scope"
          value={String(when.field ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Значения условия</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) =>
            onChange(
              updateFirstRule(config, (current) => ({
                ...current,
                when: {
                  ...when,
                  op: "in",
                  values: event.currentTarget.value.split(",").map((item) => item.trim()).filter(Boolean),
                },
              }))
            )
          }
          placeholder="department, whole_building"
          value={routingValuesText(when.values, when.value)}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Куда направить</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) =>
            onChange(updateFirstRule(config, (current) => ({ ...current, then: { ...then, queue: event.currentTarget.value } })))
          }
          placeholder={form?.default_queue_id || "servicedesk_l1"}
          value={String(then.queue ?? then.queue_id ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Повысить приоритет на</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) =>
            onChange(
              updateFirstRule(config, (current) => ({
                ...current,
                then: { ...then, priority_boost: Number(event.currentTarget.value || 0) },
              }))
            )
          }
          type="number"
          value={Number(then.priority_boost ?? 0)}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Максимум авто-маршрутов</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, max_auto_reroutes: Number(event.currentTarget.value || 0) })}
          type="number"
          value={Number(config.max_auto_reroutes ?? 3)}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(config.do_not_reroute_if_assignee_locked ?? true)}
        label="Не менять маршрут при закреплённом исполнителе"
        onChange={(checked) => onChange({ ...config, do_not_reroute_if_assignee_locked: checked })}
      />
    </div>
  );
}

function ApprovalPolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const approverSource = nestedObject(config.approver_source);
  const timeout = nestedObject(config.timeout);
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <JsonLinkedCheckbox
        checked={Boolean(config.required)}
        label="Согласование обязательно"
        onChange={(checked) => onChange({ ...config, required: checked })}
      />
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Источник согласующего</span>
        <Select
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, approver_source: { ...approverSource, type: event.currentTarget.value } })}
          value={String(approverSource.type ?? "service_owner")}
        >
          <option value="service_owner">Владелец сервиса</option>
          <option value="requester_manager">Руководитель заявителя</option>
          <option value="security_role">Роль ИБ</option>
          <option value="form_field">Поле формы</option>
          <option value="queue_lead">Руководитель очереди</option>
          <option value="group">Группа</option>
        </Select>
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Поле согласующего</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, approver_source: { ...approverSource, field: event.currentTarget.value } })}
          placeholder="manager_user_id"
          value={String(approverSource.field ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Режим согласования</span>
        <Select
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, approval_mode: event.currentTarget.value })}
          value={String(config.approval_mode ?? "any_one")}
        >
          <option value="any_one">Достаточно одного</option>
          <option value="all">Все согласующие</option>
          <option value="sequential">Последовательно</option>
        </Select>
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Напомнить через</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, timeout: { ...timeout, reminder_after: event.currentTarget.value } })}
          placeholder="4h"
          value={String(timeout.reminder_after ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Эскалировать через</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, timeout: { ...timeout, escalate_after: event.currentTarget.value } })}
          placeholder="2d"
          value={String(timeout.escalate_after ?? "")}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(config.require_comment_on_reject ?? true)}
        label="Комментарий при отказе"
        onChange={(checked) => onChange({ ...config, require_comment_on_reject: checked })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(config.log_to_passport ?? true)}
        label="Писать в паспорт решения"
        onChange={(checked) => onChange({ ...config, log_to_passport: checked })}
      />
    </div>
  );
}

function listFromCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToCsv(list: unknown): string {
  return Array.isArray(list) ? list.map((item) => String(item)).join(", ") : "";
}

function ClosurePolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const before = nestedObject(config.before_resolved);
  const evidence = nestedObject(config.evidence);
  const confirmation = nestedObject(config.requester_confirmation);
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <JsonLinkedCheckbox
        checked={Boolean(before.require_resolution_code ?? true)}
        label="Код решения обязателен"
        onChange={(checked) => onChange({ ...config, before_resolved: { ...before, require_resolution_code: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(before.require_public_summary ?? true)}
        label="Публичный итог обязателен"
        onChange={(checked) => onChange({ ...config, before_resolved: { ...before, require_public_summary: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(before.require_internal_summary)}
        label="Внутренний итог обязателен"
        onChange={(checked) => onChange({ ...config, before_resolved: { ...before, require_internal_summary: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(before.require_worklog)}
        label="Worklog обязателен"
        onChange={(checked) => onChange({ ...config, before_resolved: { ...before, require_worklog: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(evidence.require_operation_log_if_module_used)}
        label="Evidence после модуля"
        onChange={(checked) => onChange({ ...config, evidence: { ...evidence, require_operation_log_if_module_used: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(evidence.require_approval_if_approval_policy_used)}
        label="Evidence по согласованию"
        onChange={(checked) => onChange({ ...config, evidence: { ...evidence, require_approval_if_approval_policy_used: checked } })}
      />
      {["P0", "P1", "P2"].map((priority) => (
        <JsonLinkedCheckbox
          checked={
            Array.isArray(evidence.require_evidence_for_priorities)
              ? evidence.require_evidence_for_priorities.map((item) => String(item)).includes(priority)
              : false
          }
          key={priority}
          label={`Evidence для ${priority}`}
          onChange={(checked) =>
            onChange({
              ...config,
              evidence: {
                ...evidence,
                require_evidence_for_priorities: toggleStringInList(evidence.require_evidence_for_priorities, priority, checked),
              },
            })
          }
        />
      ))}
      <JsonLinkedCheckbox
        checked={Boolean(confirmation.required ?? true)}
        label="Подтверждение пользователя"
        onChange={(checked) => onChange({ ...config, requester_confirmation: { ...confirmation, required: checked } })}
      />
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Автозакрытие через дней</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          min={0}
          onChange={(event) =>
            onChange({ ...config, requester_confirmation: { ...confirmation, auto_close_after_days: Number(event.currentTarget.value || 0) } })
          }
          type="number"
          value={Number(confirmation.auto_close_after_days ?? 3)}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(confirmation.reopen_on_negative_feedback ?? true)}
        label="Открывать при отрицательном отзыве"
        onChange={(checked) => onChange({ ...config, requester_confirmation: { ...confirmation, reopen_on_negative_feedback: checked } })}
      />
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Коды решения</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, allowed_resolution_codes: listFromCsv(event.currentTarget.value) })}
          placeholder="fixed_remote, duplicate, cannot_reproduce"
          value={listToCsv(config.allowed_resolution_codes)}
        />
      </label>
    </div>
  );
}

function DiagnosticPolicyControls({
  config,
  form,
  onChange,
}: {
  config: Record<string, unknown>;
  form?: DraftForm | null;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const autoRun = nestedObject(config.auto_run);
  const consent = nestedObject(config.consent);
  const attach = nestedObject(config.attach_results);
  const reroute = nestedObject(config.reroute_by_result);
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Плейбуки</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, suggested_playbooks: listFromCsv(event.currentTarget.value) })}
          placeholder={form?.suggested_playbook_id || "diagnose.website"}
          value={listToCsv(config.suggested_playbooks)}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(autoRun.enabled)}
        label="Автозапуск"
        onChange={(checked) => onChange({ ...config, auto_run: { ...autoRun, enabled: checked } })}
      />
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Автозапуск для приоритетов</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, auto_run: { ...autoRun, only_for_priorities: listFromCsv(event.currentTarget.value) } })}
          placeholder="P0, P1, P2"
          value={listToCsv(autoRun.only_for_priorities)}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(consent.required_for_requester_device ?? true)}
        label="Нужно согласие пользователя"
        onChange={(checked) => onChange({ ...config, consent: { ...consent, required_for_requester_device: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(consent.required_for_high_risk_tools ?? true)}
        label="Согласие для high-risk tools"
        onChange={(checked) => onChange({ ...config, consent: { ...consent, required_for_high_risk_tools: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(attach.to_timeline ?? true)}
        label="Прикладывать к timeline"
        onChange={(checked) => onChange({ ...config, attach_results: { ...attach, to_timeline: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(attach.to_passport ?? true)}
        label="Прикладывать к паспорту"
        onChange={(checked) => onChange({ ...config, attach_results: { ...attach, to_passport: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(attach.as_evidence ?? true)}
        label="Считать доказательством"
        onChange={(checked) => onChange({ ...config, attach_results: { ...attach, as_evidence: checked } })}
      />
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>DNS_FAIL очередь</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, reroute_by_result: { ...reroute, DNS_FAIL: event.currentTarget.value } })}
          placeholder="networks"
          value={String(reroute.DNS_FAIL ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>HTTP_500 очередь</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, reroute_by_result: { ...reroute, HTTP_500: event.currentTarget.value } })}
          placeholder="information_systems"
          value={String(reroute.HTTP_500 ?? "")}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>TLS_CERT_INVALID очередь</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, reroute_by_result: { ...reroute, TLS_CERT_INVALID: event.currentTarget.value } })}
          placeholder="security_or_servers"
          value={String(reroute.TLS_CERT_INVALID ?? "")}
        />
      </label>
    </div>
  );
}

function VisibilityPolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const mapping = nestedObject(config.public_status_mapping);
  const updateMapping = (status: string, value: string) =>
    onChange({ ...config, public_status_mapping: { ...mapping, [status]: value } });
  const statusControls = [
    ["new", "Новая публично"],
    ["queued", "В очереди публично"],
    ["assigned", "Назначена публично"],
    ["in_progress", "В работе публично"],
    ["waiting_user", "Ожидает пользователя публично"],
    ["waiting_approval", "Ожидает согласование публично"],
    ["resolved", "Решена публично"],
    ["closed", "Закрыта публично"],
    ["canceled", "Отменена публично"],
  ];

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {statusControls.map(([status, label]) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={status}>
          <span>{label}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => updateMapping(status, event.currentTarget.value)}
            value={String(mapping[status] ?? "")}
          />
        </label>
      ))}
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Скрыть от заявителя</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, hide_from_requester: listFromCsv(event.currentTarget.value) })}
          placeholder="internal_notes, ola_details, raw_diagnostics"
          value={listToCsv(config.hide_from_requester)}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Показывать заявителю</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, show_to_requester: listFromCsv(event.currentTarget.value) })}
          placeholder="public_messages, public_status, expected_due_at"
          value={listToCsv(config.show_to_requester)}
        />
      </label>
    </div>
  );
}

function NotificationPolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const channels = nestedObject(config.channels);
  const updateEvent = (eventName: string, field: string, checked: boolean) => {
    const eventConfig = nestedObject(config[eventName]);
    onChange({ ...config, [eventName]: { ...eventConfig, [field]: checked } });
  };
  const updateChannel = (channel: string, checked: boolean) => {
    onChange({ ...config, channels: { ...channels, [channel]: checked } });
  };
  const isEnabled = (eventName: string, field: string, fallback = false) => {
    const eventConfig = nestedObject(config[eventName]);
    return Boolean(eventConfig[field] ?? fallback);
  };

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <JsonLinkedCheckbox
        checked={isEnabled("on_created", "requester")}
        label="Создание: заявителю"
        onChange={(checked) => updateEvent("on_created", "requester", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_created", "queue")}
        label="Создание: очереди"
        onChange={(checked) => updateEvent("on_created", "queue", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_assigned", "assignee")}
        label="Назначение: исполнителю"
        onChange={(checked) => updateEvent("on_assigned", "assignee", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_waiting_user", "requester")}
        label="Ожидание пользователя: заявителю"
        onChange={(checked) => updateEvent("on_waiting_user", "requester", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_requester_replied", "assignee")}
        label="Ответ пользователя: исполнителю"
        onChange={(checked) => updateEvent("on_requester_replied", "assignee", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_requester_replied", "queue_if_no_assignee")}
        label="Ответ пользователя: очередь без исполнителя"
        onChange={(checked) => updateEvent("on_requester_replied", "queue_if_no_assignee", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_sla_warning", "assignee")}
        label="Риск срока: исполнителю"
        onChange={(checked) => updateEvent("on_sla_warning", "assignee", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_sla_warning", "queue_lead")}
        label="Риск срока: руководителю"
        onChange={(checked) => updateEvent("on_sla_warning", "queue_lead", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_sla_breach", "assignee")}
        label="Нарушение срока: исполнителю"
        onChange={(checked) => updateEvent("on_sla_breach", "assignee", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_sla_breach", "queue_lead")}
        label="Нарушение срока: руководителю"
        onChange={(checked) => updateEvent("on_sla_breach", "queue_lead", checked)}
      />
      <JsonLinkedCheckbox
        checked={isEnabled("on_resolved", "requester")}
        label="Решено: заявителю"
        onChange={(checked) => updateEvent("on_resolved", "requester", checked)}
      />
      <JsonLinkedCheckbox
        checked={Boolean(channels.web ?? true)}
        label="Канал: web"
        onChange={(checked) => updateChannel("web", checked)}
      />
      <JsonLinkedCheckbox
        checked={Boolean(channels.email)}
        label="Канал: email"
        onChange={(checked) => updateChannel("email", checked)}
      />
      <JsonLinkedCheckbox
        checked={Boolean(channels.telegram)}
        label="Канал: Telegram"
        onChange={(checked) => updateChannel("telegram", checked)}
      />
      <JsonLinkedCheckbox
        checked={Boolean(channels.vk_teams)}
        label="Канал: VK Teams"
        onChange={(checked) => updateChannel("vk_teams", checked)}
      />
    </div>
  );
}

function toggleStringInList(list: unknown, value: string, enabled: boolean): string[] {
  const set = new Set(Array.isArray(list) ? list.map((item) => String(item)) : []);
  if (enabled) {
    set.add(value);
  } else {
    set.delete(value);
  }
  return Array.from(set);
}

function nestedObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function notifyRecipients(actions: Record<string, unknown>): string[] {
  const notify = actions.notify;
  if (Array.isArray(notify)) {
    return notify.map((item) => String(item)).filter(Boolean);
  }
  if (notify && typeof notify === "object") {
    return Object.entries(notify as Record<string, unknown>)
      .filter(([, enabled]) => Boolean(enabled))
      .map(([recipient]) => recipient);
  }
  return [];
}

function updateNotifyRecipient(actions: Record<string, unknown>, recipient: string, enabled: boolean): Record<string, unknown> {
  return {
    ...actions,
    notify: toggleStringInList(notifyRecipients(actions), recipient, enabled),
  };
}

function JsonLinkedCheckbox({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 rounded-[0.8rem] border border-border bg-white px-3 py-2 text-sm text-slate-700">
      <input checked={checked} onChange={(event) => onChange(event.currentTarget.checked)} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}

function PolicyActionControls({
  actions,
  onChange,
}: {
  actions: Record<string, unknown>;
  onChange: (actions: Record<string, unknown>) => void;
}) {
  const channels = nestedObject(actions.channels ?? actions.external_channels);
  const recipients = notifyRecipients(actions);
  return (
    <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-3 py-3 lg:col-span-full">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">Действия при риске срока</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Эти настройки сохраняются в `breach_actions` и исполняются dispatcher-слоем после события SLA/OLA.
          </p>
        </div>
        <Badge tone="neutral">breach_actions</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        <JsonLinkedCheckbox
          checked={recipients.includes("assignee")}
          label="Уведомить исполнителя"
          onChange={(checked) => onChange(updateNotifyRecipient(actions, "assignee", checked))}
        />
        <JsonLinkedCheckbox
          checked={recipients.includes("queue_lead") || Boolean(actions.notify_queue_lead)}
          label="Уведомить руководителя очереди"
          onChange={(checked) => onChange({ ...updateNotifyRecipient(actions, "queue_lead", checked), notify_queue_lead: checked })}
        />
        <JsonLinkedCheckbox
          checked={Boolean(actions.escalate_to_queue_lead)}
          label="Эскалировать руководителю очереди"
          onChange={(checked) => onChange({ ...actions, escalate_to_queue_lead: checked })}
        />
        <JsonLinkedCheckbox
          checked={Boolean(actions.create_internal_event)}
          label="Создать внутреннее событие"
          onChange={(checked) => onChange({ ...actions, create_internal_event: checked })}
        />
        {["email", "telegram", "vk_teams"].map((channel) => (
          <JsonLinkedCheckbox
            checked={Boolean(channels[channel])}
            key={channel}
            label={`Канал ${channel}`}
            onChange={(checked) => onChange({ ...actions, channels: { ...channels, [channel]: checked } })}
          />
        ))}
      </div>
    </div>
  );
}

function OlaPolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const targets = nestedObject(config.targets);
  const ack = nestedObject(targets.ack);
  const processing = nestedObject(targets.processing);
  const breachActions = nestedObject(config.breach_actions);
  return (
    <div className="grid gap-3 lg:grid-cols-4">
      {["P0", "P1", "P2", "P3"].map((priority) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={`ack-${priority}`}>
          <span>Принять {priority}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, targets: { ...targets, ack: { ...ack, [priority]: event.currentTarget.value } } })}
            value={String(ack[priority] ?? "")}
          />
        </label>
      ))}
      {["P0", "P1", "P2", "P3"].map((priority) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={`processing-${priority}`}>
          <span>Обработать {priority}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) =>
              onChange({ ...config, targets: { ...targets, processing: { ...processing, [priority]: event.currentTarget.value } } })
            }
            value={String(processing[priority] ?? "")}
          />
        </label>
      ))}
      <PolicyActionControls
        actions={breachActions}
        onChange={(actions) => onChange({ ...config, breach_actions: actions })}
      />
    </div>
  );
}

function SlaPolicyControls({
  config,
  form,
  onChange,
}: {
  config: Record<string, unknown>;
  form: DraftForm | null;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const targets = nestedObject(config.targets);
  const firstResponse = nestedObject(targets.first_response);
  const resolution = nestedObject(targets.resolution);
  const breachActions = nestedObject(config.breach_actions);
  return (
    <div className="grid gap-3 lg:grid-cols-4">
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>ID действующей политики сроков</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, sla_policy_id: Number(event.currentTarget.value || 0) || null })}
          placeholder={form?.sla_policy_id || "1"}
          type="number"
          value={Number(config.sla_policy_id ?? 0) || ""}
        />
      </label>
      {["P0", "P1", "P2", "P3"].map((priority) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={`fr-${priority}`}>
          <span>Ответ {priority}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) =>
              onChange({ ...config, targets: { ...targets, first_response: { ...firstResponse, [priority]: event.currentTarget.value } } })
            }
            value={String(firstResponse[priority] ?? "")}
          />
        </label>
      ))}
      {["P0", "P1", "P2", "P3"].map((priority) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={`res-${priority}`}>
          <span>Решение {priority}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) =>
              onChange({ ...config, targets: { ...targets, resolution: { ...resolution, [priority]: event.currentTarget.value } } })
            }
            value={String(resolution[priority] ?? "")}
          />
        </label>
      ))}
      <PolicyActionControls
        actions={breachActions}
        onChange={(actions) => onChange({ ...config, breach_actions: actions })}
      />
    </div>
  );
}

function csvList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).join(", ") : "";
}

function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSortDraft(value: string): Array<Record<string, unknown>> {
  try {
    const parsed = JSON.parse(value || "[]") as unknown;
    return Array.isArray(parsed)
      ? parsed.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
      : [];
  } catch {
    return [];
  }
}

function ReportingPolicyControls({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const evidencePackage = nestedObject(config.evidence_package);
  const actionPackage = nestedObject(config.action_package);
  const exportVisibility = nestedObject(config.export_visibility);
  const knowledgeDraftHints = nestedObject(config.knowledge_draft_hints);

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Разделы паспорта</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, required_sections: csvToList(event.currentTarget.value) })}
          value={csvList(config.required_sections)}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>Теги отчёта</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, report_tags: csvToList(event.currentTarget.value) })}
          value={csvList(config.report_tags)}
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Скрыть из экспорта</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) =>
            onChange({
              ...config,
              export_visibility: {
                ...exportVisibility,
                hide_sections: csvToList(event.currentTarget.value),
              },
            })
          }
          value={csvList(exportVisibility.hide_sections)}
        />
      </label>
      <JsonLinkedCheckbox
        checked={Boolean(evidencePackage.include_action_log ?? true)}
        label="Включать журнал действий"
        onChange={(checked) => onChange({ ...config, evidence_package: { ...evidencePackage, include_action_log: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(evidencePackage.include_related_objects ?? true)}
        label="Включать связанные объекты"
        onChange={(checked) => onChange({ ...config, evidence_package: { ...evidencePackage, include_related_objects: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(actionPackage.include_worklog ?? true)}
        label="Включать worklog"
        onChange={(checked) => onChange({ ...config, action_package: { ...actionPackage, include_worklog: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(actionPackage.include_approvals ?? true)}
        label="Включать согласования"
        onChange={(checked) => onChange({ ...config, action_package: { ...actionPackage, include_approvals: checked } })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(config.include_internal_notes)}
        label="Включать внутренние заметки"
        onChange={(checked) => onChange({ ...config, include_internal_notes: checked })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(config.require_official_passport)}
        label="Требовать официальный паспорт"
        onChange={(checked) => onChange({ ...config, require_official_passport: checked })}
      />
      <JsonLinkedCheckbox
        checked={Boolean(knowledgeDraftHints.enabled)}
        label="Подсказки для базы знаний"
        onChange={(checked) => onChange({ ...config, knowledge_draft_hints: { ...knowledgeDraftHints, enabled: checked } })}
      />
    </div>
  );
}

function PolicyKindControls({
  config,
  form,
  kind,
  onChange,
}: {
  config: Record<string, unknown>;
  form: DraftForm | null;
  kind: PolicyEditorKind;
  onChange: (config: Record<string, unknown>) => void;
}) {
  if (kind === "priority") {
    const manual = typeof config.manual_override === "object" && config.manual_override ? (config.manual_override as Record<string, unknown>) : {};
    const modifierFields =
      typeof config.modifier_fields === "object" && config.modifier_fields ? (config.modifier_fields as Record<string, unknown>) : {};
    return (
      <div className="grid gap-3 lg:grid-cols-3">
        {[
          ["impact_field", "Поле влияния", form?.priority_impact_field || "impact_scope"],
          ["urgency_field", "Поле срочности", form?.priority_urgency_field || "work_continuity"],
          ["importance_field", "Поле важности", form?.priority_importance_field || "business_importance"],
        ].map(([field, label, fallback]) => (
          <label className="space-y-2 text-sm font-medium text-slate-800" key={field}>
            <span>{label}</span>
            <input
              className="field-base h-11 w-full px-4 text-sm"
              onChange={(event) => onChange({ ...config, [field]: event.currentTarget.value })}
              placeholder={fallback}
              value={String(config[field] ?? "")}
            />
          </label>
        ))}
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Флаг критичной системы</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, modifier_fields: { ...modifierFields, critical_service: event.currentTarget.value } })}
            value={String(modifierFields.critical_service ?? "critical_service")}
          />
        </label>
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Флаг публичной услуги</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, modifier_fields: { ...modifierFields, public_service: event.currentTarget.value } })}
            value={String(modifierFields.public_service ?? "public_service")}
          />
        </label>
        <JsonLinkedCheckbox
          checked={Boolean(manual.require_reason ?? true)}
          label="Причина обязательна при ручном изменении"
          onChange={(checked) => onChange({ ...config, manual_override: { ...manual, require_reason: checked } })}
        />
      </div>
    );
  }

  if (kind === "sla") {
    return <SlaPolicyControls config={config} form={form} onChange={onChange} />;
  }

  if (kind === "ola") {
    return <OlaPolicyControls config={config} onChange={onChange} />;
  }

  if (kind === "routing") {
    return <RoutingPolicyControls config={config} form={form} onChange={onChange} />;
  }

  if (kind === "approval") {
    return <ApprovalPolicyControls config={config} onChange={onChange} />;
    const approverSource =
      typeof config.approver_source === "object" && config.approver_source ? (config.approver_source as Record<string, unknown>) : {};
    const timeout = typeof config.timeout === "object" && config.timeout ? (config.timeout as Record<string, unknown>) : {};
    return (
      <div className="grid gap-3 lg:grid-cols-3">
        <JsonLinkedCheckbox checked={Boolean(config.required)} label="Согласование обязательно" onChange={(checked) => onChange({ ...config, required: checked })} />
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Источник согласующего</span>
          <Select
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, approver_source: { ...approverSource, type: event.currentTarget.value } })}
            value={String(approverSource.type ?? "service_owner")}
          >
            <option value="service_owner">Владелец сервиса</option>
            <option value="requester_manager">Руководитель заявителя</option>
            <option value="security_role">Роль ИБ</option>
            <option value="form_field">Поле формы</option>
          </Select>
        </label>
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Режим</span>
          <Select
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, approval_mode: event.currentTarget.value })}
            value={String(config.approval_mode ?? "any_one")}
          >
            <option value="any_one">Достаточно одного</option>
            <option value="all">Все согласующие</option>
            <option value="sequential">Последовательно</option>
          </Select>
        </label>
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Напомнить через</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) => onChange({ ...config, timeout: { ...timeout, reminder_after: event.currentTarget.value } })}
            placeholder="4h"
            value={String(timeout.reminder_after ?? "")}
          />
        </label>
        <JsonLinkedCheckbox
          checked={Boolean(config.require_comment_on_reject ?? true)}
          label="Комментарий при отказе"
          onChange={(checked) => onChange({ ...config, require_comment_on_reject: checked })}
        />
        <JsonLinkedCheckbox
          checked={Boolean(config.log_to_passport ?? true)}
          label="Писать в паспорт решения"
          onChange={(checked) => onChange({ ...config, log_to_passport: checked })}
        />
      </div>
    );
  }

  if (kind === "closure") {
    return <ClosurePolicyControls config={config} onChange={onChange} />;
  }

  if (kind === "diagnostic") {
    return <DiagnosticPolicyControls config={config} form={form} onChange={onChange} />;
  }

  if (kind === "visibility") {
    return <VisibilityPolicyControls config={config} onChange={onChange} />;
  }

  if (kind === "notification") {
    return <NotificationPolicyControls config={config} onChange={onChange} />;
  }

  if (kind === "reporting") {
    return <ReportingPolicyControls config={config} onChange={onChange} />;
  }

  const mapping =
    typeof config.public_status_mapping === "object" && config.public_status_mapping
      ? (config.public_status_mapping as Record<string, unknown>)
      : {};
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {[
        ["new", "Новая"],
        ["in_progress", "В работе"],
        ["waiting_user", "Нужен ответ"],
        ["resolved", "Решена"],
        ["closed", "Закрыта"],
      ].map(([status, label]) => (
        <label className="space-y-2 text-sm font-medium text-slate-800" key={status}>
          <span>{label}</span>
          <input
            className="field-base h-11 w-full px-4 text-sm"
            onChange={(event) =>
              onChange({ ...config, public_status_mapping: { ...mapping, [status]: event.currentTarget.value } })
            }
            value={String(mapping[status] ?? "")}
          />
        </label>
      ))}
      <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
        <span>Скрыть от заявителя</span>
        <input
          className="field-base h-11 w-full px-4 text-sm"
          onChange={(event) => onChange({ ...config, hide_from_requester: event.currentTarget.value.split(",").map((item) => item.trim()).filter(Boolean) })}
          value={Array.isArray(config.hide_from_requester) ? config.hide_from_requester.join(", ") : ""}
        />
      </label>
    </div>
  );
}

function PolicyRegistryEditors({
  data,
  disabled,
  onFeedback,
  selectedForm,
}: {
  data?: AdminHelpdeskModelPayload;
  disabled: boolean;
  onFeedback: (feedback: ActionFeedback) => void;
  selectedForm: DraftForm | null;
}) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<PolicyEditorKind>("routing");
  const [draft, setDraft] = useState<PolicyEditorDraft>(() => buildPolicyEditorDraft("routing", selectedForm));
  const [diffFromVersion, setDiffFromVersion] = useState("");
  const [diffToVersion, setDiffToVersion] = useState("");
  const [deactivateVersion, setDeactivateVersion] = useState("");
  const [rollbackVersion, setRollbackVersion] = useState("");
  const [diffResult, setDiffResult] = useState<AdminHelpdeskPolicyDiffResult | null>(null);

  useEffect(() => {
    setDraft(buildPolicyEditorDraft(kind, selectedForm));
  }, [kind, selectedForm?.key]);

  const config = useMemo(() => {
    try {
      return parseEditorJson(draft.jsonText);
    } catch {
      return {};
    }
  }, [draft.jsonText]);

  const publishMutation = useMutation({
    mutationFn: async () => {
      const configPayload = parseEditorJson(draft.jsonText);
      if (!draft.code.trim() || !draft.title.trim()) {
        throw new Error("Укажите код и название политики.");
      }
      return publishHelpdeskPolicy({
        kind: draft.kind,
        code: draft.code.trim(),
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        scope_level: draft.scope_level,
        scope_ref: draft.scope_ref.trim() || null,
        config: configPayload,
      });
    },
    onSuccess: async (result) => {
      onFeedback({ tone: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      onFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать политику.",
      });
    },
  });

  const allKindPolicies = useMemo(() => data?.policies[kind] ?? [], [data?.policies, kind]);
  const activeKindPolicies = allKindPolicies.filter((item) => item.is_active);
  const sameCodePolicies = useMemo(
    () =>
      allKindPolicies
        .filter((item) => item.code === draft.code.trim())
        .slice()
        .sort((left, right) => left.version.localeCompare(right.version, undefined, { numeric: true })),
    [allKindPolicies, draft.code]
  );
  const latestForCode = sameCodePolicies.find((item) => item.is_active) ?? sameCodePolicies[sameCodePolicies.length - 1] ?? null;
  const lifecycleActionsEnabled = Boolean(
    data?.capabilities.policy_diff_endpoint &&
      data.capabilities.policy_deactivate_endpoint &&
      data.capabilities.policy_rollback_endpoint
  );

  useEffect(() => {
    if (!sameCodePolicies.length) {
      setDiffFromVersion("");
      setDiffToVersion("");
      setDeactivateVersion("");
      setRollbackVersion("");
      setDiffResult(null);
      return;
    }
    const versions = sameCodePolicies.map((item) => item.version);
    const firstVersion = versions[0] ?? "";
    const latestVersion = latestForCode?.version ?? versions[versions.length - 1] ?? "";
    setDiffFromVersion((current) => (versions.includes(current) ? current : firstVersion));
    setDiffToVersion((current) => (versions.includes(current) ? current : latestVersion));
    setDeactivateVersion((current) => (versions.includes(current) ? current : latestVersion));
    setRollbackVersion((current) => (versions.includes(current) ? current : firstVersion));
    setDiffResult(null);
  }, [latestForCode?.version, sameCodePolicies]);

  const diffMutation = useMutation({
    mutationFn: async () => {
      if (!draft.code.trim() || !diffFromVersion || !diffToVersion) {
        throw new Error("Выберите код политики и две версии для сравнения.");
      }
      return diffHelpdeskPolicyVersions({
        kind: draft.kind,
        code: draft.code.trim(),
        from_version: diffFromVersion,
        to_version: diffToVersion,
      });
    },
    onSuccess: (result) => {
      setDiffResult(result);
      onFeedback({ tone: "success", text: "Версии политики сравнены." });
    },
    onError: (error) => {
      onFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось сравнить версии политики." });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async () => {
      if (!draft.code.trim() || !deactivateVersion) {
        throw new Error("Выберите версию политики для деактивации.");
      }
      return deactivateHelpdeskPolicyVersion({
        kind: draft.kind,
        code: draft.code.trim(),
        version: deactivateVersion,
      });
    },
    onSuccess: async (result) => {
      onFeedback({ tone: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      onFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось деактивировать версию политики." });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async () => {
      if (!draft.code.trim() || !rollbackVersion) {
        throw new Error("Выберите версию политики для отката.");
      }
      return rollbackHelpdeskPolicyVersion({
        kind: draft.kind,
        code: draft.code.trim(),
        target_version: rollbackVersion,
      });
    },
    onSuccess: async (result) => {
      onFeedback({ tone: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      onFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось откатить политику." });
    },
  });

  const updateConfig = (nextConfig: Record<string, unknown>) => {
    setDraft((current) => ({
      ...current,
      jsonText: prettyJson(nextConfig),
    }));
  };

  return (
    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Редакторы политик</p>
          <p className="mt-1 max-w-3xl text-xs leading-6 text-slate-600">
            Каждая публикация создаёт новую активную версию отдельной policy-сущности и audit-запись. Шаблон обращения может ссылаться на эти политики или наследовать их по scope.
          </p>
        </div>
        <Button
          disabled={disabled || publishMutation.isPending || !selectedForm}
          onClick={() => publishMutation.mutate()}
          size="sm"
          variant="primary"
        >
          {publishMutation.isPending ? "Публикуем..." : "Опубликовать политику"}
        </Button>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-3 xl:grid-cols-6">
        {POLICY_EDITOR_ITEMS.map((item) => (
          <button
            className={cn(
              "rounded-[0.9rem] border px-3 py-3 text-left transition",
              kind === item.kind ? "border-brand-300 bg-brand-50 text-brand-900" : "border-border bg-surface-subtle text-slate-600"
            )}
            key={item.kind}
            onClick={() => setKind(item.kind)}
            type="button"
          >
            <span className="block text-sm font-semibold">Политика: {item.label}</span>
            <span className="mt-1 block text-xs leading-5">{item.description}</span>
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-4">
            <label className="space-y-2 text-sm font-medium text-slate-800">
              <span>Код политики</span>
              <input
                className="field-base h-11 w-full px-4 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, code: event.currentTarget.value }))}
                value={draft.code}
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
              <span>Название</span>
              <input
                className="field-base h-11 w-full px-4 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, title: event.currentTarget.value }))}
                value={draft.title}
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-800">
              <span>Scope</span>
              <Select
                className="field-base h-11 w-full px-4 text-sm"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    scope_level: event.currentTarget.value as PolicyEditorDraft["scope_level"],
                  }))
                }
                value={draft.scope_level}
              >
                <option value="system">system defaults</option>
                <option value="ticket_type">ticket_type</option>
                <option value="category">category</option>
                <option value="request_template">request_template</option>
              </Select>
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-800">
              <span>Scope ref</span>
              <input
                className="field-base h-11 w-full px-4 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, scope_ref: event.currentTarget.value }))}
                value={draft.scope_ref}
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-3">
              <span>Описание</span>
              <input
                className="field-base h-11 w-full px-4 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, description: event.currentTarget.value }))}
                value={draft.description}
              />
            </label>
          </div>

          <PolicyKindControls config={config} form={selectedForm} kind={kind} onChange={updateConfig} />
        </div>

        <div className="space-y-3">
          <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-3 py-3">
            <p className="text-xs font-semibold text-slate-950">Текущая версия</p>
            <p className="mt-1 text-sm text-slate-600">
              {latestForCode ? `${latestForCode.version} опубликована` : "Для этого кода ещё нет активной версии"}
            </p>
          </div>
          <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-slate-950">Жизненный цикл версии</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  Сравнение показывает отличия JSON-конфига. Откат публикует новую активную версию из выбранной старой версии.
                </p>
              </div>
              <Badge tone={lifecycleActionsEnabled ? "success" : "neutral"}>
                {lifecycleActionsEnabled ? "доступно" : "нет endpoint"}
              </Badge>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <label className="space-y-1 text-xs font-medium text-slate-700">
                <span>Сравнить от</span>
                <Select
                  className="field-base h-9 w-full px-3 text-xs"
                  disabled={!sameCodePolicies.length}
                  onChange={(event) => setDiffFromVersion(event.currentTarget.value)}
                  value={diffFromVersion}
                >
                  {sameCodePolicies.map((policy) => (
                    <option key={`diff-from-${policy.version}`} value={policy.version}>
                      {policy.version}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="space-y-1 text-xs font-medium text-slate-700">
                <span>Сравнить с</span>
                <Select
                  className="field-base h-9 w-full px-3 text-xs"
                  disabled={!sameCodePolicies.length}
                  onChange={(event) => setDiffToVersion(event.currentTarget.value)}
                  value={diffToVersion}
                >
                  {sameCodePolicies.map((policy) => (
                    <option key={`diff-to-${policy.version}`} value={policy.version}>
                      {policy.version}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
            <Button
              className="mt-2 w-full"
              disabled={disabled || !lifecycleActionsEnabled || !diffFromVersion || !diffToVersion || diffMutation.isPending}
              onClick={() => diffMutation.mutate()}
              size="sm"
              variant="outline"
            >
              Сравнить версии
            </Button>

            {diffResult ? (
              <div className="mt-3 max-h-36 overflow-y-auto rounded-[0.75rem] border border-border bg-surface-subtle px-3 py-2">
                {diffResult.changes.length ? (
                  <div className="space-y-2 text-xs text-slate-700">
                    {diffResult.changes.map((change) => (
                      <div className="grid gap-1" key={change.path}>
                        <code className="font-mono text-[11px] text-slate-950">{change.path}</code>
                        <span>
                          {String(change.from ?? "пусто")} → {String(change.to ?? "пусто")}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">Отличий в конфиге нет.</p>
                )}
              </div>
            ) : null}

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <label className="space-y-1 text-xs font-medium text-slate-700">
                <span>Версия для деактивации</span>
                <Select
                  className="field-base h-9 w-full px-3 text-xs"
                  disabled={!sameCodePolicies.length}
                  onChange={(event) => setDeactivateVersion(event.currentTarget.value)}
                  value={deactivateVersion}
                >
                  {sameCodePolicies.map((policy) => (
                    <option key={`deactivate-${policy.version}`} value={policy.version}>
                      {policy.version}
                      {policy.is_active ? " · активна" : ""}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="space-y-1 text-xs font-medium text-slate-700">
                <span>Версия для отката</span>
                <Select
                  className="field-base h-9 w-full px-3 text-xs"
                  disabled={!sameCodePolicies.length}
                  onChange={(event) => setRollbackVersion(event.currentTarget.value)}
                  value={rollbackVersion}
                >
                  {sameCodePolicies.map((policy) => (
                    <option key={`rollback-${policy.version}`} value={policy.version}>
                      {policy.version}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <Button
                disabled={disabled || !lifecycleActionsEnabled || !deactivateVersion || deactivateMutation.isPending}
                onClick={() => deactivateMutation.mutate()}
                size="sm"
                variant="outline"
              >
                Деактивировать выбранную версию
              </Button>
              <Button
                disabled={disabled || !lifecycleActionsEnabled || !rollbackVersion || rollbackMutation.isPending}
                onClick={() => rollbackMutation.mutate()}
                size="sm"
                variant="secondary"
              >
                Откатить к выбранной версии
              </Button>
            </div>
          </div>
          <textarea
            className="field-base min-h-[300px] w-full resize-y px-4 py-3 font-mono text-xs leading-5"
            onChange={(event) => setDraft((current) => ({ ...current, jsonText: event.currentTarget.value }))}
            spellCheck={false}
            value={draft.jsonText}
          />
          <div className="max-h-36 overflow-y-auto rounded-[0.9rem] border border-border bg-white px-3 py-3">
            <p className="text-xs font-semibold text-slate-950">Активные политики этого типа</p>
            <div className="mt-2 space-y-1 text-xs text-slate-600">
              {activeKindPolicies.length ? (
                activeKindPolicies.slice(0, 8).map((policy: AdminHelpdeskPolicyItem) => (
                  <p className="truncate" key={`${policy.code}-${policy.version}`}>
                    {policy.code} · {policy.version} · {policy.scope_level}
                  </p>
                ))
              ) : (
                <p>Пока нет опубликованных политик.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SmartViewsRegistryEditor({
  data,
  disabled,
  onFeedback,
}: {
  data?: AdminHelpdeskModelPayload;
  disabled: boolean;
  onFeedback: (feedback: ActionFeedback) => void;
}) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("sla_risk_custom");
  const [title, setTitle] = useState("Риск по сроку ответа");
  const [description, setDescription] = useState("Сохранённый рабочий срез для контроля сроков.");
  const [filterText, setFilterText] = useState(() =>
    prettyJson({
      status_not_in: ["closed", "canceled"],
      due_before_hours: 2,
      due_fields: ["first_response_due_at", "resolution_due_at"],
    })
  );
  const [sortText, setSortText] = useState(() => JSON.stringify([{ field: "resolution_due_at", direction: "asc" }], null, 2));
  const [columnsText, setColumnsText] = useState("ticket_id,title,status,assignee_id,resolution_due_at");
  const smartFilter = parseJsonDraft(filterText);
  const smartSort = parseSortDraft(sortText);
  const firstSort = smartSort[0] ?? { field: "resolution_due_at", direction: "asc" };
  const updateFilter = (patch: Record<string, unknown>) => {
    setFilterText(prettyJson({ ...parseJsonDraft(filterText), ...patch }));
  };
  const updateSort = (patch: Record<string, unknown>) => {
    setSortText(JSON.stringify([{ ...firstSort, ...patch }], null, 2));
  };

  const mutation = useMutation({
    mutationFn: async () => {
      const filter = parseEditorJson(filterText);
      const sort = parseSortDraft(sortText);
      if (!Array.isArray(sort)) {
        throw new Error("Сортировка должна быть JSON-массивом.");
      }
      return publishHelpdeskSmartView({
        code: code.trim(),
        title: title.trim(),
        description: description.trim() || null,
        scope_level: "system",
        scope_ref: null,
        filter,
        sort: sort as Array<Record<string, unknown>>,
        columns: columnsText.split(",").map((item) => item.trim()).filter(Boolean),
      });
    },
    onSuccess: async (result) => {
      onFeedback({ tone: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      onFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось опубликовать smart view." });
    },
  });

  const activeViews = data?.smart_views.filter((item) => item.is_active) ?? [];

  return (
    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Редактор smart views</p>
          <p className="mt-1 max-w-3xl text-xs leading-6 text-slate-600">
            Сохранённые рабочие срезы не являются очередями ответственности. Это фильтры для контроля риска, ожиданий, согласований и диагностики.
          </p>
        </div>
        <Button disabled={disabled || mutation.isPending} onClick={() => mutation.mutate()} size="sm" variant="primary">
          {mutation.isPending ? "Публикуем..." : "Опубликовать smart view"}
        </Button>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-3 lg:grid-cols-3">
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Код</span>
            <input className="field-base h-11 w-full px-4 text-sm" onChange={(event) => setCode(event.currentTarget.value)} value={code} />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Название</span>
            <input className="field-base h-11 w-full px-4 text-sm" onChange={(event) => setTitle(event.currentTarget.value)} value={title} />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Колонки</span>
            <input className="field-base h-11 w-full px-4 text-sm" onChange={(event) => setColumnsText(event.currentTarget.value)} value={columnsText} />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-3">
            <span>Описание</span>
            <input className="field-base h-11 w-full px-4 text-sm" onChange={(event) => setDescription(event.currentTarget.value)} value={description} />
          </label>
          <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-3 py-3 lg:col-span-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Фильтр рабочего среза</p>
                <p className="mt-1 text-xs text-slate-600">
                  Основные условия собираются в `filter`, а JSON ниже остаётся как расширенный preview.
                </p>
              </div>
              <Badge tone="neutral">smart_view.filter</Badge>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Статусы исключить</span>
                <input
                  className="field-base h-11 w-full px-4 text-sm"
                  onChange={(event) => updateFilter({ status_not_in: csvToList(event.currentTarget.value) })}
                  value={csvList(smartFilter.status_not_in)}
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Срок до, часов</span>
                <input
                  className="field-base h-11 w-full px-4 text-sm"
                  min={0}
                  onChange={(event) => updateFilter({ due_before_hours: Number(event.currentTarget.value || 0) })}
                  type="number"
                  value={Number(smartFilter.due_before_hours ?? 0)}
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Поля сроков</span>
                <input
                  className="field-base h-11 w-full px-4 text-sm"
                  onChange={(event) => updateFilter({ due_fields: csvToList(event.currentTarget.value) })}
                  value={csvList(smartFilter.due_fields)}
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Сортировать по</span>
                <input
                  className="field-base h-11 w-full px-4 text-sm"
                  onChange={(event) => updateSort({ field: event.currentTarget.value })}
                  value={String(firstSort.field ?? "")}
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Направление сортировки</span>
                <Select
                  className="field-base h-11 w-full px-4 text-sm"
                  onChange={(event) => updateSort({ direction: event.currentTarget.value })}
                  value={String(firstSort.direction ?? "asc")}
                >
                  <option value="asc">asc</option>
                  <option value="desc">desc</option>
                </Select>
              </label>
            </div>
          </div>
          <label className="space-y-2 text-sm font-medium text-slate-800 lg:col-span-2">
            <span>Фильтр</span>
            <textarea className="field-base min-h-[180px] w-full resize-y px-4 py-3 font-mono text-xs leading-5" onChange={(event) => setFilterText(event.currentTarget.value)} value={filterText} />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Сортировка</span>
            <textarea className="field-base min-h-[180px] w-full resize-y px-4 py-3 font-mono text-xs leading-5" onChange={(event) => setSortText(event.currentTarget.value)} value={sortText} />
          </label>
        </div>
        <div className="max-h-72 overflow-y-auto rounded-[0.9rem] border border-border bg-surface-subtle px-3 py-3">
          <p className="text-xs font-semibold text-slate-950">Активные smart views</p>
          <div className="mt-2 space-y-1 text-xs text-slate-600">
            {activeViews.length ? (
              activeViews.slice(0, 10).map((view) => (
                <p className="truncate" key={`${view.code}-${view.version}`}>
                  {view.code} · {view.version} · {view.scope_level}
                </p>
              ))
            ) : (
              <p>Пока нет опубликованных smart views.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TemplateConstructorPanel({
  form,
  activeStep,
  onStepChange,
  onUpdateForm,
  onUpdatePolicyJson,
  onSelectField,
}: {
  form: DraftForm;
  activeStep: TemplateStepKey;
  onStepChange: (step: TemplateStepKey) => void;
  onUpdateForm: (updater: (form: DraftForm) => DraftForm) => void;
  onUpdatePolicyJson: (field: PolicyJsonField, value: string) => void;
  onSelectField: (fieldKey: string) => void;
}) {
  const policyCounts: Partial<Record<TemplateStepKey, number>> = {
    routing: policySize(form, "routing_policy_json"),
    approvals: policySize(form, "approval_policy_json"),
    diagnostics: policySize(form, "diagnostic_policy_json"),
    deadlines: policySize(form, "ola_policy_json") + (form.sla_policy_id.trim() ? 1 : 0),
    closure: policySize(form, "closure_policy_json"),
    visibility: policySize(form, "visibility_policy_json"),
    notifications: policySize(form, "notification_policy_json"),
    reporting: policySize(form, "reporting_policy_json"),
  };
  const requiredCount = form.fields.filter((field) => field.required).length;
  const activeStepMeta = TEMPLATE_STEPS.find((step) => step.key === activeStep) ?? TEMPLATE_STEPS[0];

  return (
    <div className="rounded-[1.1rem] border border-brand-100 bg-white px-4 py-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Визуальный конструктор шаблона обращения</p>
          <p className="mt-1 max-w-3xl text-xs text-slate-500">
            Собирает сценарий от пользовательского шаблона до закрытия: форма, процесс, приоритет, сроки ответа,
            роутинг, согласования, диагностика, видимость и уведомления сохраняются в текущую версию каталога.
          </p>
        </div>
        <Badge tone="info">{form.ticket_type}</Badge>
      </div>

      <div className="mt-5 overflow-x-auto pb-2">
        <div className="flex min-w-[980px] items-stretch gap-2">
          {TEMPLATE_STEPS.map((step, index) => {
            const Icon = step.icon;
            const count = policyCounts[step.key] ?? (step.key === "form" ? form.fields.length : 1);
            const isActive = activeStep === step.key;
            return (
              <div className="flex items-center gap-2" key={step.key}>
                <button
                  className={cn(
                    "min-h-[118px] w-[148px] rounded-[0.9rem] border px-3 py-3 text-left transition-colors",
                    isActive
                      ? "border-brand-300 bg-brand-50 text-brand-900"
                      : "border-border bg-surface-subtle text-slate-700 hover:border-brand-200 hover:bg-white"
                  )}
                  onClick={() => onStepChange(step.key)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Icon className="h-4 w-4 shrink-0" />
                    <Badge tone={policyBadgeTone(count)}>{count}</Badge>
                  </div>
                  <p className="mt-3 text-sm font-semibold">{step.shortTitle}</p>
                  <p className="mt-1 text-xs leading-4 text-current/70">{step.description}</p>
                </button>
                {index < TEMPLATE_STEPS.length - 1 ? <ArrowRight className="h-4 w-4 text-slate-300" /> : null}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-5 rounded-[1rem] border border-border bg-surface-subtle px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-950">{activeStepMeta.title}</p>
            <p className="mt-1 text-xs text-slate-500">{activeStepMeta.description}</p>
          </div>
          <Badge tone="neutral">{form.key}</Badge>
        </div>

        {activeStep === "template" ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Публично</p>
              <p className="mt-2 font-semibold text-slate-950">{form.title || "Без названия"}</p>
              <p className="mt-1 text-sm text-slate-500">{form.description || "Описание не задано"}</p>
            </div>
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Классификация</p>
              <p className="mt-2 font-semibold text-slate-950">{form.ticket_type}</p>
              <p className="mt-1 text-sm text-slate-500">request_kind: {form.request_kind}</p>
            </div>
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Версия</p>
              <p className="mt-2 font-semibold text-slate-950">Публикуется вместе с catalog pack</p>
              <p className="mt-1 text-sm text-slate-500">Старые тикеты продолжают хранить свой process context.</p>
            </div>
          </div>
        ) : null}

        {activeStep === "form" ? (
          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="grid gap-3 md:grid-cols-2">
              {form.fields.map((field) => (
                <button
                  className="rounded-[0.9rem] border border-border bg-white px-4 py-3 text-left hover:border-brand-200"
                  key={field.key}
                  onClick={() => onSelectField(field.key)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-slate-950">{field.label || field.key}</p>
                    <Badge tone={field.required ? "warning" : "neutral"}>{fieldTypeLabel(field.type)}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{field.key}</p>
                  {getFieldRoles(form, field.key).length ? (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {getFieldRoles(form, field.key).map((role) => (
                        <span className="rounded-pill bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-800" key={role}>
                          {role}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </button>
              ))}
            </div>
            <div className="rounded-[0.9rem] bg-white px-4 py-3 text-sm text-slate-600">
              <p className="font-semibold text-slate-950">Итог формы</p>
              <p className="mt-3">Всего полей: {form.fields.length}</p>
              <p className="mt-1">Обязательных: {requiredCount}</p>
              <p className="mt-1">С процессными ролями: {Object.keys(parseFieldRolesDraft(form.field_roles_json)).length}</p>
            </div>
          </div>
        ) : null}

        {activeStep === "workflow" ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Тип процесса</p>
              <p className="mt-2 font-semibold text-slate-950">{form.ticket_type}</p>
              <p className="mt-1 text-sm text-slate-500">Профиль workflow выбирается по ticket_type.</p>
            </div>
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Категория</p>
              <p className="mt-2 font-semibold text-slate-950">{form.category_id || "Не задана"}</p>
              <p className="mt-1 text-sm text-slate-500">service: {form.service_id || "не задан"}</p>
            </div>
            <div className="rounded-[0.9rem] bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Очередь по умолчанию</p>
              <p className="mt-2 font-semibold text-slate-950">{form.default_queue_id || "Fallback сервера"}</p>
            </div>
          </div>
        ) : null}

        {activeStep === "priority" ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {[
              ["priority_impact_field", "Поле влияния"],
              ["priority_urgency_field", "Поле срочности"],
              ["priority_importance_field", "Поле важности"],
            ].map(([key, label]) => (
              <label className="space-y-2 text-sm font-medium text-slate-800" key={key}>
                <span>{label}</span>
                <Select
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    onUpdateForm((current) => ({ ...current, [key]: value }));
                  }}
                  value={String(form[key as keyof DraftForm] ?? "")}
                >
                  <option value="">Не выбрано</option>
                  {form.fields.map((field) => (
                    <option key={field.key} value={field.key}>
                      {field.label || field.key}
                    </option>
                  ))}
                </Select>
              </label>
            ))}
          </div>
        ) : null}

        {activeStep === "deadlines" ? (
          <div className="mt-4 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
            <div className="space-y-4">
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Политика сроков ответа</span>
                <input
                  className="field-base h-11 w-full px-4 text-sm"
                  onChange={(event) => onUpdateForm((current) => ({ ...current, sla_policy_id: event.currentTarget.value }))}
                  placeholder="incident_sla"
                  value={form.sla_policy_id}
                />
              </label>
              <Button
                onClick={() => onUpdatePolicyJson("ola_policy_json", buildOlaPreset())}
                size="sm"
                variant="outline"
              >
                Вставить OLA
              </Button>
            </div>
            <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-950">Внутренние сроки очереди</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Цели принятия/обработки и действия при риске срока собираются без ручного JSON.
                  </p>
                </div>
                <Badge tone="neutral">OLA policy</Badge>
              </div>
              <div className="mt-4">
                <OlaPolicyControls
                  config={parseJsonDraft(form.ola_policy_json, parseJsonDraft(buildOlaPreset()))}
                  onChange={(config) => onUpdatePolicyJson("ola_policy_json", prettyJson(config))}
                />
              </div>
              <details className="mt-4 rounded-[0.8rem] border border-border bg-surface-subtle px-3 py-3">
                <summary className="cursor-pointer text-xs font-semibold text-slate-700">Расширенный JSON preview</summary>
                <textarea
                  className="field-base mt-3 min-h-[160px] w-full resize-y px-4 py-3 font-mono text-xs leading-5"
                  onChange={(event) => onUpdatePolicyJson("ola_policy_json", event.currentTarget.value)}
                  spellCheck={false}
                  value={form.ola_policy_json}
                />
              </details>
            </div>
          </div>
        ) : null}

        {activeStep === "routing" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Политика маршрутизации</p>
                <p className="mt-1 text-xs text-slate-500">
                  Очередь, первое правило и защита от автоматических перекидываний настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">routing policy</Badge>
            </div>
            <div className="mt-4">
              <RoutingPolicyControls
                config={parseJsonDraft(form.routing_policy_json, parseJsonDraft(buildRoutingPreset(form)))}
                form={form}
                onChange={(config) => onUpdatePolicyJson("routing_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "routing" ? (
          <PolicyJsonEditor
            description="Условия и действия: очередь, исполнитель, повышение приоритета, теги и suggested playbook."
            onChange={(value) => onUpdatePolicyJson("routing_policy_json", value)}
            presetLabel="Вставить роутинг"
            presetValue={buildRoutingPreset(form)}
            title="Политика маршрутизации"
            value={form.routing_policy_json}
          />
        ) : null}

        {activeStep === "approvals" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Политика согласования</p>
                <p className="mt-1 text-xs text-slate-500">
                  Источник согласующего, режим, напоминания, эскалация и правила отказа настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">approval policy</Badge>
            </div>
            <div className="mt-4">
              <ApprovalPolicyControls
                config={parseJsonDraft(form.approval_policy_json, parseJsonDraft(buildApprovalPreset()))}
                onChange={(config) => onUpdatePolicyJson("approval_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "approvals" ? (
          <PolicyJsonEditor
            description="Определяет, нужно ли согласование, кто согласует и какой статус ждать."
            onChange={(value) => onUpdatePolicyJson("approval_policy_json", value)}
            presetLabel="Вставить согласование"
            presetValue={buildApprovalPreset()}
            title="Политика согласования"
            value={form.approval_policy_json}
          />
        ) : null}

        {activeStep === "diagnostics" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Политика диагностики</p>
                <p className="mt-1 text-xs text-slate-500">
                  Playbook, автозапуск, consent, evidence и reroute-by-result настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">diagnostic policy</Badge>
            </div>
            <div className="mt-4">
              <DiagnosticPolicyControls
                config={parseJsonDraft(form.diagnostic_policy_json, parseJsonDraft(buildDiagnosticPreset(form)))}
                form={form}
                onChange={(config) => onUpdatePolicyJson("diagnostic_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "diagnostics" ? (
          <PolicyJsonEditor
            description="Playbook, consent, автозапуск и прикрепление результатов к паспорту решения."
            onChange={(value) => onUpdatePolicyJson("diagnostic_policy_json", value)}
            presetLabel="Вставить диагностику"
            presetValue={buildDiagnosticPreset(form)}
            title="Политика диагностики"
            value={form.diagnostic_policy_json}
          />
        ) : null}

        {activeStep === "closure" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Правила закрытия</p>
                <p className="mt-1 text-xs text-slate-500">
                  Код решения, итоги, evidence, подтверждение пользователя и автозакрытие настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">closure policy</Badge>
            </div>
            <div className="mt-4">
              <ClosurePolicyControls
                config={parseJsonDraft(form.closure_policy_json, parseJsonDraft(buildClosurePreset()))}
                onChange={(config) => onUpdatePolicyJson("closure_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "closure" ? (
          <PolicyJsonEditor
            description="Что нужно перед статусом Решена/Закрыта: код, публичный итог, evidence и подтверждение."
            onChange={(value) => onUpdatePolicyJson("closure_policy_json", value)}
            presetLabel="Вставить закрытие"
            presetValue={buildClosurePreset()}
            title="Правила закрытия"
            value={form.closure_policy_json}
          />
        ) : null}

        {activeStep === "visibility" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Политика видимости</p>
                <p className="mt-1 text-xs text-slate-500">
                  Публичные статусы, скрытые внутренние поля и requester-visible metadata настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">visibility policy</Badge>
            </div>
            <div className="mt-4">
              <VisibilityPolicyControls
                config={parseJsonDraft(form.visibility_policy_json, parseJsonDraft(buildVisibilityPreset()))}
                onChange={(config) => onUpdatePolicyJson("visibility_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "visibility" ? (
          <PolicyJsonEditor
            description="Публичные статусы, скрытые внутренние поля и requester/support-visible metadata."
            onChange={(value) => onUpdatePolicyJson("visibility_policy_json", value)}
            presetLabel="Вставить видимость"
            presetValue={buildVisibilityPreset()}
            title="Политика видимости"
            value={form.visibility_policy_json}
          />
        ) : null}

        {activeStep === "notifications" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Политика уведомлений</p>
                <p className="mt-1 text-xs text-slate-500">
                  Получатели событий тикета и каналы доставки настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">notification policy</Badge>
            </div>
            <div className="mt-4">
              <NotificationPolicyControls
                config={parseJsonDraft(form.notification_policy_json, parseJsonDraft(buildNotificationPreset()))}
                onChange={(config) => onUpdatePolicyJson("notification_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "notifications" ? (
          <PolicyJsonEditor
            description="Получатели in-app/email уведомлений по событиям тикета и срокам ответа."
            onChange={(value) => onUpdatePolicyJson("notification_policy_json", value)}
            presetLabel="Вставить уведомления"
            presetValue={buildNotificationPreset()}
            title="Политика уведомлений"
            value={form.notification_policy_json}
          />
        ) : null}

        {activeStep === "reporting" ? (
          <div className="mt-4 rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Паспорт решения и отчётность</p>
                <p className="mt-1 text-xs text-slate-500">
                  Разделы паспорта, evidence package, видимость экспорта, теги отчёта и knowledge hints настраиваются без ручного JSON.
                </p>
              </div>
              <Badge tone="neutral">reporting policy</Badge>
            </div>
            <div className="mt-4">
              <ReportingPolicyControls
                config={parseJsonDraft(form.reporting_policy_json, parseJsonDraft(buildReportingPreset()))}
                onChange={(config) => onUpdatePolicyJson("reporting_policy_json", prettyJson(config))}
              />
            </div>
          </div>
        ) : null}

        {activeStep === "reporting" ? (
          <PolicyJsonEditor
            description="Разделы паспорта решения, evidence package, export visibility, report tags и knowledge hints."
            onChange={(value) => onUpdatePolicyJson("reporting_policy_json", value)}
            presetLabel="Вставить паспорт"
            presetValue={buildReportingPreset()}
            title="Паспорт решения и отчётность"
            value={form.reporting_policy_json}
          />
        ) : null}
      </div>
    </div>
  );
}

function HelpdeskModelRegistryPanel({
  data,
  isLoading,
  isError,
  onPublish,
  publishDisabled,
  publishPending,
  selectedForm,
}: {
  data?: AdminHelpdeskModelPayload;
  isLoading: boolean;
  isError: boolean;
  onPublish: () => void;
  publishDisabled: boolean;
  publishPending: boolean;
  selectedForm: DraftForm | null;
}) {
  const selectedTemplate = data?.request_templates.find((item) => item.template_code === selectedForm?.key);
  const selectedFormSchema = data?.form_schemas.find((item) => item.schema_id === `${selectedForm?.key ?? ""}_form` && item.is_active);
  const activePolicies = data?.summary.active_policies_count ?? 0;
  const activeTemplates = data?.summary.active_request_templates_count ?? 0;
  const activeFormSchemas = data?.summary.active_form_schemas_count ?? 0;
  return (
    <div className="rounded-[1.1rem] border border-emerald-200 bg-emerald-50/70 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Реестр целевой модели</p>
          <p className="mt-1 max-w-3xl text-xs leading-6 text-slate-600">
            Отдельное versioned-хранилище для request templates, priority/routing/approval/closure/diagnostic/visibility/notification policies и smart views. Наследование применяется в порядке: system defaults &gt; ticket type &gt; category &gt; request template.
          </p>
        </div>
        <Button
          disabled={publishDisabled || publishPending || !selectedForm}
          onClick={onPublish}
          size="sm"
          variant="primary"
        >
          {publishPending ? "Публикуем..." : "Опубликовать в реестр"}
        </Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-5">
        <div className="rounded-[0.9rem] border border-emerald-100 bg-white px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Шаблоны</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{isLoading ? "..." : activeTemplates}</p>
        </div>
        <div className="rounded-[0.9rem] border border-emerald-100 bg-white px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Form schemas</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{isLoading ? "..." : activeFormSchemas}</p>
        </div>
        <div className="rounded-[0.9rem] border border-emerald-100 bg-white px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Политики</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{isLoading ? "..." : activePolicies}</p>
        </div>
        <div className="rounded-[0.9rem] border border-emerald-100 bg-white px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Smart views</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">
            {isLoading ? "..." : data?.summary.active_smart_views_count ?? 0}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-emerald-100 bg-white px-3 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">Текущий шаблон</p>
          <p className="mt-2 truncate text-sm font-semibold text-slate-950">
            {selectedTemplate ? `${selectedTemplate.version} / schema ${selectedFormSchema?.version ?? "n/a"}` : "ещё не в реестре"}
          </p>
        </div>
      </div>
      {isError ? (
        <p className="mt-3 text-xs font-medium text-rose-700">Не удалось загрузить реестр целевой модели.</p>
      ) : null}
    </div>
  );
}

export function FormsBuilderPanel({ permissions }: { permissions?: string[] } = {}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<DraftCatalog | null>(null);
  const [baselineFingerprint, setBaselineFingerprint] = useState<string>("null");
  const [loadedVersion, setLoadedVersion] = useState<string | null>(null);
  const [loadedSourceLabel, setLoadedSourceLabel] = useState("Текущий рабочий каталог");
  const [selectedFormKey, setSelectedFormKey] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [activeTemplateStep, setActiveTemplateStep] = useState<TemplateStepKey>("template");
  const [newFieldType, setNewFieldType] = useState<AdminFormsFieldType>("text");
  const [versionSearch, setVersionSearch] = useState("");
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);
  const [previewValues, setPreviewValues] = useState<PreviewFormValues>({});
  const [previewValidationIssues, setPreviewValidationIssues] = useState<PreviewValidationIssue[]>([]);
  const publishAccess = resolveOptionalAccess(permissions, "admin.forms.publish");

  const formsQuery = useQuery({
    queryKey: ["admin-forms-builder-current"],
    queryFn: fetchAdminFormsCatalog,
    retry: false,
  });

  const versionsQuery = useQuery({
    queryKey: ["admin-forms-builder-versions"],
    queryFn: fetchTicketFormsPackList,
    retry: false,
  });

  const helpdeskModelQuery = useQuery({
    queryKey: ["admin-helpdesk-model-registry"],
    queryFn: fetchHelpdeskModelRegistry,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: saveAdminFormsCatalog,
    onSuccess: async (result) => {
      const nextDraft = hydrateDraft({
        summary: result.summary,
        forms: result.forms,
      });
      setDraft(nextDraft);
      setBaselineFingerprint(buildDraftFingerprint(nextDraft));
      setLoadedVersion(result.summary.version);
      setLoadedSourceLabel(`Опубликованная версия ${result.summary.version}`);
      setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
      setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
      setActionFeedback({
        tone: "success",
        text: result.message,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать каталог форм.",
      });
    },
  });

  const preferredMutation = useMutation({
    mutationFn: setTicketFormsPackPreferred,
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text: `Активная версия каталога обновлена: ${result.preferred.version}.`,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось обновить preferred-версию каталога.",
      });
    },
  });

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!selectedForm) {
        throw new Error("Сначала выберите форму для preview.");
      }
      const issues = validatePreviewValues(selectedForm, previewValues);
      setPreviewValidationIssues(issues);
      if (issues.length) {
        throw new Error("Заполните обязательные поля preview.");
      }
      return previewAdminFormRoute({
        form: serializeDraftForm(selectedForm),
        form_payload: previewValues,
      });
    },
  });

  const registryPublishMutation = useMutation({
    mutationFn: async () => {
      if (!selectedForm) {
        throw new Error("Сначала выберите шаблон обращения.");
      }
      return publishHelpdeskTemplateFromForm({
        form: serializeDraftForm(selectedForm),
        publish_policies: true,
      });
    },
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text: result.message,
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать шаблон обращения в реестр.",
      });
    },
  });

  useEffect(() => {
    if (!formsQuery.data || draft) {
      return;
    }
    const nextDraft = hydrateDraft(formsQuery.data);
    setDraft(nextDraft);
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setLoadedVersion(formsQuery.data.summary.version);
    setLoadedSourceLabel(`Текущая активная версия ${formsQuery.data.summary.version}`);
    setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
    setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
  }, [draft, formsQuery.data]);

  useEffect(() => {
    if (!draft?.forms.length) {
      setSelectedFormKey(null);
      return;
    }

    if (!selectedFormKey || !draft.forms.some((form) => form.key === selectedFormKey)) {
      setSelectedFormKey(draft.forms[0].key);
    }
  }, [draft, selectedFormKey]);

  const selectedForm =
    draft?.forms.find((form) => form.key === selectedFormKey) ?? draft?.forms[0] ?? null;

  const workflowProfilesQuery = useQuery({
    queryKey: ["web-settings-workflow-profiles"],
    queryFn: fetchWebSettingsPayload,
    retry: false,
    staleTime: 60_000,
  });

  const workflowProfileOptions = useMemo(() => {
    const registryTicketTypes =
      workflowProfilesQuery.data?.ticket_settings.ticket_types.map((ticketType) => ({
        value: ticketType.code,
        label: `${ticketType.title} (${ticketType.code})`,
      })) ?? [];
    const configured =
      workflowProfilesQuery.data?.ticket_settings.workflow_profiles.map((profile) => ({
        value: profile.ticket_type,
        label: `${profile.label} (${profile.ticket_type})`,
      })) ?? [];
    const options = registryTicketTypes.length
      ? registryTicketTypes
      : configured.length
        ? configured
        : [...WORKFLOW_PROFILE_OPTIONS];
    if (selectedForm?.ticket_type && !options.some((option) => option.value === selectedForm.ticket_type)) {
      return [
        ...options,
        { value: selectedForm.ticket_type, label: selectedForm.ticket_type },
      ];
    }
    return options;
  }, [
    selectedForm?.ticket_type,
    workflowProfilesQuery.data?.ticket_settings.ticket_types,
    workflowProfilesQuery.data?.ticket_settings.workflow_profiles,
  ]);

  useEffect(() => {
    if (!selectedForm?.fields.length) {
      setSelectedFieldKey(null);
      return;
    }

    if (!selectedFieldKey || !selectedForm.fields.some((field) => field.key === selectedFieldKey)) {
      setSelectedFieldKey(selectedForm.fields[0].key);
    }
  }, [selectedFieldKey, selectedForm]);

  const selectedField =
    selectedForm?.fields.find((field) => field.key === selectedFieldKey) ??
    selectedForm?.fields[0] ??
    null;

  useEffect(() => {
    setPreviewValues((current) => buildPreviewValues(selectedForm, current));
    setPreviewValidationIssues([]);
    previewMutation.reset();
  }, [selectedForm]);

  const updatePreviewValue = (fieldKey: string, value: string | boolean) => {
    setPreviewValidationIssues([]);
    previewMutation.reset();
    setPreviewValues((current) => ({
      ...current,
      [fieldKey]: value,
    }));
  };

  const updateSelectedForm = (updater: (form: DraftForm) => DraftForm) => {
    if (!selectedForm) {
      return;
    }
    setDraft((current) => (current ? updateFormInCatalog(current, selectedForm.key, updater) : current));
  };

  const updateSelectedPolicyJson = (field: PolicyJsonField, value: string) => {
    updateSelectedForm((form) => ({
      ...form,
      [field]: value,
    }));
  };

  const hasUnsavedChanges = buildDraftFingerprint(draft) !== baselineFingerprint;
  const routePreview: AdminFormsRoutePreviewResult | undefined = previewMutation.data;
  const playbookTriggerReadiness = getPlaybookTriggerReadiness(selectedForm?.playbook_triggers[0]);
  const validationIssues = useMemo(() => validateDraftCatalog(draft), [draft]);
  const validationErrors = validationIssues.filter((issue) => issue.severity === "error");
  const hasBlockingValidationIssues = validationErrors.length > 0;
  const publishDisabled = !publishAccess.allowed;
  const dependencyFields =
    selectedForm && selectedField ? getDependencyFields(selectedForm, selectedField.key) : [];
  const dependencyField =
    dependencyFields.find((field) => field.key === selectedField?.visible_when.field) ?? null;
  const dependencyValueOptions = getDependencyValueOptions(dependencyField);
  const visibilityMode = selectedField ? getVisibilityMode(selectedField) : "always";

  const visibleVersions = useMemo(
    () => (versionsQuery.data?.packs ?? []).filter((item) => versionMatchesSearch(item, versionSearch)),
    [versionSearch, versionsQuery.data?.packs]
  );

  function ensureCanSwitch(): boolean {
    if (!hasUnsavedChanges) {
      return true;
    }
    return window.confirm(
      "В редакторе есть несохранённые изменения. Переключить версию и потерять локальный черновик?"
    );
  }

  async function loadCurrentCatalog() {
    if (!formsQuery.data || !ensureCanSwitch()) {
      return;
    }
    const nextDraft = hydrateDraft(formsQuery.data);
    setDraft(nextDraft);
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setLoadedVersion(formsQuery.data.summary.version);
    setLoadedSourceLabel(`Текущая активная версия ${formsQuery.data.summary.version}`);
    setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
    setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
    setActionFeedback(null);
  }

  async function loadVersion(version: string) {
    if (!ensureCanSwitch()) {
      return;
    }
    try {
      const payload = await queryClient.fetchQuery({
        queryKey: ["admin-forms-builder-version", version],
        queryFn: () => fetchTicketFormsPackVersion(version),
      });
      const nextDraft = hydrateDraftFromPack(payload.pack);
      setDraft(nextDraft);
      setBaselineFingerprint(buildDraftFingerprint(nextDraft));
      setLoadedVersion(version);
      setLoadedSourceLabel(`Черновик из версии ${version}`);
      setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
      setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
      setActionFeedback({
        tone: "success",
        text: `Версия ${version} загружена в редактор.`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось загрузить выбранную версию каталога.",
      });
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
            Forms Builder
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
            Конструктор форм заявок
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-500 md:text-base">
            Рабочий каталог intake-форм, version registry и публикация preferred-версии теперь
            живут в одном интерфейсе без legacy iframe.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Активная версия</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {formsQuery.data?.summary.version ?? "—"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Предпочтительная версия каталога, которая сейчас идёт в `/help`.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Версий в реестре</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {versionsQuery.data?.packs.length ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Можно открыть старую версию в редакторе или сделать её preferred.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Форм в каталоге</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {draft?.forms.length ?? formsQuery.data?.summary.forms_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Полей: {draft?.forms.reduce((sum, form) => sum + form.fields.length, 0) ?? formsQuery.data?.summary.fields_count ?? 0}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Черновик</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {hasUnsavedChanges ? "Есть" : "Синхронен"}
          </p>
          <p className="mt-2 text-sm text-slate-500">{loadedSourceLabel}</p>
        </div>
      </div>

      {actionFeedback ? (
        <div
          className={cn(
            "rounded-[1.1rem] border px-4 py-3 text-sm shadow-soft",
            actionFeedback.tone === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          )}
        >
          {actionFeedback.text}
        </div>
      ) : null}

      {!publishAccess.allowed ? (
        <div className="rounded-[1.1rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 shadow-soft">
          {publishAccess.reason}
        </div>
      ) : null}

      <HelpdeskModelRegistryPanel
        data={helpdeskModelQuery.data}
        isError={helpdeskModelQuery.isError}
        isLoading={helpdeskModelQuery.isLoading}
        onPublish={() => registryPublishMutation.mutate()}
        publishDisabled={publishDisabled || hasBlockingValidationIssues}
        publishPending={registryPublishMutation.isPending}
        selectedForm={selectedForm}
      />

      <PolicyRegistryEditors
        data={helpdeskModelQuery.data}
        disabled={publishDisabled || hasBlockingValidationIssues}
        onFeedback={setActionFeedback}
        selectedForm={selectedForm}
      />

      <SmartViewsRegistryEditor
        data={helpdeskModelQuery.data}
        disabled={publishDisabled || hasBlockingValidationIssues}
        onFeedback={setActionFeedback}
      />

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <Card className="xl:sticky xl:top-[9.5rem] xl:self-start">
          <CardHeader className="gap-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>Версии и публикация</CardTitle>
                <CardDescription>
                  Реальный реестр form-pack версий, preferred-переключение и быстрый возврат к текущей конфигурации.
                </CardDescription>
              </div>
              <Button
                leadingIcon={<RefreshCcw className="h-4 w-4" />}
                onClick={() => {
                  void Promise.all([formsQuery.refetch(), versionsQuery.refetch()]);
                }}
                size="sm"
                variant="outline"
              >
                Обновить
              </Button>
            </div>

            <div className="grid gap-2">
              <Button
                leadingIcon={<ClipboardList className="h-4 w-4" />}
                onClick={() => {
                  void loadCurrentCatalog();
                }}
                size="sm"
                variant="outline"
              >
                Загрузить текущую
              </Button>
              <Button
                disabled={publishDisabled || !draft || saveMutation.isPending || hasBlockingValidationIssues}
                leadingIcon={<Save className="h-4 w-4" />}
                onClick={() => {
                  if (!draft) {
                    return;
                  }
                  if (!publishAccess.allowed) {
                    setActionFeedback({ tone: "error", text: publishAccess.reason });
                    return;
                  }
                  setActionFeedback(null);
                  saveMutation.mutate(serializeDraft(draft));
                }}
              >
                {saveMutation.isPending ? "Публикуем..." : "Опубликовать новую версию"}
              </Button>
            </div>

            <SearchField
              onChange={(event) => setVersionSearch(event.target.value)}
              placeholder="Версия, автор, заметка"
              value={versionSearch}
            />
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
              <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Preferred</p>
              <p className="mt-2 text-lg font-semibold text-slate-950">
                {versionsQuery.data?.preferred?.version ?? formsQuery.data?.summary.version ?? "—"}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Последняя публикация: {formatDateTime(formsQuery.data?.summary.last_published_at)}
              </p>
            </div>

            <div className="max-h-[calc(100vh-24rem)] space-y-3 overflow-y-auto pr-1">
              {versionsQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Загружаем версии каталога...
                </div>
              ) : null}

              {versionsQuery.isError ? (
                <div className="rounded-[1.1rem] border border-dashed border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
                  {versionsQuery.error instanceof Error
                    ? versionsQuery.error.message
                    : "Не удалось загрузить версии каталога."}
                </div>
              ) : null}

              {visibleVersions.map((item) => {
                const isLoaded = loadedVersion === item.version;
                const isPreferred = versionsQuery.data?.preferred?.version === item.version;

                return (
                  <div
                    key={item.version}
                    className={cn(
                      "rounded-[1.15rem] border px-4 py-4",
                      isLoaded ? "border-brand-200 bg-brand-50" : "border-border bg-white"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-slate-950">{item.version}</p>
                          {isPreferred ? <Badge tone="success">preferred</Badge> : null}
                          {item.is_preferred ? <Badge tone="brand">current</Badge> : null}
                        </div>
                        <p className="mt-2 text-sm text-slate-600">{item.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.created_by ?? "builtin_default"} • {formatDateTime(item.created_at)}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">
                          Форм: {item.forms_count} • Полей: {item.fields_count} • Обязательных: {item.required_fields_count}
                        </p>
                      </div>
                      <FileClock className="h-4 w-4 shrink-0 text-slate-300" />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        leadingIcon={<FilePenLine className="h-4 w-4" />}
                        onClick={() => {
                          void loadVersion(item.version);
                        }}
                        size="sm"
                        variant="outline"
                      >
                        В редактор
                      </Button>
                      <Button
                        disabled={publishDisabled || isPreferred || preferredMutation.isPending}
                        leadingIcon={<Star className="h-4 w-4" />}
                        onClick={() => {
                          if (!publishAccess.allowed) {
                            setActionFeedback({ tone: "error", text: publishAccess.reason });
                            return;
                          }
                          preferredMutation.mutate(item.version);
                        }}
                        size="sm"
                      >
                        {`Сделать preferred для ${item.version}`}
                      </Button>
                    </div>
                  </div>
                );
              })}

              {!versionsQuery.isLoading && !versionsQuery.isError && visibleVersions.length === 0 ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Под текущий фильтр версии каталога не найдены.
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Редактор каталога</CardTitle>
                <CardDescription>
                  Все формы, поля и публикация работают на реальном pack-registry без legacy iframe.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={hasUnsavedChanges ? "warning" : "success"}>
                  {hasUnsavedChanges ? "Есть несохранённые изменения" : "Черновик синхронизирован"}
                </Badge>
                <Button
                  disabled={publishDisabled || !draft || saveMutation.isPending || hasBlockingValidationIssues}
                  leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                  onClick={() => {
                    if (!draft) {
                      return;
                    }
                    if (!publishAccess.allowed) {
                      setActionFeedback({ tone: "error", text: publishAccess.reason });
                      return;
                    }
                    setActionFeedback(null);
                    saveMutation.mutate(serializeDraft(draft));
                  }}
                  size="sm"
                >
                  {saveMutation.isPending ? "Публикуем..." : "Сохранить изменения"}
                </Button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            {!draft ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-10 text-center text-sm text-slate-500">
                Загружаем рабочий каталог форм...
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Название каталога</span>
                    <input
                      className="field-base h-11 w-full px-4 text-sm"
                      onChange={(event) => {
                        const value = event.currentTarget.value;
                        setActionFeedback(null);
                        setDraft((current) => (current ? { ...current, title: value } : current));
                      }}
                      value={draft.title}
                    />
                  </label>

                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Источник черновика</p>
                    <p className="mt-2 text-base font-semibold text-slate-950">{loadedSourceLabel}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      После публикации сервер выпустит новую версию и сделает её активной.
                    </p>
                  </div>
                </div>

                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Описание каталога</span>
                  <textarea
                    className="field-base min-h-[110px] w-full resize-y px-4 py-4 text-sm"
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setActionFeedback(null);
                      setDraft((current) => (current ? { ...current, description: value } : current));
                    }}
                    value={draft.description}
                  />
                </label>

                <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Формы каталога</p>
                        <p className="text-xs text-slate-500">Выберите форму или добавьте новую.</p>
                      </div>
                      <Button
                        leadingIcon={<Plus className="h-4 w-4" />}
                        onClick={() => {
                          setActionFeedback(null);
                          setDraft((current) => {
                            if (!current) {
                              return current;
                            }
                            const nextForm = createEmptyForm(nextFormIndex(current.forms));
                            setSelectedFormKey(nextForm.key);
                            setSelectedFieldKey(nextForm.fields[0]?.key ?? null);
                            return {
                              ...current,
                              forms: [...current.forms, nextForm],
                            };
                          });
                        }}
                        size="sm"
                      >
                        Новая форма
                      </Button>
                    </div>

                    <div className="max-h-[calc(100vh-27rem)] space-y-3 overflow-y-auto pr-1">
                      {draft.forms.map((form) => (
                        <button
                          key={form.key}
                          className={cn(
                            "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                            selectedForm?.key === form.key
                              ? "border-brand-200 bg-brand-50"
                              : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                          )}
                          onClick={() => {
                            setSelectedFormKey(form.key);
                            setSelectedFieldKey(form.fields[0]?.key ?? null);
                            setActionFeedback(null);
                          }}
                          type="button"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-semibold text-slate-950">{form.title || form.key}</p>
                              <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
                                {form.request_kind}
                              </p>
                            </div>
                            <Badge tone="neutral">{form.fields.length} полей</Badge>
                          </div>
                          <p className="mt-3 text-sm text-slate-500 line-clamp-2">
                            {form.description || "Описание формы пока не заполнено."}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-5">
                    {selectedForm ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">Параметры формы</p>
                            <p className="text-xs text-slate-500">
                              Ключ, request_kind и состав полей сохраняются в следующую версию каталога.
                            </p>
                          </div>
                          <Button
                            disabled={draft.forms.length <= 1}
                            leadingIcon={<Trash2 className="h-4 w-4" />}
                            onClick={() => {
                              setActionFeedback(null);
                              setDraft((current) => {
                                if (!current) {
                                  return current;
                                }
                                const nextForms = current.forms.filter((form) => form.key !== selectedForm.key);
                                setSelectedFormKey(nextForms[0]?.key ?? null);
                                setSelectedFieldKey(nextForms[0]?.fields[0]?.key ?? null);
                                return {
                                  ...current,
                                  forms: nextForms,
                                };
                              });
                            }}
                            size="sm"
                            variant="outline"
                          >
                            Удалить форму
                          </Button>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Название формы</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        title: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.title}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Ключ формы</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) => {
                                  if (!current) {
                                    return current;
                                  }
                                  return {
                                    ...current,
                                    forms: current.forms.map((form) =>
                                      form.key === selectedForm.key
                                        ? {
                                            ...form,
                                            key: value,
                                            request_kind:
                                              form.request_kind === selectedForm.key ? value : form.request_kind,
                                          }
                                        : form
                                    ),
                                  };
                                });
                                setSelectedFormKey(value);
                              }}
                              value={selectedForm.key}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>request_kind</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        request_kind: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.request_kind}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Описание формы</span>
                            <textarea
                              className="field-base min-h-[88px] w-full resize-y px-4 py-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        description: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.description}
                            />
                          </label>
                        </div>

                        <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Процессный контекст</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Шаблон обращения задаёт тип процесса, классификацию, сроки ответа и поля, из которых считается приоритет.
                              </p>
                            </div>
                            <Badge tone="info">{selectedForm.ticket_type}</Badge>
                          </div>
                          <div className="mt-4 grid gap-4 md:grid-cols-3">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Тип процесса</span>
                              <Select
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                          ...form,
                                          ticket_type: value,
                                        }))
                                      : current
                                  );
                                }}
                                value={selectedForm.ticket_type}
                              >
                                {workflowProfileOptions.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </Select>
                            </label>
                            {[
                              ["category_id", "category_id"],
                              ["service_id", "service_id"],
                              ["subcategory_id", "subcategory_id"],
                              ["default_queue_id", "default_queue_id"],
                              ["sla_policy_id", "Политика сроков ответа"],
                              ["suggested_playbook_id", "Предлагаемый плейбук"],
                            ].map(([key, label]) => (
                              <label className="space-y-2 text-sm font-medium text-slate-800" key={key}>
                                <span>{label}</span>
                                <input
                                  className="field-base h-11 w-full px-4 text-sm"
                                  onChange={(event) => {
                                    const value = event.currentTarget.value;
                                    setDraft((current) =>
                                      current
                                        ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                            ...form,
                                            [key]: value,
                                          }))
                                        : current
                                    );
                                  }}
                                  value={String(selectedForm[key as keyof DraftForm] ?? "")}
                                />
                              </label>
                            ))}
                          </div>
                          <div className="mt-4 grid gap-4 md:grid-cols-3">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Поле влияния</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                          ...form,
                                          priority_impact_field: value,
                                        }))
                                      : current
                                  );
                                }}
                                placeholder="affected_scope"
                                value={selectedForm.priority_impact_field}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Поле срочности</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                          ...form,
                                          priority_urgency_field: value,
                                        }))
                                      : current
                                  );
                                }}
                                placeholder="work_continuity"
                                value={selectedForm.priority_urgency_field}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Поле важности</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                          ...form,
                                          priority_importance_field: value,
                                        }))
                                      : current
                                  );
                                }}
                                placeholder="business_deadline"
                                value={selectedForm.priority_importance_field}
                              />
                            </label>
                          </div>
                          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[0.9rem] border border-border bg-surface-subtle px-4 py-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Вопросы для расчёта приоритета</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Добавляет поля влияния, срочности, важности и модификаторы в шаблон обращения.
                              </p>
                            </div>
                            <Button
                              onClick={() => {
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, applyPriorityQuestionTemplate)
                                    : current
                                );
                              }}
                              size="sm"
                              variant="outline"
                            >
                              Добавить вопросы
                            </Button>
                          </div>
                        </div>

                        <TemplateConstructorPanel
                          activeStep={activeTemplateStep}
                          form={selectedForm}
                          onSelectField={(fieldKey) => {
                            setSelectedFieldKey(fieldKey);
                          }}
                          onStepChange={setActiveTemplateStep}
                          onUpdateForm={updateSelectedForm}
                          onUpdatePolicyJson={updateSelectedPolicyJson}
                        />

                        <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-4">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Плейбук при создании тикета</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Форма может запускать диагностический сценарий и прикладывать пакет фактов к тикету.
                              </p>
                            </div>
                            <div className="flex flex-col items-start gap-2 sm:items-end">
                              <Badge tone={playbookTriggerReadiness.tone}>{playbookTriggerReadiness.label}</Badge>
                              <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
                                <input
                                  checked={Boolean(selectedForm.playbook_triggers[0]?.enabled)}
                                  onChange={(event) => {
                                    const checked = event.currentTarget.checked;
                                    setDraft((current) =>
                                      current
                                        ? updateFormInCatalog(current, selectedForm.key, (form) => {
                                            const currentTrigger = form.playbook_triggers[0] ?? {
                                              event: "ticket_created" as const,
                                              playbook_key: "",
                                              module_kind: "diagnostic" as const,
                                              enabled: false,
                                            };
                                            return {
                                              ...form,
                                              playbook_triggers: [
                                                {
                                                  ...currentTrigger,
                                                  enabled: checked,
                                                },
                                              ],
                                            };
                                          })
                                        : current
                                    );
                                  }}
                                  type="checkbox"
                                />
                                Включить
                              </label>
                            </div>
                          </div>
                          <div className="mt-4 rounded-[0.9rem] border border-border bg-white px-3 py-3">
                            <p className="text-sm font-medium text-slate-900">{playbookTriggerReadiness.detail}</p>
                            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                              <span className="rounded-pill bg-slate-100 px-3 py-1">ticket_created</span>
                              <span className="rounded-pill bg-slate-100 px-3 py-1">diagnostic</span>
                              {selectedForm.playbook_triggers[0]?.playbook_key ? (
                                <span className="rounded-pill bg-brand-50 px-3 py-1 text-brand-800">
                                  {selectedForm.playbook_triggers[0]?.playbook_key}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <div className="mt-4 rounded-[0.9rem] border border-border bg-white px-3 py-3">
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Цепочка запуска</p>
                            <div className="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Форма</p>
                                <p className="mt-1 text-xs text-slate-500">{selectedForm.title || selectedForm.key}</p>
                              </div>
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Роутинг</p>
                                <p className="mt-1 text-xs text-slate-500">request_kind: {selectedForm.request_kind || "не указан"}</p>
                              </div>
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Плейбук</p>
                                <p className="mt-1 text-xs text-slate-500">
                                  {selectedForm.playbook_triggers[0]?.playbook_key || "запуск не настроен"}
                                </p>
                              </div>
                            </div>
                          </div>
                          <div className="mt-4 grid gap-4 md:grid-cols-2">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Ключ плейбука</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => {
                                          const currentTrigger = form.playbook_triggers[0] ?? {
                                            event: "ticket_created" as const,
                                            playbook_key: "",
                                            module_kind: "diagnostic" as const,
                                            enabled: true,
                                          };
                                          return {
                                            ...form,
                                            playbook_triggers: [
                                              {
                                                ...currentTrigger,
                                                event: "ticket_created",
                                                module_kind: "diagnostic",
                                                playbook_key: value,
                                              },
                                            ],
                                          };
                                        })
                                      : current
                                  );
                                }}
                                placeholder="site_not_opening"
                                value={selectedForm.playbook_triggers[0]?.playbook_key ?? ""}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Класс сценария</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                disabled
                                value="diagnostic"
                              />
                            </label>
                          </div>
                        </div>

                        <div className="space-y-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Поля формы</p>
                              <p className="text-xs text-slate-500">
                                Редактор полей полностью живой: типы, options и visible_when уйдут в новую версию.
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Select
                                className="min-w-[160px]"
                                onChange={(event) => setNewFieldType(event.target.value as AdminFormsFieldType)}
                                value={newFieldType}
                              >
                                {formsQuery.data?.capabilities.field_type_options.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </Select>
                              <Button
                                leadingIcon={<Plus className="h-4 w-4" />}
                                onClick={() => {
                                  setDraft((current) => {
                                    if (!current) {
                                      return current;
                                    }
                                    const field = createEmptyField(
                                      newFieldType,
                                      nextFieldIndex(selectedForm.fields)
                                    );
                                    setSelectedFieldKey(field.key);
                                    return updateFormInCatalog(current, selectedForm.key, (form) => ({
                                      ...form,
                                      fields: [...form.fields, field],
                                    }));
                                  });
                                }}
                                size="sm"
                              >
                                Поле
                              </Button>
                            </div>
                          </div>

                          <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
                            <div className="max-h-[calc(100vh-32rem)] space-y-3 overflow-y-auto pr-1">
                              {selectedForm.fields.map((field) => (
                                <button
                                  key={field.key}
                                  className={cn(
                                    "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                                    selectedField?.key === field.key
                                      ? "border-brand-200 bg-brand-50"
                                      : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                                  )}
                                  onClick={() => setSelectedFieldKey(field.key)}
                                  type="button"
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <p className="font-medium text-slate-900">{field.label || field.key}</p>
                                      <p className="mt-1 text-xs text-slate-500">{field.key}</p>
                                    </div>
                                    <Badge tone="neutral">{fieldTypeLabel(field.type)}</Badge>
                                  </div>
                                  <p className="mt-3 text-xs text-slate-500">
                                    {field.required ? "Обязательное поле" : "Необязательное поле"}
                                  </p>
                                </button>
                              ))}
                            </div>

                            <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                              {selectedField ? (
                                <div className="space-y-4">
                                  <div className="flex items-center justify-between gap-3">
                                    <div>
                                      <p className="font-semibold text-slate-900">Параметры поля</p>
                                      <p className="text-xs text-slate-500">{selectedField.key}</p>
                                    </div>
                                    <Button
                                      disabled={selectedForm.fields.length <= 1}
                                      leadingIcon={<Trash2 className="h-4 w-4" />}
                                     onClick={() => {
                                        setDraft((current) => {
                                          if (!current) {
                                            return current;
                                          }
                                          const nextForm = removeFieldFromForm(selectedForm, selectedField.key);
                                          const remainingFields = nextForm.fields;
                                          setSelectedFieldKey(remainingFields[0]?.key ?? null);
                                          return updateFormInCatalog(current, selectedForm.key, () => nextForm);
                                        });
                                      }}
                                      size="sm"
                                      variant="outline"
                                    >
                                      Удалить
                                    </Button>
                                  </div>

                                  <div className="grid gap-4 md:grid-cols-2">
                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Название поля</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    label: value,
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.label}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Ключ поля</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFormInCatalog(current, selectedForm.key, (form) =>
                                                  renameFieldInForm(form, selectedField.key, value)
                                                )
                                              : current
                                          );
                                          setSelectedFieldKey(value);
                                        }}
                                        value={selectedField.key}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Тип поля</span>
                                      <Select
                                        onChange={(event) => {
                                          const value = event.target.value as AdminFormsFieldType;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    type: value,
                                                    options:
                                                      value === "select" || value === "radio"
                                                        ? field.options.length
                                                          ? field.options
                                                          : [
                                                              { value: "option_1", label: "Вариант 1" },
                                                              { value: "option_2", label: "Вариант 2" },
                                                            ]
                                                        : [],
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.type}
                                      >
                                        {formsQuery.data?.capabilities.field_type_options.map((option) => (
                                          <option key={option.value} value={option.value}>
                                            {option.label}
                                          </option>
                                        ))}
                                      </Select>
                                    </label>

                                    <label className="flex h-11 items-center gap-3 rounded-pill border border-border bg-white px-4">
                                      <input
                                        checked={selectedField.required}
                                        onChange={(event) => {
                                          const checked = event.currentTarget.checked;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    required: checked,
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        type="checkbox"
                                      />
                                      <span className="text-sm font-medium text-slate-700">Поле обязательное</span>
                                    </label>
                                  </div>

                                  <div className="space-y-3 rounded-[1rem] border border-border bg-white px-4 py-4">
                                    <div>
                                      <p className="text-sm font-semibold text-slate-900">Роли поля в процессе</p>
                                      <p className="mt-1 text-xs text-slate-500">
                                        Роли определяют, участвует ли поле в приоритете, маршрутизации, сроках ответа, согласовании, диагностике или закрытии.
                                      </p>
                                    </div>
                                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                                      {FIELD_ROLE_OPTIONS.map((role) => {
                                        const roles = getFieldRoles(selectedForm, selectedField.key);
                                        return (
                                          <label
                                            className="flex items-center gap-3 rounded-[0.9rem] bg-surface-subtle px-3 py-2 text-sm"
                                            key={role.value}
                                          >
                                            <input
                                              checked={roles.includes(role.value)}
                                              onChange={(event) => {
                                                const checked = event.currentTarget.checked;
                                                setDraft((current) =>
                                                  current
                                                    ? updateFormInCatalog(current, selectedForm.key, (form) =>
                                                        updateFieldRoles(form, selectedField.key, role.value, checked)
                                                      )
                                                    : current
                                                );
                                              }}
                                              type="checkbox"
                                            />
                                            <span>{role.label}</span>
                                          </label>
                                        );
                                      })}
                                    </div>
                                  </div>

                                  <label className="space-y-2 text-sm font-medium text-slate-800">
                                    <span>Placeholder</span>
                                    <input
                                      className="field-base h-11 w-full px-4 text-sm"
                                      onChange={(event) => {
                                        const value = event.currentTarget.value;
                                        setDraft((current) =>
                                          current
                                            ? updateFieldInCatalog(
                                                current,
                                                selectedForm.key,
                                                selectedField.key,
                                                (field) => ({
                                                  ...field,
                                                  placeholder: value,
                                                })
                                              )
                                            : current
                                        );
                                      }}
                                      value={selectedField.placeholder}
                                    />
                                  </label>

                                  <label className="space-y-2 text-sm font-medium text-slate-800">
                                    <span>Help text</span>
                                    <textarea
                                      className="field-base min-h-[90px] w-full resize-y px-4 py-4 text-sm"
                                      onChange={(event) => {
                                        const value = event.currentTarget.value;
                                        setDraft((current) =>
                                          current
                                            ? updateFieldInCatalog(
                                                current,
                                                selectedForm.key,
                                                selectedField.key,
                                                (field) => ({
                                                  ...field,
                                                  help_text: value,
                                                })
                                              )
                                            : current
                                        );
                                      }}
                                      value={selectedField.help_text}
                                    />
                                  </label>

                                  {fieldTypeRequiresOptions(selectedField) ? (
                                    <div className="space-y-3 rounded-[1rem] border border-border bg-white px-4 py-4">
                                      <div className="flex items-center justify-between gap-3">
                                        <div>
                                          <p className="text-sm font-semibold text-slate-900">Варианты ответа</p>
                                          <p className="mt-1 text-xs text-slate-500">
                                            Значения уходят в payload, названия показываются пользователю.
                                          </p>
                                        </div>
                                        <Button
                                          onClick={() => {
                                            setDraft((current) =>
                                              current
                                                ? updateFieldInCatalog(
                                                    current,
                                                    selectedForm.key,
                                                    selectedField.key,
                                                    addFieldOption
                                                  )
                                                : current
                                            );
                                          }}
                                          size="sm"
                                          variant="outline"
                                        >
                                          Добавить вариант
                                        </Button>
                                      </div>
                                      <div className="space-y-2">
                                        {selectedField.options.map((option, optionIndex) => (
                                          <div
                                            className="grid gap-2 rounded-[0.9rem] bg-surface-subtle px-3 py-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                                            key={`${option.value}-${optionIndex}`}
                                          >
                                            <label className="space-y-1 text-xs font-semibold text-slate-500">
                                              <span>Значение</span>
                                              <input
                                                aria-label={`Значение варианта ${optionIndex + 1}`}
                                                className="field-base h-10 w-full px-3 text-sm"
                                                onChange={(event) => {
                                                  const value = event.currentTarget.value;
                                                  setDraft((current) =>
                                                    current
                                                      ? updateFieldInCatalog(
                                                          current,
                                                          selectedForm.key,
                                                          selectedField.key,
                                                          (field) => updateFieldOption(field, optionIndex, { value })
                                                        )
                                                      : current
                                                  );
                                                }}
                                                value={option.value}
                                              />
                                            </label>
                                            <label className="space-y-1 text-xs font-semibold text-slate-500">
                                              <span>Название</span>
                                              <input
                                                aria-label={`Название варианта ${optionIndex + 1}`}
                                                className="field-base h-10 w-full px-3 text-sm"
                                                onChange={(event) => {
                                                  const label = event.currentTarget.value;
                                                  setDraft((current) =>
                                                    current
                                                      ? updateFieldInCatalog(
                                                          current,
                                                          selectedForm.key,
                                                          selectedField.key,
                                                          (field) => updateFieldOption(field, optionIndex, { label })
                                                        )
                                                      : current
                                                  );
                                                }}
                                                value={option.label}
                                              />
                                            </label>
                                            <Button
                                              disabled={selectedField.options.length <= 1}
                                              onClick={() => {
                                                setDraft((current) =>
                                                  current
                                                    ? updateFieldInCatalog(
                                                        current,
                                                        selectedForm.key,
                                                        selectedField.key,
                                                        (field) => removeFieldOption(field, optionIndex)
                                                      )
                                                    : current
                                                );
                                              }}
                                              size="sm"
                                              variant="ghost"
                                            >
                                              Удалить
                                            </Button>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : null}

                                  <div className="space-y-4 rounded-[1rem] border border-border bg-white px-4 py-4">
                                    <div>
                                      <p className="text-sm font-semibold text-slate-900">Условие показа</p>
                                      <p className="mt-1 text-xs text-slate-500">
                                        Ограничьте поле ответом в другом поле формы. Пустое условие значит, что поле показывается всегда.
                                      </p>
                                    </div>
                                    <div className="grid gap-4 md:grid-cols-3">
                                      <label className="space-y-2 text-sm font-medium text-slate-800">
                                        <span>Зависит от поля</span>
                                        <Select
                                          aria-label="Поле условия"
                                          onChange={(event) => {
                                            const value = event.target.value;
                                            setDraft((current) =>
                                              current
                                                ? updateFieldInCatalog(
                                                    current,
                                                    selectedForm.key,
                                                    selectedField.key,
                                                    (field) => ({
                                                      ...field,
                                                      visible_when: {
                                                        field: value,
                                                        equals: value ? "" : "",
                                                        values: [],
                                                      },
                                                    })
                                                  )
                                                : current
                                            );
                                          }}
                                          value={selectedField.visible_when.field}
                                        >
                                          <option value="">Показывать всегда</option>
                                          {dependencyFields.map((field) => (
                                            <option key={field.key} value={field.key}>
                                              {field.label || field.key}
                                            </option>
                                          ))}
                                        </Select>
                                      </label>

                                      <label className="space-y-2 text-sm font-medium text-slate-800">
                                        <span>Правило</span>
                                        <Select
                                          aria-label="Условие показа"
                                          disabled={!selectedField.visible_when.field}
                                          onChange={(event) => {
                                            const mode = event.target.value;
                                            setDraft((current) =>
                                              current
                                                ? updateFieldInCatalog(
                                                    current,
                                                    selectedForm.key,
                                                    selectedField.key,
                                                    (field) => {
                                                      if (mode === "always") {
                                                        return clearVisibleWhenConfig(field);
                                                      }
                                                      const firstValue =
                                                        field.visible_when.equals ||
                                                        field.visible_when.values[0] ||
                                                        dependencyValueOptions[0]?.value ||
                                                        "";
                                                      return {
                                                        ...field,
                                                        visible_when: {
                                                          field: field.visible_when.field,
                                                          equals: mode === "equals" ? firstValue : "",
                                                          values: mode === "values" && firstValue ? [firstValue] : [],
                                                        },
                                                      };
                                                    }
                                                  )
                                                : current
                                            );
                                          }}
                                          value={visibilityMode}
                                        >
                                          <option value="always">Показывать всегда</option>
                                          <option value="equals">Равно одному значению</option>
                                          <option value="values">Одно из значений</option>
                                        </Select>
                                      </label>

                                      {visibilityMode === "equals" ? (
                                        <label className="space-y-2 text-sm font-medium text-slate-800">
                                          <span>Значение</span>
                                          {dependencyValueOptions.length ? (
                                            <Select
                                              aria-label="Значение условия"
                                              onChange={(event) => {
                                                const value = event.target.value;
                                                setDraft((current) =>
                                                  current
                                                    ? updateFieldInCatalog(
                                                        current,
                                                        selectedForm.key,
                                                        selectedField.key,
                                                        (field) => ({
                                                          ...field,
                                                          visible_when: {
                                                            ...field.visible_when,
                                                            equals: value,
                                                            values: [],
                                                          },
                                                        })
                                                      )
                                                    : current
                                                );
                                              }}
                                              value={selectedField.visible_when.equals}
                                            >
                                              <option value="">Не выбрано</option>
                                              {dependencyValueOptions.map((option) => (
                                                <option key={option.value} value={option.value}>
                                                  {option.label}
                                                </option>
                                              ))}
                                            </Select>
                                          ) : (
                                            <input
                                              aria-label="Значение условия"
                                              className="field-base h-11 w-full px-4 text-sm"
                                              onChange={(event) => {
                                                const value = event.currentTarget.value;
                                                setDraft((current) =>
                                                  current
                                                    ? updateFieldInCatalog(
                                                        current,
                                                        selectedForm.key,
                                                        selectedField.key,
                                                        (field) => ({
                                                          ...field,
                                                          visible_when: {
                                                            ...field.visible_when,
                                                            equals: value,
                                                            values: [],
                                                          },
                                                        })
                                                      )
                                                    : current
                                                );
                                              }}
                                              value={selectedField.visible_when.equals}
                                            />
                                          )}
                                        </label>
                                      ) : null}
                                    </div>
                                    {visibilityMode === "values" ? (
                                      <div className="grid gap-2 sm:grid-cols-2">
                                        {dependencyValueOptions.length ? (
                                          dependencyValueOptions.map((option) => (
                                            <label
                                              className="flex items-center gap-3 rounded-[0.9rem] bg-surface-subtle px-3 py-2 text-sm"
                                              key={option.value}
                                            >
                                              <input
                                                checked={selectedField.visible_when.values.includes(option.value)}
                                                onChange={(event) => {
                                                  const checked = event.currentTarget.checked;
                                                  setDraft((current) =>
                                                    current
                                                      ? updateFieldInCatalog(
                                                          current,
                                                          selectedForm.key,
                                                          selectedField.key,
                                                          (field) => {
                                                            const values = new Set(field.visible_when.values);
                                                            if (checked) {
                                                              values.add(option.value);
                                                            } else {
                                                              values.delete(option.value);
                                                            }
                                                            return {
                                                              ...field,
                                                              visible_when: {
                                                                ...field.visible_when,
                                                                equals: "",
                                                                values: Array.from(values),
                                                              },
                                                            };
                                                          }
                                                        )
                                                      : current
                                                  );
                                                }}
                                                type="checkbox"
                                              />
                                              <span>{option.label}</span>
                                            </label>
                                          ))
                                        ) : (
                                          <p className="text-sm text-slate-500">
                                            Для нескольких значений выберите зависимое поле со списком вариантов.
                                          </p>
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                </div>
                              ) : (
                                <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-8 text-sm text-slate-500">
                                  Выберите поле слева, чтобы настроить его параметры.
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                        Выберите форму слева или создайте новую форму.
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="xl:sticky xl:top-[9.5rem] xl:self-start">
          <CardHeader>
            <CardTitle>Контекст формы</CardTitle>
            <CardDescription>
              Быстрый контроль над текущим редактором: выбранная форма, поле и состояние публикации.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
              <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Выбрано сейчас</p>
              <p className="mt-2 text-lg font-semibold text-slate-950">
                {selectedForm?.title ?? "Форма не выбрана"}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                {selectedField ? `Поле: ${selectedField.label}` : "Выберите поле для редактирования справа."}
              </p>
            </div>

            <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">Проверка публикации</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {validationIssues.length
                      ? `${validationErrors.length} блокирующих, ${validationIssues.length - validationErrors.length} предупреждений`
                      : "Каталог можно публиковать."}
                  </p>
                </div>
                <Badge tone={hasBlockingValidationIssues ? "warning" : "success"}>
                  {hasBlockingValidationIssues ? "Нужно исправить" : "Готово"}
                </Badge>
              </div>
              {validationIssues.length ? (
                <ul className="mt-3 space-y-2 text-sm">
                  {validationIssues.slice(0, 5).map((issue) => (
                    <li
                      className={cn(
                        "rounded-[0.8rem] px-3 py-2",
                        issue.severity === "error"
                          ? "bg-rose-50 text-rose-700"
                          : "bg-amber-50 text-amber-800",
                      )}
                      key={issue.key}
                    >
                      {issue.message}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Черновик из версии</span>
                <span className="font-medium text-slate-900">{loadedVersion ?? "текущая"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Форм в черновике</span>
                <span className="font-medium text-slate-900">{draft?.forms.length ?? 0}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Всего полей</span>
                <span className="font-medium text-slate-900">
                  {draft?.forms.reduce((sum, form) => sum + form.fields.length, 0) ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Обязательных</span>
                <span className="font-medium text-slate-900">
                  {draft?.forms.reduce(
                    (sum, form) => sum + form.fields.filter((field) => field.required).length,
                    0
                  ) ?? 0}
                </span>
              </div>
            </div>

            <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
              <div className="flex items-center gap-2">
                <FolderClock className="h-4 w-4 text-brand-700" />
                <p className="font-semibold text-slate-900">Последняя публикация</p>
              </div>
              <p className="mt-3 text-sm text-slate-600">
                {formsQuery.data?.summary.last_published_by ?? "builtin_default"}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {formatDateTime(formsQuery.data?.summary.last_published_at)}
              </p>
            </div>

            <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">Предпросмотр маршрута</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Заполните пример значений и проверьте, какая очередь или routing rule сработает для текущей формы.
                  </p>
                </div>
                <Button
                  disabled={!selectedForm || previewMutation.isPending}
                  onClick={() => previewMutation.mutate()}
                  size="sm"
                >
                  {previewMutation.isPending ? "Проверяем..." : "Проверить"}
                </Button>
              </div>

              {selectedForm ? (
                <div className="mt-4 space-y-3">
                  {selectedForm.fields
                    .filter((field) => isPreviewFieldVisible(field, previewValues))
                    .map((field) => {
                      const currentValue = previewValues[field.key];
                      if (field.type === "checkbox") {
                        return (
                          <label
                            key={field.key}
                            className="flex items-center gap-3 rounded-[1rem] border border-border bg-surface-subtle px-4 py-3 text-sm"
                          >
                            <input
                              checked={Boolean(currentValue)}
                              onChange={(event) => {
                                updatePreviewValue(field.key, event.currentTarget.checked);
                              }}
                              type="checkbox"
                            />
                            <span>{field.label}</span>
                          </label>
                        );
                      }
                      if (field.type === "select" || field.type === "radio") {
                        return (
                          <label key={field.key} className="space-y-2 text-sm font-medium text-slate-800">
                            <span>{field.label}</span>
                            <Select
                              onChange={(event) => {
                                updatePreviewValue(field.key, event.target.value);
                              }}
                              value={String(currentValue ?? "")}
                            >
                              <option value="">Не выбрано</option>
                              {field.options.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </Select>
                          </label>
                        );
                      }
                      return (
                        <label key={field.key} className="space-y-2 text-sm font-medium text-slate-800">
                          <span>{field.label}</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) => {
                              updatePreviewValue(field.key, event.currentTarget.value);
                            }}
                            placeholder={field.placeholder}
                            value={String(currentValue ?? "")}
                          />
                        </label>
                      );
                    })}
                </div>
              ) : (
                <div className="mt-4 rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
                  Сначала выберите форму в редакторе.
                </div>
              )}

              {previewValidationIssues.length ? (
                <ul className="mt-4 space-y-2 rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
                  {previewValidationIssues.map((issue) => (
                    <li key={issue.key}>{issue.message}</li>
                  ))}
                </ul>
              ) : null}

              {previewMutation.isError ? (
                <div className="mt-4 rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
                  {previewMutation.error instanceof Error
                    ? previewMutation.error.message
                    : "Не удалось построить preview маршрута."}
                </div>
              ) : null}

              {routePreview ? (
                <div className="mt-4 space-y-3 rounded-[1rem] bg-surface-subtle px-4 py-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Результат</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">
                      {routePreview.target_queue_name ?? "Очередь не найдена"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {routePreview.fallback_applied
                        ? "Совпадений по правилам не нашлось, сработал fallback."
                        : routePreview.matched_rule
                          ? `Совпало правило #${routePreview.matched_rule.id} с priority ${routePreview.matched_rule.priority_order}.`
                          : "Совпадений по правилам не найдено."}
                    </p>
                  </div>

                  <div className="space-y-2 text-sm text-slate-600">
                    <div className="flex items-center justify-between gap-3">
                      <span>ticket_type</span>
                      <code>{routePreview.ticket_type}</code>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>request_kind</span>
                      <code>{routePreview.request_kind}</code>
                    </div>
                    {routePreview.matched_rule ? (
                      <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3">
                        <p className="font-medium text-slate-900">Условие правила</p>
                        <p className="mt-2 text-sm font-semibold text-slate-800">
                          {describeRouteCondition(routePreview.matched_rule.condition_json)}
                        </p>
                      </div>
                    ) : null}
                  </div>

                  {routePreview.summary_rows.length > 0 ? (
                    <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3">
                      <p className="font-medium text-slate-900">Нормализованные данные формы</p>
                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        {routePreview.summary_rows.map((row) => (
                          <div key={row.key} className="flex items-center justify-between gap-3">
                            <span>{row.label}</span>
                            <strong className="text-slate-900">{row.value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {selectedForm?.playbook_triggers[0]?.enabled &&
                  selectedForm.playbook_triggers[0].playbook_key.trim() ? (
                    <div className="rounded-[0.9rem] border border-brand-100 bg-white px-3 py-3">
                      <p className="font-medium text-slate-900">Автозапуск плейбука</p>
                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        <div className="flex items-center justify-between gap-3">
                          <span>Ключ плейбука</span>
                          <strong className="text-slate-900">
                            {selectedForm.playbook_triggers[0].playbook_key}
                          </strong>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>Событие</span>
                          <strong className="text-slate-900">ticket_created</strong>
                        </div>
                      </div>
                      <p className="mt-3 text-sm text-slate-500">
                        Факты формы будут приложены к запуску после создания тикета.
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
              Публикация всегда создаёт новую версию pack и сразу делает её активной. Если нужен откат, загрузите
              прошлую версию слева и либо сделайте её preferred, либо выпустите на её основе новую версию.
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
