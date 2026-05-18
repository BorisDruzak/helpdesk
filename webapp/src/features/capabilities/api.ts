import { SupportBootstrapApiError } from "../queues/api";
import type {
  AgentRecipeCreatePayload,
  AgentRecipeCreateResult,
  AgentRecipePrimitive,
  CapabilityDescriptor,
  DiagnosticProviderConfig,
  RunnerRolloutCreatePayload,
  RunnerRolloutPayload,
  RunnerRolloutPlan,
  ToolPresentationDetail,
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
  const response = await fetch(`/api/web/admin/capabilities?_=${Date.now()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload = await readJson<ApiOkResponse<{ capabilities: CapabilityDescriptor[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load capabilities").capabilities;
}

export async function listAdminCapabilityProviderConfigs(): Promise<DiagnosticProviderConfig[]> {
  const response = await fetch(`/api/web/admin/capabilities/provider-configs?_=${Date.now()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
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

function toolPresentationUrl(toolId: string, toolVersion?: string | null): string {
  const params = new URLSearchParams({ tool_id: toolId });
  if (toolVersion) {
    params.set("tool_version", toolVersion);
  }
  return `/api/web/tool-presentations?${params.toString()}`;
}

export async function getToolPresentation(toolId: string, toolVersion?: string | null): Promise<ToolPresentationDetail> {
  const response = await fetch(`${toolPresentationUrl(toolId, toolVersion)}&_=${Date.now()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload = await readJson<ApiOkResponse<ToolPresentationDetail> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load presentation schema");
}

export async function saveToolPresentation(
  toolId: string,
  presentationSchema: unknown,
  toolVersion?: string | null,
): Promise<ToolPresentationDetail> {
  const response = await fetch(toolPresentationUrl(toolId, toolVersion), {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presentation_schema: presentationSchema, tool_version: toolVersion ?? null, enabled: true }),
  });
  const payload = await readJson<ApiOkResponse<ToolPresentationDetail> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to save presentation schema");
}

export async function resetToolPresentation(toolId: string, toolVersion?: string | null): Promise<ToolPresentationDetail> {
  const response = await fetch(toolPresentationUrl(toolId, toolVersion), {
    method: "DELETE",
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<ToolPresentationDetail> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to reset presentation schema");
}

export async function listAgentRecipePrimitives(): Promise<AgentRecipePrimitive[]> {
  const response = await fetch(`/api/web/admin/agent-recipes/primitives?_=${Date.now()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
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

export async function getRunnerRollout(): Promise<RunnerRolloutPayload> {
  const response = await fetch(`/api/web/admin/capabilities/runner-rollout?_=${Date.now()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload = await readJson<ApiOkResponse<RunnerRolloutPayload> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load runner rollout");
}

export async function createRunnerRolloutPlan(payload: RunnerRolloutCreatePayload): Promise<RunnerRolloutPlan> {
  const response = await fetch("/api/web/admin/capabilities/runner-rollout/plans", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await readJson<ApiOkResponse<{ plan: RunnerRolloutPlan }> | ApiErrorResponse>(response);
  return assertOk(data, response, "Unable to create runner rollout plan").plan;
}

export async function runRunnerRolloutAction(
  planId: string,
  action:
    | "start-canary"
    | "promote-next-wave"
    | "pause"
    | "resume"
    | "refresh"
    | "rollback",
  payload: Record<string, unknown> = {},
): Promise<RunnerRolloutPlan> {
  const response = await fetch(
    `/api/web/admin/capabilities/runner-rollout/plans/${encodeURIComponent(planId)}/${action}`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const data = await readJson<ApiOkResponse<{ plan: RunnerRolloutPlan }> | ApiErrorResponse>(response);
  return assertOk(data, response, "Unable to update runner rollout").plan;
}
