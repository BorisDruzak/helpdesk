import type {
  AdminFormsDraftSaveRequest,
  AdminFormsFieldType,
  AdminFormsFormItem,
  AdminHelpdeskModelPayload,
} from "../forms-builder/api";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import type { RequestStudioItem } from "./studio-model";

export type StudioDraftField = {
  key: string;
  label: string;
  type: AdminFormsFieldType;
  required: boolean;
  placeholder: string;
  helpText: string;
  optionsText: string;
  visibleWhenField: string;
  visibleWhenValue: string;
  processMeaning: string;
};

export type StudioDraft = {
  serviceCode: string;
  offeringCode: string;
  templateCode: string;
  title: string;
  description: string;
  visibility: "public" | "internal" | "restricted";
  processProfile: string;
  routingPolicyCode: string;
  slaPolicyCode: string;
  approvalMode: "none" | "required";
  approvalPolicyCode: string;
  closurePolicyCode: string;
  notificationPolicyCode: string;
  fields: StudioDraftField[];
};

export type AutoFixSuggestion = {
  key: keyof Pick<
    StudioDraft,
    "routingPolicyCode" | "slaPolicyCode" | "closurePolicyCode" | "notificationPolicyCode" | "visibility"
  >;
  label: string;
  value: string;
  description: string;
  available: boolean;
};

export const PROCESS_PROFILES = [
  "Простая заявка",
  "Инцидент",
  "Срочный инцидент",
  "Заявка на доступ",
  "Установка ПО",
  "Консультация",
  "Пользовательский профиль",
] as const;

export const PROCESS_MEANINGS = [
  { value: "display_only", label: "Только отображать" },
  { value: "priority_impact", label: "Влияет на приоритет" },
  { value: "routing_input", label: "Влияет на маршрут" },
  { value: "diagnostic_input", label: "Входные данные диагностики" },
  { value: "closure_evidence", label: "Факт для закрытия/паспорта" },
];

export function buildInitialStudioDraft(item: RequestStudioItem | null): StudioDraft | null {
  if (!item) {
    return null;
  }
  const template = item.template;
  return {
    serviceCode: item.service.code,
    offeringCode: item.offering?.code ?? "",
    templateCode: template?.template_code ?? item.offering?.request_template_key ?? "",
    title: item.offering?.public_title ?? template?.public_title ?? item.service.public_title ?? "",
    description: item.offering?.short_description ?? template?.description ?? item.service.short_description ?? "",
    visibility: item.offering?.visibility ?? item.service.visibility ?? "public",
    processProfile: item.processProfile.profileName,
    routingPolicyCode: template?.routing_policy_code ?? item.offering?.routing_policy_code ?? item.service.default_routing_policy_code ?? "",
    slaPolicyCode: template?.sla_policy_code ?? item.offering?.sla_policy_code ?? item.service.default_sla_policy_code ?? "",
    approvalMode: template?.approval_policy_code ?? item.offering?.approval_policy_code ? "required" : "none",
    approvalPolicyCode: template?.approval_policy_code ?? item.offering?.approval_policy_code ?? "",
    closurePolicyCode: template?.closure_policy_code ?? item.offering?.closure_policy_code ?? "",
    notificationPolicyCode: template?.notification_policy_code ?? item.offering?.notification_policy_code ?? "",
    fields: (item.formPreview?.fields ?? []).map((field, index) => ({
      key: field.key || `field_${index + 1}`,
      label: field.label || field.key || `Поле ${index + 1}`,
      type: normalizeFieldType(field.type),
      required: Boolean(field.required),
      placeholder: "",
      helpText: "",
      optionsText: optionsToText(field.options),
      visibleWhenField: typeof field.visibility?.field === "string" ? field.visibility.field : "",
      visibleWhenValue: typeof field.visibility?.equals === "string" ? field.visibility.equals : "",
      processMeaning: normalizeProcessMeaning(field.processMapping),
    })),
  };
}

export function createDraftFromWizard(input: {
  processProfile: string;
  serviceCode: string;
  title: string;
  description: string;
  visibility: "public" | "internal" | "restricted";
}): StudioDraft {
  const slug = slugify(input.title || input.processProfile);
  return {
    serviceCode: input.serviceCode,
    offeringCode: slug,
    templateCode: slug,
    title: input.title,
    description: input.description,
    visibility: input.visibility,
    processProfile: input.processProfile,
    routingPolicyCode: "",
    slaPolicyCode: "",
    approvalMode: input.processProfile === "Заявка на доступ" ? "required" : "none",
    approvalPolicyCode: "",
    closurePolicyCode: "",
    notificationPolicyCode: "",
    fields: starterFields(input.processProfile),
  };
}

export function newDraftField(index: number): StudioDraftField {
  return {
    key: `field_${index + 1}`,
    label: `Новое поле ${index + 1}`,
    type: "text",
    required: false,
    placeholder: "",
    helpText: "",
    optionsText: "",
    visibleWhenField: "",
    visibleWhenValue: "",
    processMeaning: "display_only",
  };
}

export function buildAutoFixSuggestions(draft: StudioDraft, registry: AdminHelpdeskModelPayload | null | undefined): AutoFixSuggestion[] {
  const routing = firstActivePolicy(registry, "routing", ["route_l1", "default", "service"]);
  const sla = firstActivePolicy(registry, "sla", ["business", "default", "p2"]);
  const closure = firstActivePolicy(registry, "closure", ["basic", "default"]);
  const notification = firstActivePolicy(registry, "notification", ["standard", "default"]);
  return [
    {
      key: "routingPolicyCode",
      label: "Маршрут не выбран",
      value: draft.routingPolicyCode || routing?.code || "",
      description: routing ? `Применить маршрут: ${routing.title || routing.code}` : "Не найдено безопасное правило маршрута.",
      available: !draft.routingPolicyCode && Boolean(routing),
    },
    {
      key: "slaPolicyCode",
      label: "Срок выполнения не выбран",
      value: draft.slaPolicyCode || sla?.code || "",
      description: sla ? `Применить срок: ${sla.title || sla.code}` : "Не найдена безопасная SLA policy.",
      available: !draft.slaPolicyCode && Boolean(sla),
    },
    {
      key: "closurePolicyCode",
      label: "Закрытие не настроено",
      value: draft.closurePolicyCode || closure?.code || "",
      description: closure ? `Применить закрытие: ${closure.title || closure.code}` : "Не найдены безопасные правила закрытия.",
      available: !draft.closurePolicyCode && Boolean(closure),
    },
    {
      key: "notificationPolicyCode",
      label: "Уведомления не выбраны",
      value: draft.notificationPolicyCode || notification?.code || "__unused__",
      description: notification ? `Применить уведомления: ${notification.title || notification.code}` : "Оставить как не используется.",
      available: !draft.notificationPolicyCode,
    },
  ];
}

export function applyProfileDefaults(draft: StudioDraft, registry: AdminHelpdeskModelPayload | null | undefined): StudioDraft {
  const suggestions = buildAutoFixSuggestions(draft, registry).filter((item) => item.available);
  return suggestions.reduce((current, suggestion) => applyAutoFix(current, suggestion), draft);
}

export function applyAutoFix(draft: StudioDraft, suggestion: AutoFixSuggestion): StudioDraft {
  if (!suggestion.available) {
    return draft;
  }
  if (suggestion.key === "notificationPolicyCode" && suggestion.value === "__unused__") {
    return { ...draft, notificationPolicyCode: "" };
  }
  return { ...draft, [suggestion.key]: suggestion.value };
}

export function buildFormsDraftPayload(args: {
  draft: StudioDraft;
  currentForms: AdminFormsFormItem[];
  baseVersion?: string | null;
}): AdminFormsDraftSaveRequest {
  const nextForm = draftToForm(args.draft);
  const forms = args.currentForms.filter((form) => form.key !== nextForm.key).map(formsItemToSaveForm);
  return {
    title: "Каталог заявок",
    description: "Черновик из Студии обращений",
    base_version: args.baseVersion ?? null,
    forms: [nextForm, ...forms],
  };
}

export function buildOfferingDraftPayload(draft: StudioDraft, currentOffering: AdminServiceCatalogOffering | null | undefined) {
  const code = draft.offeringCode || draft.templateCode;
  return {
    ...currentOffering,
    service_code: draft.serviceCode,
    code,
    full_code: currentOffering?.full_code ?? `${draft.serviceCode}.${code}`,
    public_title: draft.title,
    short_description: draft.description,
    lifecycle_status: currentOffering?.lifecycle_status ?? "draft",
    visibility: draft.visibility,
    request_template_key: draft.templateCode,
    routing_policy_code: emptyToNull(draft.routingPolicyCode),
    sla_policy_code: emptyToNull(draft.slaPolicyCode),
    approval_policy_code: draft.approvalMode === "required" ? emptyToNull(draft.approvalPolicyCode) : null,
    closure_policy_code: emptyToNull(draft.closurePolicyCode),
    notification_policy_code: emptyToNull(draft.notificationPolicyCode),
  };
}

export function isDraftReadyForValidation(draft: StudioDraft | null) {
  return Boolean(draft?.templateCode && draft.fields.length && draft.routingPolicyCode && draft.slaPolicyCode && draft.closurePolicyCode);
}

function draftToForm(draft: StudioDraft): AdminFormsDraftSaveRequest["forms"][number] {
  return {
    key: draft.templateCode || draft.offeringCode,
    request_kind: draft.templateCode || draft.offeringCode,
    ticket_type: ticketTypeForProfile(draft.processProfile),
    title: draft.title,
    description: draft.description,
    routing_policy_ref: emptyToNull(draft.routingPolicyCode),
    sla_policy_ref: emptyToNull(draft.slaPolicyCode),
    approval_policy_ref: draft.approvalMode === "required" ? emptyToNull(draft.approvalPolicyCode) : null,
    closure_policy_ref: emptyToNull(draft.closurePolicyCode),
    visibility_policy_ref: draft.visibility === "public" ? "visibility_default" : null,
    notification_policy_ref: emptyToNull(draft.notificationPolicyCode),
    fields: draft.fields.map((field) => ({
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      placeholder: field.placeholder,
      help_text: field.helpText,
      options: textToOptions(field.optionsText),
      process_mapping: {
        roles: field.processMeaning === "display_only" ? ["display_only"] : [field.processMeaning],
      },
      visible_when: field.visibleWhenField
        ? {
            field: field.visibleWhenField,
            equals: field.visibleWhenValue || undefined,
            values: field.visibleWhenValue ? [field.visibleWhenValue] : undefined,
          }
        : undefined,
    })),
  };
}

function formsItemToSaveForm(form: AdminFormsFormItem): AdminFormsDraftSaveRequest["forms"][number] {
  return {
    ...form,
    description: form.description ?? "",
    fields: form.fields.map((field) => ({
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      placeholder: field.placeholder ?? "",
      help_text: field.help_text ?? "",
      options: field.options ?? [],
      validation: field.validation,
      process_mapping: field.process_mapping,
      visible_when: normalizeVisibleWhen(field.visible_when),
    })),
  };
}

function normalizeVisibleWhen(visibleWhen: AdminFormsFormItem["fields"][number]["visible_when"]) {
  if (!visibleWhen?.field) {
    return undefined;
  }
  return {
    field: visibleWhen.field,
    equals: visibleWhen.equals ?? undefined,
    values: visibleWhen.values ?? undefined,
  };
}

function firstActivePolicy(registry: AdminHelpdeskModelPayload | null | undefined, kind: string, preferredCodes: string[]) {
  const policies = (registry?.policies?.[kind] ?? []).filter((policy) => policy.is_active);
  return (
    preferredCodes.flatMap((part) => policies.filter((policy) => policy.code.toLowerCase().includes(part))).at(0) ??
    policies[0] ??
    null
  );
}

function starterFields(profile: string): StudioDraftField[] {
  if (profile === "Заявка на доступ") {
    return [
      { key: "system", label: "В какую систему?", type: "text", required: true, placeholder: "CRM, 1C, VPN", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "routing_input" },
      { key: "role", label: "Какая роль?", type: "text", required: false, placeholder: "Читатель, редактор", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "display_only" },
      { key: "reason", label: "Зачем нужен доступ?", type: "textarea", required: true, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "approval_subject" },
      { key: "until_date", label: "До какой даты?", type: "date", required: false, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "display_only" },
      { key: "approver", label: "Кто согласует?", type: "user_picker", required: false, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "approval_subject" },
    ];
  }
  if (profile === "Инцидент" || profile === "Срочный инцидент") {
    return [
      { key: "what_happened", label: "Что случилось?", type: "textarea", required: true, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "diagnostic_input" },
      { key: "affected_scope", label: "Кого затронула проблема?", type: "select", required: true, placeholder: "", helpText: "", optionsText: "me=Только меня\nteam=Команду\ncompany=Всех", visibleWhenField: "", visibleWhenValue: "", processMeaning: "priority_impact" },
      { key: "can_work", label: "Можно ли продолжать работу?", type: "checkbox", required: true, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "priority_impact" },
    ];
  }
  if (profile === "Установка ПО") {
    return [
      { key: "software", label: "Какое ПО?", type: "text", required: true, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "routing_input" },
      { key: "target_user", label: "Для кого?", type: "user_picker", required: false, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "display_only" },
      { key: "reason", label: "Обоснование", type: "textarea", required: false, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "approval_subject" },
    ];
  }
  return [
    { key: "summary", label: "Что нужно сделать?", type: "textarea", required: true, placeholder: "", helpText: "", optionsText: "", visibleWhenField: "", visibleWhenValue: "", processMeaning: "display_only" },
  ];
}

function normalizeFieldType(value: string): AdminFormsFieldType {
  const allowed: AdminFormsFieldType[] = ["text", "textarea", "select", "multi_select", "radio", "checkbox", "date", "datetime", "file", "user_picker", "department_picker", "location_picker", "device_picker", "service_picker", "url", "phone", "email"];
  return allowed.includes(value as AdminFormsFieldType) ? (value as AdminFormsFieldType) : "text";
}

function normalizeProcessMeaning(mapping: Record<string, unknown> | undefined) {
  const roles = Array.isArray(mapping?.roles) ? mapping.roles : typeof mapping?.role === "string" ? [mapping.role] : [];
  const found = roles.find((role) => PROCESS_MEANINGS.some((item) => item.value === role));
  return typeof found === "string" ? found : "display_only";
}

function optionsToText(options: Array<Record<string, unknown>> | undefined) {
  return (options ?? [])
    .map((option) => `${String(option.value ?? "")}=${String(option.label ?? option.value ?? "")}`)
    .join("\n");
}

function textToOptions(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [rawValue, ...labelParts] = line.split("=");
      const optionValue = rawValue.trim();
      return { value: optionValue, label: (labelParts.join("=").trim() || optionValue) };
    });
}

function slugify(value: string) {
  const ascii = value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[\s_-]+/g, "_");
  return ascii || `request_${Date.now()}`;
}

function ticketTypeForProfile(profile: string) {
  if (profile.includes("Инцидент")) {
    return "incident";
  }
  if (profile === "Заявка на доступ") {
    return "access_request";
  }
  return "service_request";
}

function emptyToNull(value: string | null | undefined) {
  return value && value !== "__unused__" ? value : null;
}
