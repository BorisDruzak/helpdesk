import type { AdminHelpdeskModelPayload } from "../forms-builder/api";
import type { AdminServiceCatalogOffering, AdminServiceCatalogService } from "../service-catalog/api";

export type PickerOption = {
  value: string;
  label: string;
  subtitle?: string;
  status?: string;
  disabled?: boolean;
  disabledReason?: string | null;
};

export const POLICY_KIND_LABELS: Record<string, string> = {
  priority: "Приоритет",
  routing: "Маршрутизация",
  sla: "SLA",
  ola: "OLA, внутренний срок",
  approval: "Согласование",
  closure: "Закрытие",
  visibility: "Видимость",
  diagnostic: "Диагностика",
  notification: "Уведомления",
  reporting: "Отчётность",
};

export function optionLabelWithCode(label: string, code: string): string {
  return label && label !== code ? `${label} (${code})` : code;
}

export function serviceOptions(services: AdminServiceCatalogService[]): PickerOption[] {
  return services.map((service) => ({
    value: service.code,
    label: optionLabelWithCode(service.public_title || service.name || service.code, service.code),
    subtitle: [service.short_description, service.visibility, service.owner_queue_id ? `Очередь ${service.owner_queue_id}` : null]
      .filter(Boolean)
      .join(" · "),
    status: service.lifecycle_status,
    disabled: service.lifecycle_status === "retired",
    disabledReason: service.lifecycle_status === "retired" ? "Услуга выведена из каталога" : null,
  }));
}

export function offeringOptions(
  offerings: AdminServiceCatalogOffering[],
  serviceCode?: string | null,
): PickerOption[] {
  return offerings
    .filter((offering) => !serviceCode || offering.service_code === serviceCode)
    .map((offering) => ({
      value: offering.full_code || offering.code,
      label: optionLabelWithCode(offering.public_title || offering.full_code || offering.code, offering.full_code || offering.code),
      subtitle: [offering.request_template_key ? `Шаблон ${offering.request_template_key}` : "Шаблон не привязан", offering.visibility]
        .filter(Boolean)
        .join(" · "),
      status: offering.lifecycle_status,
      disabled: offering.lifecycle_status === "retired",
      disabledReason: offering.lifecycle_status === "retired" ? "Вариант услуги выведен из каталога" : null,
    }));
}

export function requestTemplateOptions(registry?: AdminHelpdeskModelPayload | null): PickerOption[] {
  return (registry?.request_templates ?? []).map((template) => ({
    value: template.template_code,
    label: optionLabelWithCode(template.public_title || template.internal_name || template.template_code, template.template_code),
    subtitle: [template.ticket_type, template.version, template.is_active ? "активен" : "неактивен"].filter(Boolean).join(" · "),
    status: template.is_active ? "active" : "inactive",
    disabled: !template.is_active,
    disabledReason: template.is_active ? null : "Шаблон не активен",
  }));
}

export function policyOptions(
  registry: AdminHelpdeskModelPayload | null | undefined,
  kind: string,
): PickerOption[] {
  return (registry?.policies?.[kind] ?? []).map((policy) => ({
    value: policy.code,
    label: optionLabelWithCode(policy.title || policy.code, policy.code),
    subtitle: [POLICY_KIND_LABELS[kind] ?? kind, policy.version, policy.scope_level, policy.scope_ref].filter(Boolean).join(" · "),
    status: policy.is_active ? "active" : "inactive",
    disabled: !policy.is_active,
    disabledReason: policy.is_active ? null : "Политика не активна",
  }));
}

export type GuidedSimulationDraft = {
  requester: string;
  device: string;
  location: string;
  serviceCode: string;
  offeringCode: string;
  answerSummary: string;
  expectedPriority: string;
  expectedRouting: string;
  expectedSla: string;
  expectedApprovals: string;
  expectedDiagnostics: string;
  expectedClosure: string;
};

export const defaultGuidedSimulationDraft: GuidedSimulationDraft = {
  requester: "",
  device: "",
  location: "",
  serviceCode: "",
  offeringCode: "",
  answerSummary: "",
  expectedPriority: "",
  expectedRouting: "",
  expectedSla: "",
  expectedApprovals: "",
  expectedDiagnostics: "",
  expectedClosure: "",
};

export function buildGuidedSimulationPayload(draft: GuidedSimulationDraft): {
  request_form_data: Record<string, unknown>;
  custom_fields: Record<string, unknown>;
  device_metadata: Record<string, unknown>;
  requester_context: Record<string, unknown>;
} {
  return {
    request_form_data: {
      summary: draft.answerSummary,
      expected_priority: draft.expectedPriority,
      expected_routing: draft.expectedRouting,
      expected_sla: draft.expectedSla,
      expected_approvals: draft.expectedApprovals,
      expected_diagnostics: draft.expectedDiagnostics,
      expected_closure: draft.expectedClosure,
    },
    custom_fields: {
      service_code: draft.serviceCode || undefined,
      offering_code: draft.offeringCode || undefined,
    },
    device_metadata: {
      device_id: draft.device || undefined,
    },
    requester_context: {
      requester_id: draft.requester || undefined,
      location: draft.location || undefined,
    },
  };
}
