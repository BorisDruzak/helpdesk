import { SupportBootstrapApiError } from "../queues/api";
import type { CapabilityDescriptor, DiagnosticProviderConfig, ToolPresentationDetail } from "./types";

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

export async function listAdminCapabilities(deviceId?: string | null): Promise<CapabilityDescriptor[]> {
  const params = new URLSearchParams({ _: String(Date.now()) });
  if (deviceId) {
    params.set("device_id", deviceId);
  }
  const response = await fetch(`/api/web/admin/capabilities?${params.toString()}`, {
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

function toolPresentationUrl(toolId: string, toolVersion?: string | null, deviceId?: string | null): string {
  const params = new URLSearchParams({ tool_id: toolId });
  if (toolVersion) {
    params.set("tool_version", toolVersion);
  }
  if (deviceId) {
    params.set("device_id", deviceId);
  }
  return `/api/web/tool-presentations?${params.toString()}`;
}

export async function getToolPresentation(
  toolId: string,
  toolVersion?: string | null,
  deviceId?: string | null,
): Promise<ToolPresentationDetail> {
  const response = await fetch(`${toolPresentationUrl(toolId, toolVersion, deviceId)}&_=${Date.now()}`, {
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
  deviceId?: string | null,
): Promise<ToolPresentationDetail> {
  const response = await fetch(toolPresentationUrl(toolId, toolVersion, deviceId), {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presentation_schema: presentationSchema, tool_version: toolVersion ?? null, enabled: true }),
  });
  const payload = await readJson<ApiOkResponse<ToolPresentationDetail> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to save presentation schema");
}

export async function resetToolPresentation(
  toolId: string,
  toolVersion?: string | null,
  deviceId?: string | null,
): Promise<ToolPresentationDetail> {
  const response = await fetch(toolPresentationUrl(toolId, toolVersion, deviceId), {
    method: "DELETE",
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<ToolPresentationDetail> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to reset presentation schema");
}
