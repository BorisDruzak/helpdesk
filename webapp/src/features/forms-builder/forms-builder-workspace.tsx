import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Braces,
  CheckCircle2,
  ChevronDown,
  Eye,
  FileCheck2,
  FileClock,
  FilePenLine,
  GripVertical,
  History,
  LayoutDashboard,
  ListChecks,
  Plus,
  RefreshCcw,
  Route,
  Save,
  ShieldCheck,
  Stethoscope,
  Trash2,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { requirePermission } from "../auth/permissions";
import { cn } from "../../shared/ui/cn";
import {
  fetchAdminFormsCatalog,
  fetchHelpdeskModelRegistry,
  previewAdminFormProcess,
  publishAdminFormsCatalog,
  publishHelpdeskSmartView,
  saveAdminFormsDraft,
  setAdminFormsPreferredVersion,
  validateAdminFormsCatalog,
  type AdminFormsFieldItem,
  type AdminFormsFieldOption,
  type AdminFormsFieldType,
  type AdminFormsFormItem,
  type AdminFormsPayload,
  type AdminFormsPlaybookTrigger,
  type AdminFormsProcessPreviewResult,
  type AdminFormsSaveRequest,
  type AdminFormsValidateResult,
  type AdminHelpdeskPolicyItem,
  type AdminHelpdeskSmartViewItem,
} from "./api";
import { fetchTicketFormsPackList, fetchTicketFormsPackVersion, type TicketFormsPackSummary } from "./catalog-api";
import { fetchSupportQueue, type SupportQueuePayload } from "../queues/api";

type FormsBuilderMode =
  | "overview"
  | "template_editor"
  | "policy_editor"
  | "smart_views"
  | "versions"
  | "process_preview";

type BuilderComplexityMode = "basic" | "expert";

type CatalogDraft = {
  title: string;
  description: string;
  forms: AdminFormsFormItem[];
};

type Feedback = {
  tone: "success" | "error";
  text: string;
} | null;

type VersionCompareSummary = {
  fromVersion: string;
  toVersion: string;
  added: number;
  removed: number;
  changed: number;
  unchanged: number;
};

type TemplateStepKey =
  | "main"
  | "classification"
  | "fields"
  | "process"
  | "priority"
  | "routing"
  | "sla"
  | "approvals"
  | "diagnostics"
  | "closure"
  | "visibility"
  | "passport"
  | "check";

const MODE_QUERY_TO_STATE: Record<string, FormsBuilderMode> = {
  overview: "overview",
  template: "template_editor",
  template_editor: "template_editor",
  policy: "policy_editor",
  policy_editor: "policy_editor",
  "smart-views": "smart_views",
  smart_views: "smart_views",
  versions: "versions",
  preview: "process_preview",
  process_preview: "process_preview",
};

const MODE_STATE_TO_QUERY: Record<FormsBuilderMode, string> = {
  overview: "overview",
  template_editor: "template",
  policy_editor: "policy",
  smart_views: "smart-views",
  versions: "versions",
  process_preview: "preview",
};

const BUILDER_MODES = [
  { mode: "overview", label: "Обзор", icon: LayoutDashboard },
  { mode: "template_editor", label: "Шаблоны", icon: FilePenLine },
  { mode: "policy_editor", label: "Политики", icon: ShieldCheck },
  { mode: "smart_views", label: "Smart views", icon: Eye },
  { mode: "versions", label: "Версии", icon: History },
  { mode: "process_preview", label: "Проверка процесса", icon: Stethoscope },
] satisfies Array<{ mode: FormsBuilderMode; label: string; icon: typeof LayoutDashboard }>;

const TEMPLATE_STEPS: Array<{ key: TemplateStepKey; label: string; description: string }> = [
  { key: "main", label: "Основное", description: "Название и публичное описание" },
  { key: "classification", label: "Классификация", description: "Тип обращения и каталог" },
  { key: "fields", label: "Поля формы", description: "Поля, видимость и роли" },
  { key: "process", label: "Процесс", description: "Связанные policy refs" },
  { key: "priority", label: "Приоритет", description: "Impact, urgency, importance" },
  { key: "routing", label: "Роутинг", description: "Routing policy и queue fallback" },
  { key: "sla", label: "SLA/OLA", description: "Сроки ответа и обработки" },
  { key: "approvals", label: "Согласования", description: "Approver source и режим" },
  { key: "diagnostics", label: "Диагностика", description: "Playbooks и входные факты" },
  { key: "closure", label: "Закрытие", description: "Evidence и resolution code" },
  { key: "visibility", label: "Видимость", description: "Публичные поля и статусы" },
  { key: "passport", label: "Паспорт", description: "Reporting и паспорт решения" },
  { key: "check", label: "Проверка конфигурации", description: "Ошибки и публикация" },
];

const FIELD_ROLE_GROUPS = [
  {
    title: "Приоритет",
    roles: [
      { value: "priority_impact", label: "Priority impact" },
      { value: "priority_urgency", label: "Priority urgency" },
      { value: "priority_importance", label: "Priority importance" },
    ],
  },
  { title: "Маршрутизация", roles: [{ value: "routing_field", label: "Routing field" }] },
  { title: "Диагностика", roles: [{ value: "diagnostic_input", label: "Diagnostic input" }] },
  { title: "Согласования", roles: [{ value: "approval_subject", label: "Approval subject" }] },
  { title: "Закрытие", roles: [{ value: "closure_evidence", label: "Closure evidence" }] },
  {
    title: "Отчётность / паспорт",
    roles: [
      { value: "reporting_dimension", label: "Reporting dimension" },
      { value: "passport_fact", label: "Passport fact" },
      { value: "visibility_public", label: "Requester-visible fact" },
    ],
  },
  { title: "Прочее", roles: [{ value: "display_only", label: "Display only" }] },
] as const;

const FIELD_TYPE_LABELS: Record<AdminFormsFieldType, string> = {
  text: "Текст",
  textarea: "Текстовая область",
  select: "Список",
  multi_select: "Мультивыбор",
  radio: "Переключатель",
  checkbox: "Флажок",
  date: "Дата",
  datetime: "Дата и время",
  file: "Файл",
  user_picker: "Пользователь",
  department_picker: "Отдел",
  location_picker: "Локация",
  device_picker: "Устройство",
  service_picker: "Сервис",
  url: "URL",
  phone: "Телефон",
  email: "Email",
};

const POLICY_REFS = [
  ["priority_policy_ref", "Приоритет"],
  ["routing_policy_ref", "Роутинг"],
  ["sla_policy_ref", "SLA"],
  ["ola_policy_ref", "OLA"],
  ["approval_policy_ref", "Согласования"],
  ["diagnostic_policy_ref", "Диагностика"],
  ["closure_policy_ref", "Закрытие"],
  ["visibility_policy_ref", "Видимость"],
  ["notification_policy_ref", "Уведомления"],
  ["reporting_policy_ref", "Паспорт"],
] as const;

const POLICY_JSON_FIELDS = [
  ["priority_policy", "Priority JSON"],
  ["routing_policy", "Routing JSON"],
  ["approval_policy", "Approval JSON"],
  ["diagnostic_policy", "Diagnostic JSON"],
  ["ola_policy", "OLA JSON"],
  ["closure_policy", "Closure JSON"],
  ["visibility_policy", "Visibility JSON"],
  ["notification_policy", "Notification JSON"],
  ["reporting_policy", "Reporting JSON"],
] as const;

function parseBuilderMode(value: string | null): FormsBuilderMode {
  return value ? MODE_QUERY_TO_STATE[value] ?? "overview" : "overview";
}

function parseComplexityMode(value: string | null): BuilderComplexityMode {
  return value === "expert" ? "expert" : "basic";
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function cloneDraft(payload: AdminFormsPayload): CatalogDraft {
  return {
    title: payload.summary.title,
    description: payload.summary.description ?? "",
    forms: payload.forms.map((form) => ({
      ...form,
      description: form.description ?? "",
      fields: form.fields.map((field) => ({
        ...field,
        placeholder: field.placeholder ?? "",
        help_text: field.help_text ?? "",
        options: [...field.options],
        visible_when: field.visible_when
          ? {
              field: field.visible_when.field,
              equals: field.visible_when.equals,
              values: [...field.visible_when.values],
            }
          : null,
      })),
    })),
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function asFieldOptions(value: unknown): AdminFormsFieldOption[] {
  return Array.isArray(value)
    ? value.map((item) => {
        const option = asRecord(item);
        return {
          value: String(option.value ?? option.key ?? option.label ?? ""),
          label: String(option.label ?? option.value ?? option.key ?? ""),
        };
      }).filter((option) => option.value)
    : [];
}

function normalizeVisibleWhen(value: unknown): AdminFormsFieldItem["visible_when"] {
  const rule = asRecord(value);
  const field = asString(rule.field).trim();
  if (!field) {
    return null;
  }
  return {
    field,
    equals: typeof rule.equals === "string" ? rule.equals : null,
    values: asStringArray(rule.values ?? rule.in),
  };
}

function normalizePackDraft(rawPack: Record<string, unknown>, fallbackSummary?: TicketFormsPackSummary | null): CatalogDraft {
  const forms = Array.isArray(rawPack.forms) ? rawPack.forms : [];
  return {
    title: asString(rawPack.title, fallbackSummary?.title ?? "Каталог заявок"),
    description: asString(rawPack.description, fallbackSummary?.description ?? ""),
    forms: forms.map((item) => {
      const form = asRecord(item);
      const fields = Array.isArray(form.fields) ? form.fields : [];
      return {
        key: asString(form.key),
        request_kind: asString(form.request_kind, asString(form.key)),
        ticket_type: asNullableString(form.ticket_type),
        title: asString(form.title, asString(form.key)),
        description: asString(form.description),
        category_id: asNumberOrNull(form.category_id),
        service_id: asNumberOrNull(form.service_id),
        subcategory_id: asNumberOrNull(form.subcategory_id),
        default_queue_id: asNumberOrNull(form.default_queue_id),
        sla_policy_id: asNumberOrNull(form.sla_policy_id),
        suggested_playbook_id: asNullableString(form.suggested_playbook_id),
        field_roles: asRecord(form.field_roles) as Record<string, string[]>,
        priority_policy: asRecord(form.priority_policy),
        routing_policy: asRecord(form.routing_policy),
        approval_policy: asRecord(form.approval_policy),
        diagnostic_policy: asRecord(form.diagnostic_policy),
        ola_policy: asRecord(form.ola_policy),
        closure_policy: asRecord(form.closure_policy),
        visibility_policy: asRecord(form.visibility_policy),
        notification_policy: asRecord(form.notification_policy),
        reporting_policy: asRecord(form.reporting_policy),
        priority_policy_ref: asNullableString(form.priority_policy_ref),
        routing_policy_ref: asNullableString(form.routing_policy_ref),
        sla_policy_ref: asNullableString(form.sla_policy_ref),
        ola_policy_ref: asNullableString(form.ola_policy_ref),
        approval_policy_ref: asNullableString(form.approval_policy_ref),
        diagnostic_policy_ref: asNullableString(form.diagnostic_policy_ref),
        closure_policy_ref: asNullableString(form.closure_policy_ref),
        visibility_policy_ref: asNullableString(form.visibility_policy_ref),
        notification_policy_ref: asNullableString(form.notification_policy_ref),
        reporting_policy_ref: asNullableString(form.reporting_policy_ref),
        route_preview_examples: Array.isArray(form.route_preview_examples) ? form.route_preview_examples as Array<Record<string, unknown>> : [],
        process_preview_examples: Array.isArray(form.process_preview_examples) ? form.process_preview_examples as Array<Record<string, unknown>> : [],
        field_aliases: asRecord(form.field_aliases) as Record<string, string | string[]>,
        field_migration_note: asNullableString(form.field_migration_note),
        playbook_triggers: Array.isArray(form.playbook_triggers) ? form.playbook_triggers as AdminFormsPlaybookTrigger[] : [],
        fields: fields.map((rawField) => {
          const field = asRecord(rawField);
          const type = asString(field.type, "text") as AdminFormsFieldType;
          return {
            key: asString(field.key),
            label: asString(field.label, asString(field.key)),
            type,
            type_label: FIELD_TYPE_LABELS[type] ?? type,
            required: Boolean(field.required),
            placeholder: asString(field.placeholder),
            help_text: asString(field.help_text),
            options: asFieldOptions(field.options),
            visible_when: normalizeVisibleWhen(field.visible_when),
            validation: asRecord(field.validation),
            process_mapping: asRecord(field.process_mapping),
          };
        }),
      };
    }),
  };
}

function draftFingerprint(draft: CatalogDraft | null) {
  return JSON.stringify(draft);
}

function toSaveField(field: AdminFormsFieldItem): AdminFormsSaveRequest["forms"][number]["fields"][number] {
  return {
    key: field.key,
    label: field.label,
    type: field.type,
    required: field.required,
    placeholder: field.placeholder ?? "",
    help_text: field.help_text ?? "",
    options: field.options,
    validation: field.validation,
    process_mapping: field.process_mapping,
    visible_when: field.visible_when
      ? {
          field: field.visible_when.field,
          equals: field.visible_when.equals ?? undefined,
          values: field.visible_when.values,
        }
      : undefined,
  };
}

function toSaveForm(form: AdminFormsFormItem): AdminFormsSaveRequest["forms"][number] {
  return {
    key: form.key,
    request_kind: form.request_kind,
    ticket_type: form.ticket_type ?? null,
    title: form.title,
    description: form.description ?? "",
    category_id: form.category_id ?? null,
    service_id: form.service_id ?? null,
    subcategory_id: form.subcategory_id ?? null,
    default_queue_id: form.default_queue_id ?? null,
    sla_policy_id: form.sla_policy_id ?? null,
    suggested_playbook_id: form.suggested_playbook_id ?? null,
    field_roles: form.field_roles ?? {},
    priority_policy: form.priority_policy ?? {},
    routing_policy: form.routing_policy ?? {},
    approval_policy: form.approval_policy ?? {},
    diagnostic_policy: form.diagnostic_policy ?? {},
    ola_policy: form.ola_policy ?? {},
    closure_policy: form.closure_policy ?? {},
    visibility_policy: form.visibility_policy ?? {},
    notification_policy: form.notification_policy ?? {},
    reporting_policy: form.reporting_policy ?? {},
    priority_policy_ref: form.priority_policy_ref ?? null,
    routing_policy_ref: form.routing_policy_ref ?? null,
    sla_policy_ref: form.sla_policy_ref ?? null,
    ola_policy_ref: form.ola_policy_ref ?? null,
    approval_policy_ref: form.approval_policy_ref ?? null,
    diagnostic_policy_ref: form.diagnostic_policy_ref ?? null,
    closure_policy_ref: form.closure_policy_ref ?? null,
    visibility_policy_ref: form.visibility_policy_ref ?? null,
    notification_policy_ref: form.notification_policy_ref ?? null,
    reporting_policy_ref: form.reporting_policy_ref ?? null,
    route_preview_examples: form.route_preview_examples ?? [],
    process_preview_examples: form.process_preview_examples ?? [],
    field_aliases: form.field_aliases ?? {},
    field_migration_note: form.field_migration_note ?? null,
    playbook_triggers: form.playbook_triggers ?? [],
    fields: form.fields.map(toSaveField),
  };
}

function toSaveRequest(draft: CatalogDraft): AdminFormsSaveRequest {
  return {
    title: draft.title,
    description: draft.description,
    forms: draft.forms.map(toSaveForm),
  };
}

function createEmptyField(index: number): AdminFormsFieldItem {
  return {
    key: `field_${index}`,
    label: `Новое поле ${index}`,
    type: "text",
    type_label: "Текст",
    required: false,
    placeholder: "",
    help_text: "",
    options: [],
    visible_when: null,
    validation: {},
    process_mapping: {},
  };
}

function getFieldRoles(form: AdminFormsFormItem, fieldKey: string): string[] {
  return Object.entries(form.field_roles ?? {})
    .filter(([, fields]) => Array.isArray(fields) && fields.includes(fieldKey))
    .map(([role]) => role);
}

function isFieldVisible(field: AdminFormsFieldItem, values: Record<string, string | boolean>) {
  if (!field.visible_when?.field) {
    return true;
  }
  const actual = values[field.visible_when.field];
  if (field.visible_when.values.length > 0) {
    return field.visible_when.values.includes(String(actual ?? ""));
  }
  if (field.visible_when.equals !== null && field.visible_when.equals !== "") {
    return String(actual ?? "") === String(field.visible_when.equals);
  }
  return true;
}

function buildPreviewValues(form: AdminFormsFormItem | null, current: Record<string, string | boolean>) {
  if (!form) {
    return {};
  }
  return Object.fromEntries(
    form.fields.map((field) => [
      field.key,
      current[field.key] ?? (field.type === "checkbox" ? false : field.options[0]?.value ?? ""),
    ])
  );
}

function issueCounts(report: AdminFormsValidateResult | null, draft: CatalogDraft | null) {
  if (report) {
    return {
      errors: report.summary.errors_count,
      warnings: report.summary.warnings_count,
      canPublish: report.summary.can_publish,
    };
  }
  const missing = draft?.forms.reduce((count, form) => {
    const formIssues = Number(!form.title.trim()) + Number(!form.key.trim());
    return count + formIssues + form.fields.filter((field) => !field.key.trim() || !field.label.trim()).length;
  }, 0) ?? 0;
  return { errors: missing, warnings: 0, canPublish: false };
}

function getPublicationBlocker(
  report: AdminFormsValidateResult | null,
  publishAccess: { allowed: boolean; reason: string | null },
  isChecking: boolean
) {
  if (!publishAccess.allowed) {
    return publishAccess.reason ?? "Недостаточно прав для публикации.";
  }
  if (isChecking) {
    return "Дождитесь завершения проверки публикации.";
  }
  if (!report) {
    return "Сначала выполните проверку публикации. UI не отправит publish, пока preflight не подтвердит готовность.";
  }
  if (!report.summary.can_publish) {
    const firstBlocker = [...report.errors, ...report.warnings].find((issue) => issue.blocking !== false);
    return firstBlocker?.message ?? "Исправьте блокирующие ошибки перед публикацией.";
  }
  return null;
}

function compareCatalogDrafts(
  fromVersion: string,
  fromDraft: CatalogDraft,
  toVersion: string,
  toDraft: CatalogDraft
): VersionCompareSummary {
  const fromItems = new Map(fromDraft.forms.map((form) => [form.key, draftFingerprint({ title: "", description: "", forms: [form] })]));
  const toItems = new Map(toDraft.forms.map((form) => [form.key, draftFingerprint({ title: "", description: "", forms: [form] })]));
  let added = 0;
  let removed = 0;
  let changed = 0;
  let unchanged = 0;

  for (const [key, value] of toItems) {
    if (!fromItems.has(key)) {
      added += 1;
    } else if (fromItems.get(key) === value) {
      unchanged += 1;
    } else {
      changed += 1;
    }
  }
  for (const key of fromItems.keys()) {
    if (!toItems.has(key)) {
      removed += 1;
    }
  }

  return { fromVersion, toVersion, added, removed, changed, unchanged };
}

function policyList(policies: Record<string, AdminHelpdeskPolicyItem[]> | undefined) {
  return Object.entries(policies ?? {}).flatMap(([kind, items]) => items.map((item) => ({ ...item, kind })));
}

function SectionTitle({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight text-slate-950">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
    </div>
  );
}

export function FormsBuilderWorkspace({ permissions }: { permissions?: string[] } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const activeMode = parseBuilderMode(searchParams.get("mode"));
  const complexityMode = parseComplexityMode(searchParams.get("complexity"));
  const [draft, setDraft] = useState<CatalogDraft | null>(null);
  const [baseline, setBaseline] = useState("null");
  const [selectedFormKey, setSelectedFormKey] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [templateStep, setTemplateStep] = useState<TemplateStepKey>("fields");
  const [selectedPolicyCode, setSelectedPolicyCode] = useState<string | null>(null);
  const [selectedSmartViewCode, setSelectedSmartViewCode] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [validationReport, setValidationReport] = useState<AdminFormsValidateResult | null>(null);
  const [versionCompare, setVersionCompare] = useState<VersionCompareSummary | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [previewValues, setPreviewValues] = useState<Record<string, string | boolean>>({});
  const [versionQuery, setVersionQuery] = useState("");

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
  const registryQuery = useQuery({
    queryKey: ["admin-helpdesk-model-registry"],
    queryFn: fetchHelpdeskModelRegistry,
    retry: false,
  });

  const publishAccess = requirePermission({ permissions: permissions ?? [] }, "admin.forms.publish");
  const selectedForm = draft?.forms.find((form) => form.key === selectedFormKey) ?? draft?.forms[0] ?? null;
  const selectedField =
    selectedForm?.fields.find((field) => field.key === selectedFieldKey) ?? selectedForm?.fields[0] ?? null;
  const selectedPolicy =
    policyList(registryQuery.data?.policies).find((policy) => policy.code === selectedPolicyCode) ??
    policyList(registryQuery.data?.policies)[0] ??
    null;
  const selectedSmartView =
    registryQuery.data?.smart_views.find((view) => view.code === selectedSmartViewCode) ??
    registryQuery.data?.smart_views[0] ??
    null;
  const selectedVersionItem =
    versionsQuery.data?.packs.find((version) => version.version === selectedVersion) ??
    versionsQuery.data?.current ??
    versionsQuery.data?.packs[0] ??
    null;
  const hasUnsavedChanges = draftFingerprint(draft) !== baseline;
  const health = issueCounts(validationReport, draft);
  const currentStepIndex = Math.max(0, TEMPLATE_STEPS.findIndex((step) => step.key === templateStep));
  const visibleVersions = useMemo(
    () =>
      (versionsQuery.data?.packs ?? []).filter((item) => {
        const query = versionQuery.trim().toLowerCase();
        if (!query) {
          return true;
        }
        return `${item.version} ${item.title} ${item.created_by ?? ""}`.toLowerCase().includes(query);
      }),
    [versionQuery, versionsQuery.data?.packs]
  );

  useEffect(() => {
    if (!formsQuery.data || draft) {
      return;
    }
    const nextDraft = cloneDraft(formsQuery.data);
    setDraft(nextDraft);
    setBaseline(draftFingerprint(nextDraft));
    setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
    setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
  }, [draft, formsQuery.data]);

  useEffect(() => {
    const templateKey = searchParams.get("template");
    if (!templateKey || !draft?.forms.some((form) => form.key === templateKey)) {
      return;
    }
    setSelectedFormKey(templateKey);
    setSelectedFieldKey(draft.forms.find((form) => form.key === templateKey)?.fields[0]?.key ?? null);
  }, [draft, searchParams]);

  useEffect(() => {
    const policyCode = searchParams.get("policy");
    if (!policyCode || !policyList(registryQuery.data?.policies).some((policy) => policy.code === policyCode)) {
      return;
    }
    setSelectedPolicyCode(policyCode);
  }, [registryQuery.data?.policies, searchParams]);

  useEffect(() => {
    const viewCode = searchParams.get("view");
    if (!viewCode || !registryQuery.data?.smart_views.some((view) => view.code === viewCode)) {
      return;
    }
    setSelectedSmartViewCode(viewCode);
  }, [registryQuery.data?.smart_views, searchParams]);

  useEffect(() => {
    const version = searchParams.get("version");
    if (!version || !versionsQuery.data?.packs.some((item) => item.version === version)) {
      return;
    }
    setSelectedVersion(version);
  }, [searchParams, versionsQuery.data?.packs]);

  useEffect(() => {
    setPreviewValues((current) => buildPreviewValues(selectedForm, current));
  }, [selectedForm?.key]);

  useEffect(() => {
    if (selectedForm && !selectedField) {
      setSelectedFieldKey(selectedForm.fields[0]?.key ?? null);
    }
  }, [selectedField, selectedForm]);

  const saveDraftMutation = useMutation({
    mutationFn: saveAdminFormsDraft,
    onSuccess: (result) => {
      setDraftId(result.draft_id);
      setBaseline(draftFingerprint(draft));
      setValidationReport(null);
      setFeedback({ tone: "success", text: result.message });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось сохранить черновик." });
    },
  });
  const validateMutation = useMutation({
    mutationFn: validateAdminFormsCatalog,
    onSuccess: (result) => {
      setValidationReport(result);
      setFeedback({ tone: result.summary.can_publish ? "success" : "error", text: result.message });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось проверить каталог." });
    },
  });
  const publishMutation = useMutation({
    mutationFn: publishAdminFormsCatalog,
    onSuccess: async (result) => {
      const nextDraft = { title: result.summary.title, description: result.summary.description ?? "", forms: result.forms };
      setDraft(nextDraft);
      setBaseline(draftFingerprint(nextDraft));
      setDraftId(null);
      setValidationReport(null);
      setFeedback({ tone: "success", text: result.message });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось опубликовать каталог." });
    },
  });
  const preferredMutation = useMutation({
    mutationFn: setAdminFormsPreferredVersion,
    onSuccess: async (result) => {
      setFeedback({ tone: "success", text: result.message });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось переключить preferred." });
    },
  });
  const processPreviewMutation = useMutation({
    mutationFn: async () => {
      if (!selectedForm) {
        throw new Error("Сначала выберите шаблон обращения.");
      }
      return previewAdminFormProcess({ form: toSaveForm(selectedForm), form_payload: previewValues });
    },
  });
  const smartViewPreviewMutation = useMutation({
    mutationFn: async (view: AdminHelpdeskSmartViewItem) =>
      fetchSupportQueue({ scope: "all", statusFilter: "all", smartView: view.code, query: "" }),
    onSuccess: (result, view) => {
      setFeedback({ tone: "success", text: `Предпросмотр ${view.title || view.code}: найдено ${result.summary.visible_count} заявок.` });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось выполнить предпросмотр smart view." });
    },
  });
  const smartViewPublishMutation = useMutation({
    mutationFn: async (view: AdminHelpdeskSmartViewItem) =>
      publishHelpdeskSmartView({
        code: view.code,
        title: view.title,
        description: view.description,
        scope_level: view.scope_level,
        scope_ref: view.scope_ref,
        filter: view.filter,
        sort: view.sort,
        columns: view.columns,
        requested_version: view.version,
      }),
    onSuccess: async (result) => {
      setFeedback({ tone: "success", text: result.message });
      setSelectedSmartViewCode(result.smart_view.code);
      await queryClient.invalidateQueries({ queryKey: ["admin-helpdesk-model-registry"] });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось опубликовать smart view." });
    },
  });
  const openVersionMutation = useMutation({
    mutationFn: async (version: TicketFormsPackSummary) => {
      const detail = await fetchTicketFormsPackVersion(version.version);
      return { version, draft: normalizePackDraft(detail.pack, version) };
    },
    onSuccess: ({ version, draft: loadedDraft }) => {
      setDraft(loadedDraft);
      setBaseline(draftFingerprint(loadedDraft));
      setDraftId(null);
      setValidationReport(null);
      setVersionCompare(null);
      setSelectedFormKey(loadedDraft.forms[0]?.key ?? null);
      setSelectedFieldKey(loadedDraft.forms[0]?.fields[0]?.key ?? null);
      setTemplateStep("fields");
      setFeedback({ tone: "success", text: `Версия ${version.version} открыта в редакторе.` });
      setMode("template_editor", { version: version.version, template: loadedDraft.forms[0]?.key ?? null });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось открыть версию в редакторе." });
    },
  });
  const compareVersionMutation = useMutation({
    mutationFn: async (version: TicketFormsPackSummary) => {
      const currentVersion = versionsQuery.data?.current?.version ?? formsQuery.data?.summary.version ?? version.version;
      const [fromDetail, toDetail] = await Promise.all([
        fetchTicketFormsPackVersion(currentVersion),
        fetchTicketFormsPackVersion(version.version),
      ]);
      return compareCatalogDrafts(
        currentVersion,
        normalizePackDraft(fromDetail.pack, versionsQuery.data?.current),
        version.version,
        normalizePackDraft(toDetail.pack, version)
      );
    },
    onSuccess: (summary) => {
      setVersionCompare(summary);
      setFeedback({
        tone: "success",
        text: `Сравнение ${summary.fromVersion} → ${summary.toVersion}: добавлено ${summary.added}, изменено ${summary.changed}, удалено ${summary.removed}.`,
      });
    },
    onError: (error) => {
      setFeedback({ tone: "error", text: error instanceof Error ? error.message : "Не удалось сравнить версии каталога." });
    },
  });
  const publicationBlocker = getPublicationBlocker(validationReport, publishAccess, validateMutation.isPending);

  function setMode(mode: FormsBuilderMode, next?: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams);
    params.set("mode", MODE_STATE_TO_QUERY[mode]);
    Object.entries(next ?? {}).forEach(([key, value]) => {
      if (value === null) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });
    setSearchParams(params);
  }

  function setComplexityMode(mode: BuilderComplexityMode) {
    const params = new URLSearchParams(searchParams);
    if (mode === "expert") {
      params.set("complexity", "expert");
    } else {
      params.delete("complexity");
    }
    setSearchParams(params);
  }

  function saveDraft() {
    if (!draft) {
      return;
    }
    if (!publishAccess.allowed) {
      setFeedback({ tone: "error", text: publishAccess.reason });
      return;
    }
    saveDraftMutation.mutate({ ...toSaveRequest(draft), base_version: formsQuery.data?.summary.version ?? null, draft_id: draftId });
  }

  function validateDraft() {
    if (!draft) {
      return;
    }
    validateMutation.mutate({ ...toSaveRequest(draft), base_version: formsQuery.data?.summary.version ?? null, draft_id: draftId });
  }

  function publishDraft() {
    if (!draft) {
      return;
    }
    if (publicationBlocker) {
      setFeedback({ tone: "error", text: publicationBlocker });
      return;
    }
    publishMutation.mutate({ ...toSaveRequest(draft), draft_id: draftId, make_preferred: true });
  }

  function previewSmartView() {
    if (!selectedSmartView) {
      setFeedback({ tone: "error", text: "Сначала выберите smart view." });
      return;
    }
    setMode("smart_views", { view: selectedSmartView.code });
    smartViewPreviewMutation.mutate(selectedSmartView);
  }

  function saveSmartView() {
    if (!selectedSmartView) {
      setFeedback({ tone: "error", text: "Сначала выберите smart view." });
      return;
    }
    setFeedback({
      tone: "success",
      text: "Черновик smart view пока не сохраняется отдельным endpoint. Для реального изменения используйте публикацию новой версии.",
    });
  }

  function publishSmartView() {
    if (!selectedSmartView) {
      setFeedback({ tone: "error", text: "Сначала выберите smart view." });
      return;
    }
    if (!publishAccess.allowed) {
      setFeedback({ tone: "error", text: publishAccess.reason ?? "Недостаточно прав для публикации." });
      return;
    }
    smartViewPublishMutation.mutate(selectedSmartView);
  }

  function openSelectedVersionInEditor() {
    if (!selectedVersionItem) {
      setFeedback({ tone: "error", text: "Сначала выберите версию каталога." });
      return;
    }
    openVersionMutation.mutate(selectedVersionItem);
  }

  function compareSelectedVersion() {
    if (!selectedVersionItem) {
      setFeedback({ tone: "error", text: "Сначала выберите версию каталога." });
      return;
    }
    compareVersionMutation.mutate(selectedVersionItem);
  }

  function updateSelectedForm(updater: (form: AdminFormsFormItem) => AdminFormsFormItem) {
    if (!selectedForm) {
      return;
    }
    setValidationReport(null);
    setDraft((current) =>
      current
        ? {
            ...current,
            forms: current.forms.map((form) => (form.key === selectedForm.key ? updater(form) : form)),
          }
        : current
    );
  }

  function updateSelectedField(updater: (field: AdminFormsFieldItem) => AdminFormsFieldItem) {
    if (!selectedField) {
      return;
    }
    updateSelectedForm((form) => ({
      ...form,
      fields: form.fields.map((field) => (field.key === selectedField.key ? updater(field) : field)),
    }));
  }

  function toggleFieldRole(role: string, checked: boolean) {
    if (!selectedField) {
      return;
    }
    updateSelectedForm((form) => {
      const nextRoles = { ...(form.field_roles ?? {}) };
      const fields = new Set(nextRoles[role] ?? []);
      if (checked) {
        fields.add(selectedField.key);
      } else {
        fields.delete(selectedField.key);
      }
      nextRoles[role] = Array.from(fields);
      return { ...form, field_roles: nextRoles };
    });
  }

  function updatePolicyRef(key: (typeof POLICY_REFS)[number][0], value: string) {
    updateSelectedForm((form) => ({ ...form, [key]: value || null }));
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 border-b border-border pb-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <p className="text-sm text-slate-500">Администрирование / Конструктор форм</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-slate-950">
            Конструктор форм
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Каталог шаблонов обращений, политик, smart views и публикаций.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand">Основан на версии {formsQuery.data?.summary.version ?? "..."}</Badge>
          <Badge tone={hasUnsavedChanges ? "warning" : "success"}>
            {hasUnsavedChanges ? "Есть изменения" : "Сохранено"}
          </Badge>
          <Badge tone={health.errors ? "danger" : "success"}>Ошибки: {health.errors}</Badge>
          <Badge tone={health.warnings ? "warning" : "neutral"}>Предупреждения: {health.warnings}</Badge>
          <div className="flex rounded-pill border border-border bg-white p-1">
            {(["basic", "expert"] as const).map((mode) => (
              <button
                className={cn(
                  "rounded-pill px-3 py-1.5 text-xs font-semibold transition-colors",
                  complexityMode === mode ? "bg-brand-600 text-white" : "text-slate-500 hover:bg-slate-100"
                )}
                key={mode}
                onClick={() => setComplexityMode(mode)}
                type="button"
              >
                {mode === "basic" ? "Базовый" : "Экспертный"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <nav aria-label="Разделы конструктора форм" className="flex flex-wrap gap-2">
        {BUILDER_MODES.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={cn(
                "inline-flex items-center gap-2 rounded-pill border px-4 py-2 text-sm font-semibold transition-colors",
                activeMode === item.mode
                  ? "border-brand-200 bg-brand-50 text-brand-800"
                  : "border-border bg-white text-slate-600 hover:border-brand-100 hover:bg-surface-subtle"
              )}
              key={item.mode}
              onClick={() => setMode(item.mode)}
              type="button"
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      {feedback ? (
        <div
          className={cn(
            "rounded-[1rem] border px-4 py-3 text-sm",
            feedback.tone === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"
          )}
        >
          {feedback.text}
        </div>
      ) : null}

      {formsQuery.isLoading ? (
        <Card>
          <CardContent className="py-10 text-sm text-slate-500">Загружаем каталог форм...</CardContent>
        </Card>
      ) : null}

      {formsQuery.isError ? (
        <Card>
          <CardContent className="py-10 text-sm text-rose-700">
            {formsQuery.error instanceof Error ? formsQuery.error.message : "Не удалось загрузить каталог форм."}
          </CardContent>
        </Card>
      ) : null}

      {draft && activeMode === "overview" ? renderOverview() : null}
      {draft && activeMode === "template_editor" ? renderTemplateEditor() : null}
      {draft && activeMode === "policy_editor" ? renderPolicyEditor() : null}
      {draft && activeMode === "smart_views" ? renderSmartViews() : null}
      {draft && activeMode === "versions" ? renderVersions() : null}
      {draft && activeMode === "process_preview" ? renderProcessPreview() : null}
    </section>
  );

  function renderOverview() {
    if (!draft) {
      return null;
    }
    const summary = formsQuery.data?.summary;
    const smartViewsCount = registryQuery.data?.summary.active_smart_views_count ?? registryQuery.data?.smart_views.length ?? 0;
    const policiesCount = registryQuery.data?.summary.active_policies_count ?? policyList(registryQuery.data?.policies).length;
    const recentTemplates = draft.forms.slice(0, 6);
    return (
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-3 2xl:grid-cols-6">
            {[
              ["Активная версия каталога", summary?.version ?? "...", "Опубликована"],
              ["Статус черновика", hasUnsavedChanges ? "Есть изменения" : "Синхронизирован", hasUnsavedChanges ? "Нужно сохранить" : "Черновик актуален"],
              ["Шаблоны", String(draft.forms.length), "Всего в каталоге"],
              ["Политики", String(policiesCount), "Активных политик"],
              ["Smart views", String(smartViewsCount), "Сохранённых срезов"],
              ["Последняя публикация", formatDate(summary?.last_published_at), summary?.last_published_by ?? "нет автора"],
            ].map(([label, value, hint]) => (
              <Card key={label}>
                <CardContent className="py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
                  <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
                  <p className="mt-1 text-xs text-slate-500">{hint}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div>
            <h2 className="text-base font-semibold text-slate-950">Что хотите сделать?</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {BUILDER_MODES.filter((item) => item.mode !== "overview").map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    className="rounded-[1rem] border border-border bg-white px-4 py-4 text-left transition-colors hover:border-brand-200 hover:bg-brand-50"
                    key={item.mode}
                    onClick={() => setMode(item.mode)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <Icon className="h-5 w-5 text-brand-700" />
                      <ArrowRight className="h-4 w-4 text-slate-400" />
                    </div>
                    <p className="mt-4 font-semibold text-slate-950">{item.label}</p>
                    <p className="mt-1 text-sm leading-5 text-slate-500">{item.mode === "template_editor" ? "Управление шаблонами обращений и полями." : item.mode === "versions" ? "История версий, публикация и rollback." : "Открыть отдельный рабочий режим конструктора."}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <div>
                <CardTitle>Недавние шаблоны</CardTitle>
                <CardDescription>На overview не показываются редакторы полей и JSON.</CardDescription>
              </div>
              <Button onClick={() => setMode("template_editor")} size="sm" trailingIcon={<ArrowRight className="h-4 w-4" />} variant="outline">
                Открыть все шаблоны
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-[0.14em] text-slate-400">
                    <tr>
                      <th className="py-3 pr-4">Название шаблона</th>
                      <th className="py-3 pr-4">Ключ</th>
                      <th className="py-3 pr-4">Статус</th>
                      <th className="py-3 pr-4">Последнее изменение</th>
                      <th className="py-3 pr-4">Владелец</th>
                      <th className="py-3">Действия</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {recentTemplates.map((form) => (
                      <tr key={form.key}>
                        <td className="py-3 pr-4 font-semibold text-slate-900">{form.title}</td>
                        <td className="py-3 pr-4 text-slate-500">{form.key}</td>
                        <td className="py-3 pr-4"><Badge tone="success">Опубликовано</Badge></td>
                        <td className="py-3 pr-4 text-slate-500">{formatDate(summary?.last_published_at)}</td>
                        <td className="py-3 pr-4 text-slate-500">{summary?.last_published_by ?? "admin"}</td>
                        <td className="py-3">
                          <Button
                            onClick={() => {
                              setSelectedFormKey(form.key);
                              setSelectedFieldKey(form.fields[0]?.key ?? null);
                              setMode("template_editor", { template: form.key });
                            }}
                            size="sm"
                            variant="outline"
                          >
                            Открыть
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <BuilderHealthPanel />
          <Card>
            <CardHeader>
              <CardTitle>Последние изменения</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              <p>Активная версия: {summary?.version ?? "..."}</p>
              <p>Последняя публикация: {formatDate(summary?.last_published_at)}</p>
              <p>Автор: {summary?.last_published_by ?? "нет данных"}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Полезные ссылки</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-brand-700">
              <p>Документация по конструктору форм</p>
              <p>Гайд по созданию шаблонов</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  function renderTemplateEditor() {
    if (!selectedForm) {
      return <EmptyState text="В каталоге пока нет шаблонов." />;
    }
    const step = TEMPLATE_STEPS[currentStepIndex] ?? TEMPLATE_STEPS[0];
    return (
      <div className="grid gap-5 xl:grid-cols-[236px_minmax(0,1fr)_320px]">
        <aside className="space-y-3 xl:sticky xl:top-24 xl:self-start">
          <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
            <p className="font-semibold text-slate-950">Шаг {currentStepIndex + 1} из {TEMPLATE_STEPS.length}</p>
            <div className="mt-3 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-brand-600" style={{ width: `${((currentStepIndex + 1) / TEMPLATE_STEPS.length) * 100}%` }} />
            </div>
          </div>
          <div className="rounded-[1rem] border border-border bg-white p-2">
            {TEMPLATE_STEPS.map((item, index) => (
              <button
                aria-current={item.key === templateStep ? "step" : undefined}
                className={cn(
                  "flex w-full items-start gap-3 rounded-[0.8rem] px-3 py-3 text-left text-sm transition-colors",
                  item.key === templateStep ? "bg-brand-50 text-brand-900" : "text-slate-600 hover:bg-slate-50"
                )}
                key={item.key}
                onClick={() => setTemplateStep(item.key)}
                type="button"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current/20 text-xs font-semibold">
                  {index + 1}
                </span>
                <span>
                  <span className="block font-semibold">{item.label}</span>
                  <span className="block text-xs text-current/70">{item.description}</span>
                </span>
              </button>
            ))}
          </div>
          <Button onClick={() => setMode("overview")} size="sm" variant="outline" leadingIcon={<ArrowLeft className="h-4 w-4" />}>
            Назад к обзору
          </Button>
        </aside>

        <main className="space-y-4">
          <Card>
            <CardHeader className="gap-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-sm text-slate-500">Конструктор форм / Шаблоны / {selectedForm.title}</p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                    Редактор шаблона обращения: {selectedForm.title}
                  </h2>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge tone="brand">Черновик</Badge>
                    <Badge tone={hasUnsavedChanges ? "warning" : "success"}>{hasUnsavedChanges ? "Есть изменения" : "Сохранено"}</Badge>
                    <Badge tone="info">Основан на версии {formsQuery.data?.summary.version ?? "..."}</Badge>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button disabled={saveDraftMutation.isPending} onClick={saveDraft} size="sm" variant="outline" leadingIcon={<Save className="h-4 w-4" />}>
                    {saveDraftMutation.isPending ? "Сохраняем..." : "Сохранить черновик"}
                  </Button>
                  <Button disabled={validateMutation.isPending} onClick={validateDraft} size="sm" variant="outline" leadingIcon={<FileCheck2 className="h-4 w-4" />}>
                    Проверить
                  </Button>
                  <Button onClick={() => setMode("process_preview", { template: selectedForm.key })} size="sm" variant="outline" leadingIcon={<Eye className="h-4 w-4" />}>
                    Предпросмотр
                  </Button>
                  <Button
                    onClick={() => setTemplateStep(TEMPLATE_STEPS[Math.min(currentStepIndex + 1, TEMPLATE_STEPS.length - 1)].key)}
                    size="sm"
                    trailingIcon={<ArrowRight className="h-4 w-4" />}
                  >
                    Далее
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <SectionTitle title={`Шаг ${currentStepIndex + 1}. ${step.label}`} description={step.description} />
              {templateStep === "fields" ? renderFieldsStep() : renderTemplateMetaStep(templateStep)}
              <div className="flex justify-between border-t border-border pt-4">
                <Button
                  disabled={currentStepIndex === 0}
                  onClick={() => setTemplateStep(TEMPLATE_STEPS[Math.max(currentStepIndex - 1, 0)].key)}
                  variant="outline"
                  leadingIcon={<ArrowLeft className="h-4 w-4" />}
                >
                  Назад
                </Button>
                <Button
                  onClick={() => setTemplateStep(TEMPLATE_STEPS[Math.min(currentStepIndex + 1, TEMPLATE_STEPS.length - 1)].key)}
                  trailingIcon={<ArrowRight className="h-4 w-4" />}
                >
                  Далее
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>

        <TemplateContextPanel />
      </div>
    );
  }

  function renderTemplateMetaStep(step: TemplateStepKey) {
    if (!selectedForm) {
      return null;
    }
    if (step === "main") {
      return (
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="Название шаблона" value={selectedForm.title} onChange={(value) => updateSelectedForm((form) => ({ ...form, title: value }))} />
          <TextField label="Ключ шаблона" value={selectedForm.key} onChange={(value) => {
            updateSelectedForm((form) => ({ ...form, key: value, request_kind: form.request_kind === form.key ? value : form.request_kind }));
            setSelectedFormKey(value);
          }} />
          <label className="space-y-2 text-sm font-medium text-slate-800 md:col-span-2">
            <span>Описание</span>
            <textarea className="field-base min-h-[110px] w-full resize-y px-4 py-3 text-sm" value={selectedForm.description ?? ""} onChange={(event) => updateSelectedForm((form) => ({ ...form, description: event.currentTarget.value }))} />
          </label>
        </div>
      );
    }
    if (step === "classification") {
      return (
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="request_kind" value={selectedForm.request_kind} onChange={(value) => updateSelectedForm((form) => ({ ...form, request_kind: value }))} />
          <TextField label="ticket_type" value={selectedForm.ticket_type ?? ""} onChange={(value) => updateSelectedForm((form) => ({ ...form, ticket_type: value || null }))} />
          <TextField label="default_queue_id" value={String(selectedForm.default_queue_id ?? "")} onChange={(value) => updateSelectedForm((form) => ({ ...form, default_queue_id: value ? Number(value) : null }))} />
          <TextField label="sla_policy_id" value={String(selectedForm.sla_policy_id ?? "")} onChange={(value) => updateSelectedForm((form) => ({ ...form, sla_policy_id: value ? Number(value) : null }))} />
        </div>
      );
    }
    if (["process", "priority", "routing", "sla", "approvals", "diagnostics", "closure", "visibility", "passport"].includes(step)) {
      return (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {POLICY_REFS.map(([key, label]) => (
              <TextField
                key={key}
                label={`${label} policy ref`}
                value={String(selectedForm[key] ?? "")}
                onChange={(value) => updatePolicyRef(key, value)}
              />
            ))}
          </div>
          {complexityMode === "expert" ? <AdvancedJsonPanel form={selectedForm} /> : <AdvancedCollapsedNotice />}
        </div>
      );
    }
    return <BuilderValidationReport />;
  }

  function renderFieldsStep() {
    if (!selectedForm) {
      return null;
    }
    return (
      <div className="grid gap-4 2xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-3 rounded-[1rem] border border-border bg-surface-subtle p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-950">Поля формы</h3>
            <Button
              onClick={() => {
                const nextField = createEmptyField(selectedForm.fields.length + 1);
                updateSelectedForm((form) => ({ ...form, fields: [...form.fields, nextField] }));
                setSelectedFieldKey(nextField.key);
              }}
              size="sm"
              leadingIcon={<Plus className="h-4 w-4" />}
            >
              Добавить поле
            </Button>
          </div>
          <div className="space-y-2">
            {selectedForm.fields.map((field) => (
              <button
                className={cn(
                  "flex w-full items-start gap-3 rounded-[0.9rem] border bg-white px-3 py-3 text-left transition-colors",
                  selectedField?.key === field.key ? "border-brand-200 bg-brand-50" : "border-border hover:border-brand-100"
                )}
                key={field.key}
                onClick={() => setSelectedFieldKey(field.key)}
                type="button"
              >
                <GripVertical className="mt-1 h-4 w-4 text-slate-400" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-slate-900">{field.label || field.key}</span>
                  <span className="mt-1 block text-xs text-slate-500">{field.key}</span>
                  <span className="mt-2 flex flex-wrap gap-1">
                    <Badge tone="neutral">{FIELD_TYPE_LABELS[field.type]}</Badge>
                    {field.required ? <Badge tone="warning">required</Badge> : null}
                    {field.visible_when ? <Badge tone="info">visible_when</Badge> : null}
                    {getFieldRoles(selectedForm, field.key).length ? <Badge tone="success">roles</Badge> : null}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
        <TemplateFieldEditor />
      </div>
    );
  }

  function TemplateFieldEditor() {
    if (!selectedField || !selectedForm) {
      return <EmptyState text="Выберите поле формы." />;
    }
    const roles = getFieldRoles(selectedForm, selectedField.key);
    return (
      <div className="space-y-4 rounded-[1rem] border border-border bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-950">Настройки поля</h3>
          <Button
            disabled={selectedForm.fields.length <= 1}
            onClick={() => {
              const remaining = selectedForm.fields.filter((field) => field.key !== selectedField.key);
              updateSelectedForm((form) => ({ ...form, fields: remaining }));
              setSelectedFieldKey(remaining[0]?.key ?? null);
            }}
            size="sm"
            variant="outline"
            leadingIcon={<Trash2 className="h-4 w-4" />}
          >
            Удалить поле
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField label="Название поля" value={selectedField.label} onChange={(value) => updateSelectedField((field) => ({ ...field, label: value }))} />
          <TextField label="Ключ поля" value={selectedField.key} onChange={(value) => {
            const previousKey = selectedField.key;
            updateSelectedForm((form) => ({
              ...form,
              field_roles: Object.fromEntries(Object.entries(form.field_roles ?? {}).map(([role, fields]) => [role, fields.map((fieldKey) => fieldKey === previousKey ? value : fieldKey)])),
              fields: form.fields.map((field) => field.key === previousKey ? { ...field, key: value } : field),
            }));
            setSelectedFieldKey(value);
          }} />
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Тип поля</span>
            <Select value={selectedField.type} onChange={(event) => updateSelectedField((field) => ({ ...field, type: event.currentTarget.value as AdminFormsFieldType }))}>
              {Object.entries(FIELD_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
          </label>
          <label className="flex min-h-11 items-center gap-3 rounded-[0.9rem] border border-border bg-surface-subtle px-4 py-2 text-sm font-medium text-slate-800">
            <input checked={selectedField.required} onChange={(event) => updateSelectedField((field) => ({ ...field, required: event.currentTarget.checked }))} type="checkbox" />
            Обязательное поле
          </label>
          <TextField label="Placeholder" value={selectedField.placeholder ?? ""} onChange={(value) => updateSelectedField((field) => ({ ...field, placeholder: value }))} />
          <TextField label="Help text" value={selectedField.help_text ?? ""} onChange={(value) => updateSelectedField((field) => ({ ...field, help_text: value }))} />
        </div>
        <div className="rounded-[1rem] border border-border bg-surface-subtle p-4">
          <h4 className="font-semibold text-slate-950">Условие показа</h4>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <TextField label="Поле-условие" value={selectedField.visible_when?.field ?? ""} onChange={(value) => updateSelectedField((field) => ({ ...field, visible_when: value ? { field: value, equals: field.visible_when?.equals ?? "", values: field.visible_when?.values ?? [] } : null }))} />
            <TextField label="Значение equals" value={selectedField.visible_when?.equals ?? ""} onChange={(value) => updateSelectedField((field) => ({ ...field, visible_when: { field: field.visible_when?.field ?? "", equals: value, values: [] } }))} />
          </div>
        </div>
        <div className="rounded-[1rem] border border-border bg-white p-4">
          <h4 className="font-semibold text-slate-950">Роли поля в процессе</h4>
          <div className="mt-4 space-y-4">
            {FIELD_ROLE_GROUPS.map((group) => (
              <div key={group.title}>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{group.title}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {group.roles.map((role) => (
                    <label className="inline-flex items-center gap-2 rounded-pill border border-border bg-surface-subtle px-3 py-2 text-sm" key={role.value}>
                      <input checked={roles.includes(role.value)} onChange={(event) => toggleFieldRole(role.value, event.currentTarget.checked)} type="checkbox" />
                      {role.label}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        {complexityMode === "expert" ? <AdvancedJsonPanel form={selectedForm} /> : <AdvancedCollapsedNotice />}
      </div>
    );
  }

  function renderPolicyEditor() {
    const policies = policyList(registryQuery.data?.policies);
    return (
      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_280px]">
        <ObjectList
          title="Политики"
          items={policies.map((policy) => ({ key: policy.code, title: policy.title || policy.code, subtitle: `${policy.kind} / ${policy.version}` }))}
          selectedKey={selectedPolicy?.code ?? null}
          onSelect={(code) => {
            setSelectedPolicyCode(code);
            setMode("policy_editor", { policy: code });
          }}
        />
        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm text-slate-500">Конструктор форм / Политики / {selectedPolicy?.kind ?? "routing"}</p>
                <CardTitle>Политика {selectedPolicy?.kind ?? "routing"}: {selectedPolicy?.title ?? "не выбрана"}</CardTitle>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge tone={selectedPolicy?.is_active ? "success" : "neutral"}>{selectedPolicy?.is_active ? "Опубликована" : "Черновик"}</Badge>
                  <Badge tone="info">version {selectedPolicy?.version ?? "n/a"}</Badge>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline">Сравнить версии</Button>
                <Button onClick={validateDraft} size="sm" variant="outline">Проверить</Button>
                <Button onClick={saveDraft} size="sm" variant="outline">Сохранить</Button>
                <Button onClick={() => setMode("versions")} size="sm">Опубликовать новую версию</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <ConditionBuilderPreview policy={selectedPolicy} />
            {complexityMode === "expert" ? (
              <pre className="max-h-[420px] overflow-auto rounded-[1rem] bg-slate-950 p-4 text-xs text-slate-100">
                {JSON.stringify(selectedPolicy?.config ?? {}, null, 2)}
              </pre>
            ) : (
              <AdvancedCollapsedNotice />
            )}
          </CardContent>
        </Card>
        <RightInfoPanel title="Где используется" rows={[
          ["Scope", selectedPolicy?.scope_level ?? "request_template"],
          ["Policy code", selectedPolicy?.code ?? "не выбрана"],
          ["Владелец", selectedPolicy?.updated_by ?? selectedPolicy?.created_by ?? "admin"],
          ["Проверка политики", "Синтаксис условий OK"],
        ]} />
      </div>
    );
  }

  function renderSmartViews() {
    const smartViews = registryQuery.data?.smart_views ?? [];
    return (
      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_280px]">
        <ObjectList
          title="Smart views"
          items={smartViews.map((view) => ({ key: view.code, title: view.title || view.code, subtitle: formatDate(view.updated_at ?? view.created_at) }))}
          selectedKey={selectedSmartView?.code ?? null}
          onSelect={(code) => {
            setSelectedSmartViewCode(code);
            setMode("smart_views", { view: code });
          }}
        />
        <SmartViewEditor
          isPreviewPending={smartViewPreviewMutation.isPending}
          isPublishPending={smartViewPublishMutation.isPending}
          onPreview={previewSmartView}
          onPublish={publishSmartView}
          onSave={saveSmartView}
          preview={smartViewPreviewMutation.data}
          view={selectedSmartView}
        />
        <RightInfoPanel title="Проверка запроса" rows={[
          ["Где используется", "Дашборды, очереди, плейбуки"],
          ["Найдено заявок", smartViewPreviewMutation.data ? String(smartViewPreviewMutation.data.summary.visible_count) : "Запустите предпросмотр"],
          ["Время выполнения", smartViewPreviewMutation.data ? "получено из API" : "нет данных"],
          ["Статус", smartViewPreviewMutation.isError ? "Ошибка" : smartViewPreviewMutation.data ? "Успешно" : "Не запускался"],
        ]} />
      </div>
    );
  }

  function renderVersions() {
    return (
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_300px]">
        <Card className="xl:sticky xl:top-24 xl:self-start">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Все версии</CardTitle>
              <Button onClick={() => void versionsQuery.refetch()} size="sm" variant="outline" leadingIcon={<RefreshCcw className="h-4 w-4" />}>Обновить</Button>
            </div>
            <SearchField value={versionQuery} onChange={(event) => setVersionQuery(event.currentTarget.value)} placeholder="Версия, автор, заметка" />
          </CardHeader>
          <CardContent className="space-y-2">
            {visibleVersions.map((version) => (
              <button
                className={cn("w-full rounded-[1rem] border px-4 py-4 text-left", selectedVersionItem?.version === version.version ? "border-brand-200 bg-brand-50" : "border-border bg-white")}
                key={version.version}
                onClick={() => setSelectedVersion(version.version)}
                type="button"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-slate-950">{version.version}</span>
                  <Badge tone={version.is_preferred ? "success" : "neutral"}>{version.is_preferred ? "Preferred" : "Архивная"}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-500">{formatDate(version.created_at)} / {version.created_by ?? "admin"}</p>
              </button>
            ))}
          </CardContent>
        </Card>
        <VersionDetails
          compareSummary={versionCompare}
          isComparing={compareVersionMutation.isPending}
          isOpening={openVersionMutation.isPending}
          onCompare={compareSelectedVersion}
          onOpenEditor={openSelectedVersionInEditor}
          version={selectedVersionItem}
        />
        <div className="space-y-4">
          <BuilderHealthPanel />
          <Card>
            <CardHeader><CardTitle>Действия с публикацией</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {publicationBlocker ? (
                <div className="rounded-[0.9rem] border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
                  {publicationBlocker}
                </div>
              ) : null}
              <Button disabled={Boolean(publicationBlocker) || publishMutation.isPending} onClick={publishDraft} className="w-full" leadingIcon={<CheckCircle2 className="h-4 w-4" />} title={publicationBlocker ?? undefined}>
                {publishMutation.isPending ? "Публикуем..." : "Опубликовать"}
              </Button>
              <Button disabled={!selectedVersionItem || selectedVersionItem.is_preferred || preferredMutation.isPending} onClick={() => selectedVersionItem ? preferredMutation.mutate(selectedVersionItem.version) : undefined} className="w-full" variant="outline">
                Сделать preferred
              </Button>
              <Button className="w-full" disabled={!selectedVersionItem || compareVersionMutation.isPending} onClick={compareSelectedVersion} variant="outline">
                {compareVersionMutation.isPending ? "Сравниваем..." : "Сравнить с текущей"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  function renderProcessPreview() {
    if (!draft) {
      return null;
    }
    const result = processPreviewMutation.data;
    return (
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_300px]">
        <Card>
          <CardHeader>
            <CardTitle>Симуляция обработки обращения</CardTitle>
            <CardDescription>form payload &rarr; validation &rarr; priority &rarr; routing &rarr; SLA/OLA &rarr; approval &rarr; diagnostics &rarr; closure.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="space-y-2 text-sm font-medium text-slate-800">
              <span>Выбранный шаблон</span>
              <Select value={selectedForm?.key ?? ""} onChange={(event) => {
                const form = draft?.forms.find((item) => item.key === event.currentTarget.value) ?? null;
                setSelectedFormKey(form?.key ?? null);
                setSelectedFieldKey(form?.fields[0]?.key ?? null);
              }}>
                {draft.forms.map((form) => <option key={form.key} value={form.key}>{form.title}</option>)}
              </Select>
            </label>
            {selectedForm?.fields.filter((field) => isFieldVisible(field, previewValues)).map((field) => (
              <PreviewInput key={field.key} field={field} value={previewValues[field.key]} onChange={(value) => setPreviewValues((current) => ({ ...current, [field.key]: value }))} />
            ))}
            <div className="flex gap-2">
              <Button disabled={processPreviewMutation.isPending} onClick={() => processPreviewMutation.mutate()} leadingIcon={<Stethoscope className="h-4 w-4" />}>
                {processPreviewMutation.isPending ? "Проверяем..." : "Проверить"}
              </Button>
              <Button onClick={() => setPreviewValues(buildPreviewValues(selectedForm, {}))} variant="outline">Сбросить</Button>
            </div>
            {processPreviewMutation.isError ? <p className="text-sm text-rose-700">{processPreviewMutation.error instanceof Error ? processPreviewMutation.error.message : "Не удалось проверить процесс."}</p> : null}
          </CardContent>
        </Card>
        <ProcessResult result={result} />
        <RightInfoPanel title="Почему так" rows={[
          ["Приоритет", String(result?.priority.priority_class ?? "Запустите проверку")],
          ["Очередь", String(result?.routing.target_queue_name ?? result?.routing.target_queue_id ?? "нет результата")],
          ["Политики", String(result?.routing.source ?? "нет результата")],
          ["Предупреждения", String((result?.validation_report as { warnings?: unknown[] } | undefined)?.warnings?.length ?? health.warnings)],
        ]} />
      </div>
    );
  }

  function BuilderHealthPanel() {
    const issues = [...(validationReport?.errors ?? []), ...(validationReport?.warnings ?? [])];
    return (
      <Card>
        <CardHeader>
          <CardTitle>Состояние каталога</CardTitle>
          <CardDescription>{validationReport ? health.canPublish ? "К публикации готово" : "Есть блокирующие замечания" : "Публикация требует preflight-проверки"}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3"><span>Ошибки</span><strong>{health.errors}</strong></div>
          <div className="flex items-center justify-between gap-3"><span>Предупреждения</span><strong>{health.warnings}</strong></div>
          <div className="flex items-center justify-between gap-3"><span>Черновик</span><strong>{hasUnsavedChanges ? "Есть изменения" : "Синхронизирован"}</strong></div>
          {!validationReport ? (
            <div className="rounded-[0.9rem] bg-amber-50 px-3 py-2 text-amber-900">Проверка ещё не запускалась. Publish заблокирован до результата preflight.</div>
          ) : null}
          {issues.slice(0, 3).map((issue) => (
            <div className="rounded-[0.9rem] bg-surface-subtle px-3 py-2" key={`${issue.code}-${issue.path ?? ""}`}>
              <p className="font-medium text-slate-900">{issue.message}</p>
              <p className="mt-1 text-xs text-slate-500">{issue.recommendation ?? issue.path ?? issue.code}</p>
            </div>
          ))}
          <Button disabled={validateMutation.isPending || !draft} onClick={validateDraft} className="w-full" variant="outline" leadingIcon={<ListChecks className="h-4 w-4" />}>
            {validateMutation.isPending ? "Проверяем..." : "Проверить"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  function BuilderValidationReport() {
    const errors = validationReport?.errors ?? [];
    const warnings = validationReport?.warnings ?? [];
    return (
      <div className="space-y-3">
        <BuilderHealthPanel />
        {[...errors, ...warnings].map((issue) => (
          <div className="rounded-[0.9rem] border border-border bg-white px-4 py-3 text-sm" key={`${issue.code}-${issue.path}`}>
            <p className="font-semibold text-slate-950">{issue.message}</p>
            <p className="mt-1 text-slate-500">{issue.recommendation ?? issue.path ?? issue.code}</p>
          </div>
        ))}
      </div>
    );
  }

  function TemplateContextPanel() {
    return (
      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
        <Card>
          <CardHeader><CardTitle>Как увидит пользователь</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {selectedForm?.fields.filter((field) => isFieldVisible(field, previewValues)).slice(0, 6).map((field) => (
              <PreviewInput key={field.key} field={field} value={previewValues[field.key]} onChange={(value) => setPreviewValues((current) => ({ ...current, [field.key]: value }))} />
            ))}
          </CardContent>
        </Card>
        <BuilderHealthPanel />
        <RightInfoPanel title="Информация о шаблоне" rows={[
          ["Название", selectedForm?.title ?? "не выбран"],
          ["Ключ", selectedForm?.key ?? "n/a"],
          ["Поля", String(selectedForm?.fields.length ?? 0)],
          ["Источник", formsQuery.data?.summary.version ?? "current"],
        ]} />
      </aside>
    );
  }
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2 text-sm font-medium text-slate-800">
      <span>{label}</span>
      <input className="field-base h-11 w-full px-4 text-sm" value={value} onChange={(event) => onChange(event.currentTarget.value)} />
    </label>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-10 text-center text-sm text-slate-500">{text}</div>;
}

function PreviewInput({ field, value, onChange }: { field: AdminFormsFieldItem; value: string | boolean | undefined; onChange: (value: string | boolean) => void }) {
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-3 rounded-[0.9rem] border border-border bg-white px-3 py-3 text-sm">
        <input checked={Boolean(value)} onChange={(event) => onChange(event.currentTarget.checked)} type="checkbox" />
        <span>{field.label}{field.required ? " *" : ""}</span>
      </label>
    );
  }
  if (field.type === "select" || field.type === "radio") {
    return (
      <label className="space-y-2 text-sm font-medium text-slate-800">
        <span>{field.label}{field.required ? " *" : ""}</span>
        <Select value={String(value ?? "")} onChange={(event) => onChange(event.currentTarget.value)}>
          <option value="">Не выбрано</option>
          {field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </Select>
      </label>
    );
  }
  return (
    <label className="space-y-2 text-sm font-medium text-slate-800">
      <span>{field.label}{field.required ? " *" : ""}</span>
      <input className="field-base h-11 w-full px-4 text-sm" placeholder={field.placeholder ?? ""} value={String(value ?? "")} onChange={(event) => onChange(event.currentTarget.value)} />
    </label>
  );
}

function AdvancedCollapsedNotice() {
  return (
    <details className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-3 text-sm text-slate-600">
      <summary className="flex cursor-pointer items-center justify-between font-semibold text-slate-900">
        Расширенные настройки JSON
        <ChevronDown className="h-4 w-4" />
      </summary>
      <p className="mt-2">Raw JSON скрыт в базовом режиме. Переключите «Экспертный», чтобы видеть низкоуровневые refs, scope и raw policy config.</p>
    </details>
  );
}

function AdvancedJsonPanel({ form }: { form: AdminFormsFormItem }) {
  return (
    <details open className="rounded-[1rem] border border-border bg-slate-950 px-4 py-4 text-slate-100">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
        <Braces className="h-4 w-4" />
        Advanced JSON / RAW
      </summary>
      <div className="mt-4 grid gap-3">
        {POLICY_JSON_FIELDS.map(([key, label]) => (
          <div key={key}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <pre className="max-h-52 overflow-auto rounded-[0.8rem] bg-black/30 p-3 text-xs">
              {JSON.stringify(form[key] ?? {}, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </details>
  );
}

function ObjectList({ title, items, selectedKey, onSelect }: { title: string; items: Array<{ key: string; title: string; subtitle: string }>; selectedKey: string | null; onSelect: (key: string) => void }) {
  return (
    <Card className="xl:sticky xl:top-24 xl:self-start">
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {items.map((item) => (
          <button className={cn("w-full rounded-[0.9rem] border px-3 py-3 text-left", selectedKey === item.key ? "border-brand-200 bg-brand-50" : "border-border bg-white")} key={item.key} onClick={() => onSelect(item.key)} type="button">
            <p className="font-semibold text-slate-950">{item.title}</p>
            <p className="mt-1 text-xs text-slate-500">{item.subtitle}</p>
          </button>
        ))}
        {!items.length ? <EmptyState text="Список пуст." /> : null}
      </CardContent>
    </Card>
  );
}

function ConditionBuilderPreview({ policy }: { policy: AdminHelpdeskPolicyItem | null }) {
  const config = policy?.config ?? {};
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <TextField label="Поле запроса" value={String(config.field ?? "category")} onChange={() => undefined} />
        <TextField label="Оператор" value={String(config.operator ?? "equals")} onChange={() => undefined} />
        <TextField label="Значение" value={String(config.value ?? policy?.code ?? "")} onChange={() => undefined} />
        <TextField label="Действие" value={String(config.target_queue ?? "servicedesk_l1")} onChange={() => undefined} />
      </div>
      <Button size="sm" variant="outline" leadingIcon={<Plus className="h-4 w-4" />}>Добавить условие</Button>
    </div>
  );
}

function SmartViewEditor({
  isPreviewPending,
  isPublishPending,
  onPreview,
  onPublish,
  onSave,
  preview,
  view,
}: {
  isPreviewPending: boolean;
  isPublishPending: boolean;
  onPreview: () => void;
  onPublish: () => void;
  onSave: () => void;
  preview: SupportQueuePayload | undefined;
  view: AdminHelpdeskSmartViewItem | null;
}) {
  const previewRows = preview?.tickets.slice(0, 5) ?? [];
  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm text-slate-500">Конструктор форм / Smart views</p>
            <CardTitle>{view?.title ?? "Smart view не выбран"}</CardTitle>
            <CardDescription>{view?.description ?? "Сохранённый рабочий срез для контроля сроков, рисков и диагностики."}</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button disabled={!view || isPreviewPending} onClick={onPreview} size="sm" variant="outline">
              {isPreviewPending ? "Загружаем..." : "Предпросмотр"}
            </Button>
            <Button disabled={!view} onClick={onSave} size="sm" variant="outline">Сохранить</Button>
            <Button disabled={!view || isPublishPending} onClick={onPublish} size="sm">
              {isPublishPending ? "Публикуем..." : "Опубликовать smart view"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <SectionTitle title="Фильтры" description="JSON не является основным интерфейсом в базовом режиме." />
        <div className="space-y-2 rounded-[1rem] bg-surface-subtle p-4 text-sm text-slate-700">
          <p>Статус не равен Closed, Cancelled</p>
          <p>Срок до ≤ 2 часа</p>
          <p>Поля сроков включает first_response_due_at, resolution_due_at</p>
        </div>
        <div className="overflow-x-auto rounded-[1rem] border border-border">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-subtle text-xs uppercase tracking-[0.14em] text-slate-400">
              <tr><th className="px-4 py-3">ID</th><th className="px-4 py-3">Название</th><th className="px-4 py-3">Статус</th><th className="px-4 py-3">Исполнитель</th><th className="px-4 py-3">Срок до</th><th className="px-4 py-3">Срок решения</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {previewRows.length > 0 ? previewRows.map((ticket) => (
                <tr key={ticket.ticket_id}>
                  <td className="px-4 py-3 font-semibold">{ticket.ticket_code ?? ticket.ticket_id}</td>
                  <td className="px-4 py-3">{ticket.title}</td>
                  <td className="px-4 py-3"><Badge tone="success">{ticket.status_label || ticket.status}</Badge></td>
                  <td className="px-4 py-3">{ticket.assignee_display_name ?? ticket.queue_code ?? "Не назначен"}</td>
                  <td className="px-4 py-3 text-rose-600">{ticket.next_action_due_at ? formatDate(ticket.next_action_due_at) : "нет срока"}</td>
                  <td className="px-4 py-3">{ticket.priority_class ?? ticket.priority ?? "—"}</td>
                </tr>
              )) : (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                    {preview ? "По текущему smart view заявок не найдено." : "Нажмите «Предпросмотр», чтобы загрузить реальные результаты из API."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {preview ? (
          <p className="text-sm text-slate-500">Показано {previewRows.length} из {preview.summary.visible_count} заявок.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function VersionDetails({
  compareSummary,
  isComparing,
  isOpening,
  onCompare,
  onOpenEditor,
  version,
}: {
  compareSummary: VersionCompareSummary | null;
  isComparing: boolean;
  isOpening: boolean;
  onCompare: () => void;
  onOpenEditor: () => void;
  version: TicketFormsPackSummary | null;
}) {
  const summaryCards = compareSummary
    ? [
        ["Добавлено", String(compareSummary.added)],
        ["Изменено", String(compareSummary.changed)],
        ["Удалено", String(compareSummary.removed)],
        ["Без изменений", String(compareSummary.unchanged)],
      ]
    : [
        ["Добавлено", "—"],
        ["Изменено", "—"],
        ["Удалено", "—"],
        ["Без изменений", "—"],
      ];
  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm text-slate-500">Выбрана версия</p>
            <CardTitle>{version?.version ?? "нет версии"}</CardTitle>
            <CardDescription>{version?.title ?? "Каталог заявок"}</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!version || isOpening} onClick={onOpenEditor} size="sm" variant="outline">
              {isOpening ? "Открываем..." : "Открыть в редакторе"}
            </Button>
            <Button disabled={!version || isComparing} onClick={onCompare} size="sm" variant="outline">
              {isComparing ? "Сравниваем..." : "Сравнить"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-4">
          {summaryCards.map(([label, value]) => (
            <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={label}>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
            </div>
          ))}
        </div>
        <div className="space-y-3 text-sm text-slate-600">
          {compareSummary ? (
            <>
              <p>Сравнение версий: {compareSummary.fromVersion} → {compareSummary.toVersion}.</p>
              <p>Изменения в шаблонах: добавлено {compareSummary.added}, изменено {compareSummary.changed}, удалено {compareSummary.removed}.</p>
              <p>Проверка совместимости: для публикации всё равно требуется preflight-проверка каталога.</p>
            </>
          ) : (
            <>
              <p>Нажмите «Сравнить», чтобы загрузить выбранную версию и сравнить её с текущей.</p>
              <p>Данные берутся из version history request_forms, без изменения backend-состояния.</p>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ProcessResult({ result }: { result: AdminFormsProcessPreviewResult | undefined }) {
  const rows = [
    ["Тип тикета", result?.ticket_type ?? "—"],
    ["Приоритет", String(result?.priority.priority_class ?? "—")],
    ["Очередь", String(result?.routing.target_queue_name ?? result?.routing.target_queue_id ?? "—")],
    ["SLA", String(result?.sla.policy_code ?? result?.sla.policy_ref ?? "—")],
    ["OLA", String(result?.ola.policy_code ?? result?.ola.policy_ref ?? "—")],
    ["Диагностика", Array.isArray(result?.diagnostics.suggested_playbooks) ? result?.diagnostics.suggested_playbooks.join(", ") || "нет" : "—"],
    ["Согласование", result?.approval.required ? "Требуется" : "Не требуется"],
    ["Закрытие", result?.closure.requires_evidence ? "Нужны evidence" : "Без evidence"],
  ];
  return (
    <Card>
      <CardHeader><CardTitle>Расчёт процесса</CardTitle><CardDescription>Полный result обработки, не только route-preview.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          {rows.map(([label, value]) => (
            <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={label}>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-2 font-semibold text-slate-950">{value}</p>
            </div>
          ))}
        </div>
        <div className="rounded-[1rem] border border-brand-100 bg-brand-50 px-4 py-4">
          <p className="font-semibold text-brand-900">Форма → Приоритет → Роутинг → SLA/OLA → Диагностика → Создание тикета</p>
        </div>
        <div className="space-y-2">
          {(result?.summary_rows ?? []).map((row) => (
            <div className="flex items-center justify-between gap-3 rounded-[0.9rem] bg-surface-subtle px-3 py-2 text-sm" key={row.key}>
              <span>{row.label}</span><strong>{row.value}</strong>
            </div>
          ))}
          {!result ? <EmptyState text="Заполните пример payload и нажмите «Проверить»." /> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function RightInfoPanel({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <Card className="xl:sticky xl:top-24 xl:self-start">
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {rows.map(([label, value]) => (
          <div className="flex items-start justify-between gap-3" key={label}>
            <span className="text-slate-500">{label}</span>
            <strong className="max-w-[160px] text-right text-slate-900">{value}</strong>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
