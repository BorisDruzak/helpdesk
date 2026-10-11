import type { AdminServiceCatalogOffering, AdminServiceCatalogService } from "../service-catalog/api";
import { RequestStudioApiError } from "./api";
import type { ScenarioAnswerRequest, ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import type { RequestFormField } from "../requester/types";

export type ScenarioStatus = "draft" | "published" | "errors" | "archived";
export type ScenarioCategory = {
  id: string; service_code: string; parent_id: string | null; slug: string; title: string;
  description: string; sort_order: number; visibility: "public" | "internal" | "restricted";
  effective_visibility?: string; lifecycle_status: "draft" | "published" | "archived"; revision: number;
};
export type CategoryInput = Omit<ScenarioCategory, "id" | "effective_visibility" | "revision"> & { revision?: number | null };
export type ScenarioItem = {
  id: string; scenario_key: string; service_code: string; offering_full_code: string;
  category_id: string | null; title: string; description: string; archived: boolean; enabled: boolean;
  published_version_id: string | null; status?: ScenarioStatus; revision?: number;
  issues?: { code: string; path: string; message: string }[];
};
export type ScenarioDetail = { scenario: ScenarioItem; draft: { revision: number; definition: ScenarioDraftDefinition } };
export type ScenarioCatalog = {
  categories: ScenarioCategory[]; services: AdminServiceCatalogService[]; offerings: AdminServiceCatalogOffering[];
  scenarios: ScenarioItem[]; total: number; offset: number; limit: number;
  legacy_offerings?: AdminServiceCatalogOffering[];
};
export type SimulationState = { current_block_id: string; revision: number; state: string; answers: Record<string, unknown>; history: string[]; results: Record<string, unknown> };
export type ScenarioSimulation = { revision: number; current_block: ScenarioBlock; state: SimulationState;
  current_step?: { id: string; kind: string; title: string; fields?: (RequestFormField & { value?: unknown })[];
    has_dynamic_fields?: boolean; content?: { body: string }; acknowledgment_required?: boolean; message?: string;
    answers?: { key: string; label: string; display_value: string }[] };
  processing?: { priority: { priority_class: string }; routing: { queue_code?: string; queue_id?: number };
    sla: { resolution_min?: number }; approval: { required: boolean }; would_create_ticket: false } | null;
};
export type ScenarioPublicationPreview = {
  revision: number; source_hash: string; health: { health_status: string };
  readiness: { can_publish: boolean; variants_checked: number; issues: { code: string; path?: string; message: string }[] };
  diff: { path: string; before: unknown; after: unknown }[];
  confirmation_token: string | null; expires_at: string | null;
};
const root = "/api/web/admin/request-studio";
async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${root}${path}`, { method, credentials: "same-origin",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  const payload = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
  if (!response.ok || payload?.status !== "success") {
    throw new RequestStudioApiError("Не удалось выполнить действие в Студии", response.status, payload?.error_code);
  }
  return payload.data as T;
}
export function fetchScenarioCatalog(q = "", status = "all", offset = 0, categoryId: string | null = null) {
  return request<ScenarioCatalog>(`/catalog?${new URLSearchParams({ q, status, offset: String(offset), limit: "100", ...(categoryId ? { category_id: categoryId } : {}) })}`);
}
export function fetchScenarioDetail(id: string) { return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}`); }
export function createScenario(definition: ScenarioDraftDefinition) { return request<ScenarioDetail>("/scenarios", "POST", { definition }); }
export function saveScenario(id: string, definition: ScenarioDraftDefinition, revision: number) {
  return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/draft`, "PUT", { definition, revision });
}
export function archiveScenario(id: string, revision: number) { return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/archive`, "POST", { revision }); }
export function saveCategory(input: CategoryInput, id?: string) { return request<ScenarioCategory>(id ? `/categories/${encodeURIComponent(id)}` : "/categories", id ? "PUT" : "POST", input); }
export function archiveCategory(id: string, revision: number) { return request<ScenarioCategory>(`/categories/${encodeURIComponent(id)}?revision=${revision}`, "DELETE"); }
export function simulateScenario(id: string, revision: number, steps: ScenarioAnswerRequest[] = [], preview?: ScenarioAnswerRequest) {
  return request<ScenarioSimulation>(`/scenarios/${encodeURIComponent(id)}/simulate`, "POST", { revision, steps, ...(preview ? { preview } : {}) });
}
export function previewScenarioPublication(id: string, revision: number) {
  return request<ScenarioPublicationPreview>(`/scenarios/${encodeURIComponent(id)}/publish-preview`, "POST", { revision });
}
export function publishScenario(id: string, revision: number, confirmationToken: string) {
  return request<ScenarioDetail & { version: { version: number; id: string } }>(`/scenarios/${encodeURIComponent(id)}/publish`, "POST", { revision, confirm: true, confirmation_token: confirmationToken });
}
export function fetchScenarioVersions(id: string) {
  return request<{ id: string; version: number; state: string }[]>(`/scenarios/${encodeURIComponent(id)}/versions`);
}
export function rollbackScenarioDraft(id: string, revision: number, versionId: string) {
  return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/rollback-draft`, "POST", { revision, version_id: versionId });
}
