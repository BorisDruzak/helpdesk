export type CatalogLifecycle = "draft" | "published" | "retired";
export type CatalogVisibility = "public" | "internal" | "restricted";

export type AdminServiceCatalogService = {
  service_id?: string;
  code: string;
  name?: string | null;
  public_title: string;
  short_description?: string | null;
  description?: string | null;
  lifecycle_status: CatalogLifecycle;
  visibility: CatalogVisibility;
  owner_queue_id?: number | null;
  default_queue_id?: number | null;
  default_sla_policy_code?: string | null;
  default_routing_policy_code?: string | null;
  default_diagnostic_policy_code?: string | null;
  business_criticality?: string | null;
  reporting_category?: string | null;
};

export type AdminServiceCatalogOffering = {
  offering_id?: string;
  service_id?: string;
  service_code?: string | null;
  code: string;
  full_code: string;
  public_title: string;
  short_description?: string | null;
  lifecycle_status: CatalogLifecycle;
  visibility: CatalogVisibility;
  request_type?: string | null;
  request_template_key?: string | null;
  routing_policy_code?: string | null;
  sla_policy_code?: string | null;
  ola_policy_code?: string | null;
  approval_policy_code?: string | null;
  closure_policy_code?: string | null;
  visibility_policy_code?: string | null;
  diagnostic_policy_code?: string | null;
  notification_policy_code?: string | null;
  reporting_policy_code?: string | null;
  reporting_category?: string | null;
};

export type PublicationIssue = {
  severity: "critical" | "error" | "warning" | "info";
  kind: string;
  object_type: string;
  object_code: string;
  path: string;
  message: string;
  suggested_fix?: string | null;
};

export type PublicationValidation = {
  status: "ok" | "warning" | "error";
  issues: PublicationIssue[];
  blocking: boolean;
};

export type ServiceCatalogDashboard = {
  status: "ok";
  services: AdminServiceCatalogService[];
  offerings: AdminServiceCatalogOffering[];
};

export type ServiceCatalogSimulation = {
  template_code?: string;
  service_catalog?: Record<string, unknown> | null;
  routing?: Record<string, unknown>;
  priority?: Record<string, unknown>;
  sla?: Record<string, unknown>;
  ola?: Record<string, unknown>;
  approval?: Record<string, unknown>;
  closure?: Record<string, unknown>;
  visibility?: Record<string, unknown>;
  diagnostic?: Record<string, unknown>;
  warnings?: string[];
  would_create_ticket: false;
};

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.details ?? payload?.error ?? fallbackMessage);
  }
  return payload as T;
}

export async function fetchServiceCatalogDashboard(): Promise<ServiceCatalogDashboard> {
  const response = await fetch("/api/web/admin/service-catalog", {
    credentials: "same-origin",
  });
  return readJson(response, "Не удалось загрузить Service Catalog");
}

export async function saveServiceDraft(payload: Partial<AdminServiceCatalogService> & { code: string }) {
  const response = await fetch("/api/web/admin/service-catalog/services/save-draft", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ status: "ok"; service: AdminServiceCatalogService }>(response, "Не удалось сохранить услугу");
}

export async function saveOfferingDraft(payload: Partial<AdminServiceCatalogOffering> & { service_code: string; code: string }) {
  const response = await fetch("/api/web/admin/service-catalog/offerings/save-draft", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ status: "ok"; offering: AdminServiceCatalogOffering }>(response, "Не удалось сохранить offering");
}

export async function publishServiceCatalogObject(kind: "service" | "offering", code: string) {
  const url =
    kind === "service"
      ? `/api/web/admin/service-catalog/services/${encodeURIComponent(code)}/publish`
      : `/api/web/admin/service-catalog/offerings/${encodeURIComponent(code)}/publish`;
  const response = await fetch(url, { method: "POST", credentials: "same-origin" });
  return readJson<unknown>(response, "Не удалось опубликовать объект");
}

export async function retireServiceCatalogObject(kind: "service" | "offering", code: string) {
  const url =
    kind === "service"
      ? `/api/web/admin/service-catalog/services/${encodeURIComponent(code)}/retire`
      : `/api/web/admin/service-catalog/offerings/${encodeURIComponent(code)}/retire`;
  const response = await fetch(url, { method: "POST", credentials: "same-origin" });
  return readJson<unknown>(response, "Не удалось retired объект");
}

export async function validateServiceCatalogObject(
  kind: "service" | "offering",
  code: string,
): Promise<PublicationValidation> {
  const url =
    kind === "service"
      ? `/api/web/admin/service-catalog/services/${encodeURIComponent(code)}/validate`
      : `/api/web/admin/service-catalog/offerings/${encodeURIComponent(code)}/validate`;
  const response = await fetch(url, { method: "POST", credentials: "same-origin" });
  const payload = await readJson<{ validation: PublicationValidation }>(response, "Не удалось проверить публикацию");
  return payload.validation;
}

export async function simulateServiceCatalog(payload: {
  service_code?: string | null;
  offering_code?: string | null;
  offering_full_code?: string | null;
  request_form_data: Record<string, unknown>;
  custom_fields?: Record<string, unknown>;
  device_metadata?: Record<string, unknown>;
  requester_context?: Record<string, unknown>;
}): Promise<ServiceCatalogSimulation> {
  const response = await fetch("/api/web/admin/service-catalog/simulate", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson(response, "Не удалось выполнить simulation");
}
