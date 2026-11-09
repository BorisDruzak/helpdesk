import type { ScenarioStepDisplay } from "../requester/scenario-step-content";
import type { AdminServiceCatalogOffering, AdminServiceCatalogService } from "../service-catalog/api";
import { RequestStudioApiError } from "./api";
import type { ScenarioApiIssue } from "./scenario-issues";
import type { ScenarioAnswerRequest, ScenarioAttachment, ScenarioBlock, ScenarioDraftDefinition, ScenarioEntryPoint } from "./scenario-contract";
import type { RequestFormField } from "../requester/types";
import type { DiagnosticFailureStatus } from "./scenario-diagnostics";

export type ScenarioStatus = "draft" | "published" | "errors" | "archived";
export type ScenarioCategory = {
  id: string; service_code: string; parent_id: string | null; slug: string; title: string;
  description: string; sort_order: number; visibility: "public" | "internal" | "restricted";
  effective_visibility?: string; lifecycle_status: "draft" | "published" | "archived"; revision: number;
};
export type CategoryInput = Omit<ScenarioCategory, "id" | "effective_visibility" | "revision"> & { revision?: number | null };
export type ScenarioItem = {
  has_draft_changes?: boolean;
  schema_version?:1|2|3|4;
  id: string; scenario_key: string; service_code: string; offering_full_code: string;
  category_id: string | null; title: string; description: string; archived: boolean; enabled: boolean;
  published_version_id: string | null; status?: ScenarioStatus; revision?: number;
  published_version?: number | null; updated_at?: string;
  published_entry_count?: number;
  entry_points?: ScenarioEntryPoint[];
  published_entry_points?: ScenarioEntryPoint[];
  published_public_entry_keys?: string[];
  issues?: { code: string; path: string; message: string }[];
};
export type ScenarioDetail = { scenario: ScenarioItem; draft: { revision: number; definition: ScenarioDraftDefinition }; asset_rebindings?: Record<string, ScenarioAttachment> };
export type ScenarioCatalog = {
  categories: ScenarioCategory[]; services: AdminServiceCatalogService[]; offerings: AdminServiceCatalogOffering[];
  scenarios: ScenarioItem[]; total: number; offset: number; limit: number;
  legacy_offerings?: AdminServiceCatalogOffering[];
  entries?: OfferingCard[];
};
export type OfferingCard = { offering: AdminServiceCatalogOffering; scenarios: ScenarioItem[];
  active_mode: "form" | "scenario"; requester_available?: boolean; active_scenario_id?: string | null; category_ids: string[] };
export type SimulationState = { current_block_id: string; revision: number; state: string; answers: Record<string, unknown>; history: string[]; results: Record<string, unknown> };
export type ScenarioConditionEvaluation = { op: string; matched: boolean; source?: string; field?: string; value?: unknown; actual?: unknown; present?: boolean; children?: ScenarioConditionEvaluation[] };
export type ProcessingSource = { kind: "default" | "transition" | "terminal" | "block" | "server" | "attachment"; block_id?: string; attached_to?: string; transition_index?: number };
export type ScenarioMapProcessingResult = {
  assignment_mode: "last_matching_branch";
  route: { key: string; title: string; queue_code: string; source: ProcessingSource };
  sla_profile: { key: string; title: string; first_response_minutes: number; resolution_minutes: number; time_basis: "calendar" | "business"; calendar_id?: number | null; source: ProcessingSource };
  approval_required?: boolean;
  trace: { block_id: string; transition_index: number; to: string; matched: boolean; assignments: { route?: string; sla_profile?: string; approval_required?: boolean } }[];
  condition_trace?: { block_id: string; transition_index: number; to: string; selected: boolean; condition_evaluation: ScenarioConditionEvaluation }[];
};
export type ScenarioSimulation = { revision: number; current_block: ScenarioBlock; state: SimulationState;
  map_processing?: ScenarioMapProcessingResult;
    processing_error?: { code: "PROCESSING_INPUT_INVALID" | "AUTHOR_PREVIEW_INCOMPLETE" } | null;
    preview_stop?: { code: "missing_continuation"; block_id: string } | null;
  simulation_scope?: { limited_scope: boolean; excluded_block_ids: string[]; issues: { code: string; path: string; message: string }[] };
  current_step?: ScenarioStepDisplay;
  processing?: { priority: { priority_class: string; reason?: string | null }; routing: { queue_title?: string | null; queue_code?: string; queue_id?: number; source?: ProcessingSource; selection?: { kind: "policy" | "route"; key: string; source: ProcessingSource } };
    sla: { first_response_min?: number; resolution_min?: number; time_basis?: "calendar" | "business"; policy_code?: string | null; source?: ProcessingSource; selection?: { kind: "policy" | "profile"; key: string; source: ProcessingSource }; first_response_due_preview?: string | null; resolution_due_preview?: string | null }; map_processing?: ScenarioMapProcessingResult; ola?: { policy_code?: string | null; ack_min?: number; processing_min?: number };
    approval: { required: boolean }; closure?: { requires_public_summary: boolean; requires_resolution_code: boolean };
    validated_facts?: Record<string, unknown>; notification?: { would_send: false; recipient_groups: string[]; channels: { channel: string; enabled: boolean; available: boolean }[] };
    would_create_ticket: false } | null;
};
export type ScenarioPublicationOutcome = {
  terminal: string; kind: "ticket" | "self_service"; entry_point_key?: string | null;
  priority?: { priority_class: string; reason?: string | null };
  routing?: NonNullable<ScenarioSimulation["processing"]>["routing"];
  sla?: NonNullable<ScenarioSimulation["processing"]>["sla"];
  approval_required?: boolean; map_processing?: ScenarioMapProcessingResult;
};
export type ScenarioPublicationPreview = {
  revision: number; source_hash: string; health: { health_status: string };
  catalog_visibility?: "public" | "internal" | "restricted";
  readiness: { can_publish: boolean; variants_checked: number; issues: { code: string; path?: string; message: string }[] };
  diff: { path: string; before: unknown; after: unknown }[];
  outcomes?: ScenarioPublicationOutcome[];
  confirmation_token: string | null; expires_at: string | null;
};
const root = "/api/web/admin/request-studio";
export async function uploadScenarioAttachment(id: string, file: File, blockId: string, fieldKey?: string, signal?: AbortSignal): Promise<ScenarioAttachment> {
  const body = new FormData(); body.append("file", file); body.append("block_id", blockId); if (fieldKey) body.append("field_key", fieldKey);
  const response = await fetch(`${root}/scenarios/${encodeURIComponent(id)}/attachments`, { method: "POST", body, signal, credentials: "same-origin" });
  const payload = await response.json();
  if (!response.ok || payload.status !== "success") throw new ScenarioApiError(response.status, payload.error_code);
  return payload.data;
}
export class ScenarioApiError extends RequestStudioApiError {
  constructor(status: number, code?: string, public issues: ScenarioApiIssue[] = [], public dependencies: {kind:string;key:string;label:string}[] = [], public errors: Record<string,string> = {}) {
    super("Не удалось выполнить действие в Студии", status, code);
  }
}
async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${root}${path}`, { method, credentials: "same-origin",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  const payload = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
  if (!response.ok || payload?.status !== "success") {
    const issues = Array.isArray(payload?.issues) ? payload.issues.filter((item: unknown): item is ScenarioApiIssue => !!item && typeof item === "object" && "code" in item && typeof item.code === "string" && "path" in item && typeof item.path === "string").slice(0, 100).map((item: ScenarioApiIssue) => ({ code: item.code, path: item.path, ...(typeof item.message === "string" ? { message: item.message.slice(0, 1000) } : {}) })) : [];
    const dependencies = Array.isArray(payload?.dependencies) ? payload.dependencies.filter((item: unknown): item is {kind:string;key:string;label:string} => !!item && typeof item === "object" && "kind" in item && typeof item.kind === "string" && "key" in item && typeof item.key === "string" && "label" in item && typeof item.label === "string").slice(0, 256).map((item: {kind:string;key:string;label:string}) => ({kind:item.kind.slice(0, 64), key:item.key.slice(0, 300), label:item.label.slice(0, 300)})) : [];
    const errors = payload?.errors && typeof payload.errors === "object" && !Array.isArray(payload.errors)
      ? Object.fromEntries(Object.entries(payload.errors).filter(([key,value])=>key.length>0&&key.length<=100&&typeof value==="string").slice(0,100).map(([key,value])=>[key,(value as string).slice(0,1000)])) : {};
    throw new ScenarioApiError(response.status, payload?.error_code, issues, dependencies, errors);
  }
  return payload.data as T;
}
export const scenarioRequest = request;
export function fetchScenarioCatalog(q = "", status = "all", offset = 0, categoryId: string | null = null, offeringCode?: string) {
  return request<ScenarioCatalog>(`/catalog?${new URLSearchParams({ q, status, offset: String(offset), limit: "100", ...(categoryId ? categoryId.startsWith("service:") ? { service_code: categoryId.slice(8) } : { category_id: categoryId } : {}), ...(offeringCode ? { offering_code: offeringCode } : {}) })}`);
}
export function fetchScenarioDetail(id: string) { return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}`); }
export function createScenario(definition: ScenarioDraftDefinition) { return request<ScenarioDetail>("/scenarios", "POST", { definition }); }
export function createServiceScenario(definition:ScenarioDraftDefinition,copySourceId?:string|null){return request<ScenarioDetail>("/services","POST",{definition,...(copySourceId?{copy_source_id:copySourceId}:{})});}
export type ConversionItem={offering_full_code:string;title?:string;archived?:boolean;status:"existing"|"ready"|"converted"|"blocked";detail?:ScenarioDetail;issues?:{code:string;message:string}[]};
export function convertForms(apply=false,offering_full_code?:string){return request<{items:ConversionItem[]}>("/convert-forms","POST",{apply,offering_full_code:offering_full_code??null});}
export function validateScenarioDocument(content:string,format:"json"|"yaml",id?:string){return request<{definition:ScenarioDraftDefinition;issues:{code:string;path:string;message:string}[];diff:{path:string;before:unknown;after:unknown}[]}>(`/documents/validate${id?`?scenario_id=${encodeURIComponent(id)}`:""}`,"POST",{content,format});}
export function exportScenarioDocument(id:string,format:"json"|"yaml"){return request<{format:string;content:string}>(`/scenarios/${encodeURIComponent(id)}/document?format=${format}`);}
export function saveScenario(id: string, definition: ScenarioDraftDefinition, revision: number) {
  return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/draft`, "PUT", { definition, revision });
}
export function upgradeScenarioV4(id: string, revision: number) { return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/upgrade-v4`, "POST", { revision }); }
export function archiveScenario(id: string, revision: number) { return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/archive`, "POST", { revision }); }
export function saveCategory(input: CategoryInput, id?: string) { return request<ScenarioCategory>(id ? `/categories/${encodeURIComponent(id)}` : "/categories", id ? "PUT" : "POST", input); }
export function archiveCategory(id: string, revision: number) { return request<ScenarioCategory>(`/categories/${encodeURIComponent(id)}?revision=${revision}`, "DELETE"); }
export function simulateScenario(id: string, revision: number, steps: ScenarioAnswerRequest[] = [], preview?: ScenarioAnswerRequest, diagnosticOutcomes?: Record<string, DiagnosticFailureStatus>, entryPointKey?: string, authorPreview = false) {
  return request<ScenarioSimulation>(`/scenarios/${encodeURIComponent(id)}/simulate`, "POST", { revision, steps, ...(authorPreview ? { author_preview: true } : {}), ...(entryPointKey ? { entry_point_key: entryPointKey } : {}), ...(preview ? { preview } : {}), ...(diagnosticOutcomes && Object.keys(diagnosticOutcomes).length ? { diagnostic_outcomes: diagnosticOutcomes } : {}) });
}
export function previewScenarioPublication(id: string, revision: number) {
  return request<ScenarioPublicationPreview>(`/scenarios/${encodeURIComponent(id)}/publish-preview`, "POST", { revision });
}
export function publishScenario(id: string, revision: number, confirmationToken: string) {
  return request<ScenarioDetail & { version: { version: number; id: string; definition?: ScenarioDraftDefinition } }>(`/scenarios/${encodeURIComponent(id)}/publish`, "POST", { revision, confirm: true, confirmation_token: confirmationToken });
}
export function fetchScenarioVersions(id: string) {
  return request<{ id: string; version: number; state: string }[]>(`/scenarios/${encodeURIComponent(id)}/versions`);
}
export function rollbackScenarioDraft(id: string, revision: number, versionId: string) {
  return request<ScenarioDetail>(`/scenarios/${encodeURIComponent(id)}/rollback-draft`, "POST", { revision, version_id: versionId });
}
