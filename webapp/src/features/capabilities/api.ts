import { SupportBootstrapApiError } from "../queues/api";
import type {
  AgentRecipeCreatePayload,
  AgentRecipeCreateResult,
  AgentRecipePrimitive,
  CapabilityDescriptor,
  DiagnosticProviderConfig,
} from "./types";

type ApiErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

type ApiOkResponse<T> = {
  status: "ok";
} & T;

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

function assertOk<T>(payload: ApiOkResponse<T> | ApiErrorResponse | null, response: Response, fallback: string): T {
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(errorPayload?.error ?? fallback, response.status, errorPayload?.error_code);
  }
  return payload as ApiOkResponse<T>;
}

export async function listAdminCapabilities(): Promise<CapabilityDescriptor[]> {
  const response = await fetch("/api/web/admin/capabilities", { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ capabilities: CapabilityDescriptor[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load capabilities").capabilities;
}

export async function listAdminCapabilityProviderConfigs(): Promise<DiagnosticProviderConfig[]> {
  const response = await fetch("/api/web/admin/capabilities/provider-configs", { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ provider_configs: DiagnosticProviderConfig[] }> | ApiErrorResponse>(
    response,
  );
  return assertOk(payload, response, "Unable to load capability provider configs").provider_configs;
}

export async function listTicketCapabilityReadiness(ticketId: string): Promise<CapabilityDescriptor[]> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/diagnostics/capabilities`, {
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ capabilities: CapabilityDescriptor[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load ticket capability readiness").capabilities;
}

export async function listAgentRecipePrimitives(): Promise<AgentRecipePrimitive[]> {
  const response = await fetch("/api/web/admin/agent-recipes/primitives", { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ primitives: AgentRecipePrimitive[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load agent recipe primitives").primitives;
}

export async function createAgentRecipe(payload: AgentRecipeCreatePayload): Promise<AgentRecipeCreateResult> {
  const response = await fetch("/api/web/admin/agent-recipes", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await readJson<ApiOkResponse<AgentRecipeCreateResult> | ApiErrorResponse>(response);
  return assertOk(data, response, "Unable to create agent recipe");
}

export async function validateAgentRecipe(recipeVersionId: string): Promise<{ validation_status: string }> {
  const response = await fetch(`/api/web/admin/agent-recipes/${encodeURIComponent(recipeVersionId)}/validate`, {
    method: "POST",
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ validation_status: string }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to validate agent recipe");
}

export async function publishAgentRecipe(recipeVersionId: string): Promise<{ capability_id: string }> {
  const response = await fetch(`/api/web/admin/agent-recipes/${encodeURIComponent(recipeVersionId)}/publish`, {
    method: "POST",
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ capability_id: string }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to publish agent recipe");
}
