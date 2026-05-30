import type {
  AdminFormsFieldItem,
  AdminFormsFormItem,
  AdminHelpdeskFormSchemaItem,
  AdminHelpdeskModelPayload,
  AdminHelpdeskRequestTemplateItem,
} from "../forms-builder/api";
import type { PolicyHealthDashboard, PolicyHealthIssue, PolicyHealthTemplate } from "../policy-health/api";
import type { AdminServiceCatalogOffering, AdminServiceCatalogService } from "../service-catalog/api";

export type StudioStatus = "ready" | "needs_setup" | "recommended" | "unused" | "error";
export type RequestStudioMode = "basic" | "advanced" | "expert";
export type ProcessBlockKey =
  | "identity"
  | "form"
  | "processing"
  | "routing"
  | "sla"
  | "approval"
  | "execution"
  | "closure"
  | "notifications"
  | "validation"
  | "publication";

export type StudioLinks = {
  forms: string;
  serviceCatalog: string;
  policyHealth: string;
};

export type FormPreviewModel = {
  title: string;
  description: string | null;
  source: "registry" | "forms-builder";
  fields: Array<{
    key: string;
    label: string;
    type: string;
    required: boolean;
    options?: Array<Record<string, unknown>>;
    visibility?: Record<string, unknown> | null;
    visibleWhen?: AdminFormsFieldItem["visible_when"];
    processMapping?: Record<string, unknown>;
  }>;
};

export type ProcessBlock = {
  key: ProcessBlockKey;
  title: string;
  status: StudioStatus;
  explanation: string;
  actionLabel: string;
};

export type PolicySummary = {
  profileName: string;
  requiredMissing: string[];
  recommendedMissing: string[];
  readyLabels: string[];
  issueLabels: string[];
};

export type RequestStudioItem = {
  id: string;
  group: string;
  service: AdminServiceCatalogService;
  offering: AdminServiceCatalogOffering | null;
  template: AdminHelpdeskRequestTemplateItem | null;
  health: PolicyHealthTemplate | null;
  formPreview: FormPreviewModel | null;
  processProfile: PolicySummary;
  processBlocks: ProcessBlock[];
  readinessStatus: "ok" | "warning" | "error";
  isTechnical: boolean;
  technicalRefs: {
    serviceCode: string;
    offeringCode: string | null;
    templateCode: string | null;
  };
};

const REQUIRED_POLICIES: Array<[keyof AdminHelpdeskRequestTemplateItem, string]> = [
  ["routing_policy_code", "маршрут"],
  ["sla_policy_code", "срок выполнения"],
  ["closure_policy_code", "правила закрытия"],
  ["visibility_policy_code", "видимость"],
];

const RECOMMENDED_POLICIES: Array<[keyof AdminHelpdeskRequestTemplateItem, string]> = [
  ["approval_policy_code", "согласование"],
  ["diagnostic_policy_code", "диагностика"],
  ["notification_policy_code", "уведомления"],
  ["reporting_policy_code", "отчётность"],
];

export function getRequestStudioModeLabel(mode: RequestStudioMode) {
  if (mode === "advanced") {
    return "Расширенный";
  }
  if (mode === "expert") {
    return "Экспертный";
  }
  return "Базовый";
}

export function statusLabel(status: StudioStatus) {
  const labels: Record<StudioStatus, string> = {
    ready: "Готово",
    needs_setup: "Нужно настроить",
    recommended: "Рекомендуется",
    unused: "Не используется",
    error: "Ошибка",
  };
  return labels[status];
}

export function statusTone(status: StudioStatus | string | null | undefined) {
  if (status === "ready" || status === "ok" || status === "published" || status === "active") {
    return "success" as const;
  }
  if (status === "recommended" || status === "warning" || status === "draft" || status === "needs_setup") {
    return "warning" as const;
  }
  if (status === "error" || status === "critical" || status === "retired" || status === "inactive") {
    return "danger" as const;
  }
  return "neutral" as const;
}

export function tech(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "не задано" : String(value);
}

export function buildDeepLink(base: string, item: RequestStudioItem | null | undefined) {
  const search = new URLSearchParams();
  if (item?.service.code) {
    search.set("service", item.service.code);
  }
  if (item?.offering?.full_code) {
    search.set("offering", item.offering.full_code);
  }
  if (item?.template?.template_code) {
    search.set("template", item.template.template_code);
  }
  const suffix = search.toString();
  return `${base}${suffix ? `?${suffix}` : ""}`;
}

export function buildRequestStudioItems({
  services,
  offerings,
  registry,
  forms,
  health,
}: {
  services: AdminServiceCatalogService[];
  offerings: AdminServiceCatalogOffering[];
  registry: AdminHelpdeskModelPayload | null | undefined;
  forms: AdminFormsFormItem[];
  health: PolicyHealthDashboard | null | undefined;
}): RequestStudioItem[] {
  const items: RequestStudioItem[] = [];
  for (const service of services) {
    const serviceOfferings = offerings.filter((offering) => offering.service_code === service.code);
    if (!serviceOfferings.length) {
      items.push(buildItem(service, null, registry, forms, health));
      continue;
    }
    for (const offering of serviceOfferings) {
      items.push(buildItem(service, offering, registry, forms, health));
    }
  }
  return items.sort((left, right) => {
    if (left.isTechnical !== right.isTechnical) {
      return left.isTechnical ? 1 : -1;
    }
    return `${left.group}:${left.offering?.public_title ?? left.service.public_title}`.localeCompare(
      `${right.group}:${right.offering?.public_title ?? right.service.public_title}`,
      "ru",
    );
  });
}

export function findStudioItem(
  items: RequestStudioItem[],
  params: { service?: string | null; offering?: string | null; template?: string | null },
) {
  if (!params.service && !params.offering && !params.template) {
    return null;
  }
  return (
    items.find((item) => params.offering && (item.offering?.full_code === params.offering || item.offering?.code === params.offering)) ??
    items.find((item) => params.template && item.template?.template_code === params.template) ??
    items.find((item) => params.service && item.service.code === params.service) ??
    null
  );
}

export function findDefaultStudioItem(items: RequestStudioItem[], showTechnicalItems: boolean) {
  return items.find((item) => !item.isTechnical && item.offering?.lifecycle_status === "published") ?? (showTechnicalItems ? items[0] ?? null : null);
}

export function hasBlockingIssue(issue: PolicyHealthIssue) {
  return issue.severity === "critical" || issue.severity === "error";
}

function buildItem(
  service: AdminServiceCatalogService,
  offering: AdminServiceCatalogOffering | null,
  registry: AdminHelpdeskModelPayload | null | undefined,
  forms: AdminFormsFormItem[],
  health: PolicyHealthDashboard | null | undefined,
): RequestStudioItem {
  const templateCode = offering?.request_template_key ?? null;
  const template = templateCode ? registry?.request_templates.find((item) => item.template_code === templateCode) ?? null : null;
  const formPreview = findFormPreview(registry, forms, template);
  const selectedHealth = template?.template_code ? health?.templates.find((item) => item.template_code === template.template_code) ?? null : null;
  const profile = buildPolicySummary(template, selectedHealth);
  const processBlocks = buildProcessBlocks({ service, offering, template, formPreview, health: selectedHealth, profile });
  const readinessStatus = processBlocks.some((block) => block.status === "error")
    ? "error"
    : processBlocks.some((block) => block.status === "needs_setup" || block.status === "recommended")
      ? "warning"
      : "ok";
  return {
    id: offering?.full_code ?? `service:${service.code}`,
    group: groupService(service),
    service,
    offering,
    template,
    health: selectedHealth,
    formPreview,
    processProfile: profile,
    processBlocks,
    readinessStatus,
    isTechnical: isTechnicalCatalogObject(service, offering),
    technicalRefs: {
      serviceCode: service.code,
      offeringCode: offering?.full_code ?? null,
      templateCode: template?.template_code ?? templateCode,
    },
  };
}

function buildPolicySummary(template: AdminHelpdeskRequestTemplateItem | null, health: PolicyHealthTemplate | null): PolicySummary {
  const requiredMissing = REQUIRED_POLICIES.filter(([key]) => !template?.[key]).map(([, label]) => label);
  const recommendedMissing = RECOMMENDED_POLICIES.filter(([key]) => !template?.[key]).map(([, label]) => label);
  const readyLabels = [
    template?.routing_policy_code ? "маршрут" : null,
    template?.sla_policy_code ? "сроки" : null,
    template?.closure_policy_code ? "закрытие" : null,
    template?.approval_policy_code ? "согласование" : null,
    template?.notification_policy_code ? "уведомления" : null,
  ].filter(Boolean) as string[];
  const issueLabels = health?.issues.filter(hasBlockingIssue).map((issue) => issue.message).slice(0, 4) ?? [];
  return {
    profileName: inferProfileName(template),
    requiredMissing,
    recommendedMissing,
    readyLabels,
    issueLabels,
  };
}

function buildProcessBlocks({
  service,
  offering,
  template,
  formPreview,
  health,
  profile,
}: {
  service: AdminServiceCatalogService;
  offering: AdminServiceCatalogOffering | null;
  template: AdminHelpdeskRequestTemplateItem | null;
  formPreview: FormPreviewModel | null;
  health: PolicyHealthTemplate | null;
  profile: PolicySummary;
}): ProcessBlock[] {
  const blockingHealth = health?.issues.some(hasBlockingIssue) ?? false;
  return [
    {
      key: "identity",
      title: "Раздел и тип обращения",
      status: offering ? "ready" : "needs_setup",
      explanation: offering
        ? `${service.public_title || service.code}: ${offering.public_title || offering.full_code}`
        : "В разделе пока не выбран рабочий тип обращения.",
      actionLabel: "Открыть блок",
    },
    {
      key: "form",
      title: "Форма пользователя",
      status: formPreview?.fields.length ? "ready" : "error",
      explanation: formPreview?.fields.length
        ? `Пользователь заполнит ${formPreview.fields.length} полей, обязательных: ${formPreview.fields.filter((field) => field.required).length}.`
        : "Форма не найдена. Без формы публикация невозможна.",
      actionLabel: "Открыть блок",
    },
    {
      key: "processing",
      title: "Правила обработки",
      status: profile.requiredMissing.length ? "needs_setup" : profile.recommendedMissing.length ? "recommended" : "ready",
      explanation: `Профиль: ${profile.profileName}. ${profile.requiredMissing.length ? `Не настроено: ${profile.requiredMissing.join(", ")}.` : "Обязательные правила есть."}`,
      actionLabel: "Открыть блок",
    },
    {
      key: "routing",
      title: "Маршрутизация",
      status: template?.routing_policy_code || offering?.routing_policy_code || service.default_routing_policy_code ? "ready" : "error",
      explanation: template?.routing_policy_code || offering?.routing_policy_code || service.default_routing_policy_code
        ? "Исполнитель будет выбран правилами маршрутизации."
        : "Не выбран маршрут. Заявка не сможет попасть в рабочую очередь.",
      actionLabel: "Открыть блок",
    },
    {
      key: "sla",
      title: "SLA / сроки",
      status: template?.sla_policy_code || offering?.sla_policy_code || service.default_sla_policy_code ? "ready" : "error",
      explanation: template?.sla_policy_code || offering?.sla_policy_code || service.default_sla_policy_code
        ? "Срок ответа и выполнения определяются политикой SLA."
        : "Срок выполнения не выбран. Без срока публикация невозможна.",
      actionLabel: "Открыть блок",
    },
    {
      key: "approval",
      title: "Согласование",
      status: template?.approval_policy_code || offering?.approval_policy_code ? "ready" : inferProfileName(template) === "Заявка на доступ" ? "recommended" : "unused",
      explanation: template?.approval_policy_code || offering?.approval_policy_code
        ? "Согласование включено в сценарий обработки."
        : inferProfileName(template) === "Заявка на доступ"
          ? "Для заявок на доступ обычно требуется согласование."
          : "Для этого типа обращения согласование не используется.",
      actionLabel: "Открыть блок",
    },
    {
      key: "execution",
      title: "Выполнение / диагностика",
      status: template?.diagnostic_policy_code || offering?.diagnostic_policy_code || service.default_diagnostic_policy_code ? "ready" : "unused",
      explanation: template?.diagnostic_policy_code || offering?.diagnostic_policy_code || service.default_diagnostic_policy_code
        ? "Диагностика или playbook подключены."
        : "Автоматическая диагностика не используется.",
      actionLabel: "Открыть блок",
    },
    {
      key: "closure",
      title: "Закрытие",
      status: template?.closure_policy_code || offering?.closure_policy_code ? "ready" : "error",
      explanation: template?.closure_policy_code || offering?.closure_policy_code
        ? "Правила закрытия определяют результат, сообщение и подтверждение."
        : "Не выбраны правила закрытия.",
      actionLabel: "Открыть блок",
    },
    {
      key: "notifications",
      title: "Уведомления",
      status: template?.notification_policy_code || offering?.notification_policy_code ? "ready" : "recommended",
      explanation: template?.notification_policy_code || offering?.notification_policy_code
        ? "Уведомления подключены."
        : "Рекомендуется включить стандартные уведомления пользователю.",
      actionLabel: "Открыть блок",
    },
    {
      key: "validation",
      title: "Проверка",
      status: blockingHealth ? "error" : health ? "ready" : "needs_setup",
      explanation: blockingHealth
        ? "Проверка готовности нашла блокирующие проблемы."
        : health
          ? "Policy Health проверил выбранный сценарий."
          : "Запустите проверку перед публикацией.",
      actionLabel: "Открыть блок",
    },
    {
      key: "publication",
      title: "Публикация",
      status: blockingHealth || !template || !offering ? "error" : "needs_setup",
      explanation: blockingHealth || !template || !offering
        ? "Публикация заблокирована до устранения проблем."
        : "Откройте экспертную публикацию для безопасного publish.",
      actionLabel: "Открыть блок",
    },
  ];
}

export function findFormPreview(
  registry: AdminHelpdeskModelPayload | null | undefined,
  forms: AdminFormsFormItem[],
  template: AdminHelpdeskRequestTemplateItem | null,
): FormPreviewModel | null {
  if (!template) {
    return null;
  }
  const schema =
    registry?.form_schemas.find((item) => item.schema_id === template.form_schema_id) ??
    registry?.form_schemas.find((item) => item.request_template_code === template.template_code) ??
    registry?.form_schemas.find((item) => item.form_key === template.template_code);
  if (schema) {
    return fromRegistrySchema(schema);
  }
  const form = forms.find((item) => item.key === template.template_code);
  return form ? fromFormsBuilder(form) : null;
}

function fromRegistrySchema(schema: AdminHelpdeskFormSchemaItem): FormPreviewModel {
  return {
    title: schema.title || schema.schema_id,
    description: schema.description,
    source: "registry",
    fields: schema.fields.map((field) => ({
      key: field.key,
      label: field.label || field.key,
      type: field.type,
      required: field.required,
      options: field.options,
      visibility: field.visibility,
      processMapping: field.process_mapping,
    })),
  };
}

function fromFormsBuilder(form: AdminFormsFormItem): FormPreviewModel {
  return {
    title: form.title || form.key,
    description: form.description,
    source: "forms-builder",
    fields: form.fields.map((field) => ({
      key: field.key,
      label: field.label || field.key,
      type: field.type_label || field.type,
      required: field.required,
      options: field.options as Array<Record<string, unknown>>,
      visibleWhen: field.visible_when,
      processMapping: field.process_mapping,
    })),
  };
}

function groupService(service: AdminServiceCatalogService) {
  const text = `${service.code} ${service.public_title} ${service.name ?? ""}`.toLowerCase();
  if (text.includes("work") || text.includes("рабоч") || text.includes("printer") || text.includes("laptop") || text.includes("software")) {
    return "Рабочее место";
  }
  if (text.includes("access") || text.includes("доступ") || text.includes("password")) {
    return "Доступы";
  }
  if (text.includes("network") || text.includes("сеть") || text.includes("vpn") || text.includes("internet")) {
    return "Сеть";
  }
  if (text.includes("mail") || text.includes("почт")) {
    return "Почта";
  }
  return "Другое";
}

function isTechnicalCatalogObject(service: AdminServiceCatalogService, offering: AdminServiceCatalogOffering | null) {
  const text = `${service.code} ${service.public_title} ${offering?.full_code ?? ""} ${offering?.public_title ?? ""}`.toLowerCase();
  return (
    service.lifecycle_status === "retired" ||
    offering?.lifecycle_status === "retired" ||
    text.includes("test") ||
    text.includes("smoke") ||
    text.includes("codex") ||
    text.includes("тест")
  );
}

function inferProfileName(template: AdminHelpdeskRequestTemplateItem | null) {
  const text = `${template?.template_code ?? ""} ${template?.public_title ?? ""} ${template?.ticket_type ?? ""}`.toLowerCase();
  if (text.includes("access") || text.includes("доступ")) {
    return "Заявка на доступ";
  }
  if (text.includes("incident") || text.includes("инцид")) {
    return "Инцидент";
  }
  if (text.includes("software") || text.includes("по") || text.includes("установ")) {
    return "Установка ПО";
  }
  if (text.includes("consult") || text.includes("консульт")) {
    return "Консультация";
  }
  return "Простая заявка";
}
