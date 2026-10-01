import type { AdminEndpointFleet, AdminEndpointContext, ContextRefreshResult, EndpointCollectionDetails, EndpointContextHistory, DeviceContextDiffV1, SafeContextProfile } from "./endpoint-context-types";

const base = "/api/web/admin/endpoint";
export class EndpointContextApiError extends Error {
  constructor(public readonly code: string, public readonly status: number) { super(code); }
}
async function read<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { credentials: "same-origin", ...options });
  const payload = await response.json() as { status: string; data?: T; error_code?: string };
  if (!response.ok || payload.status !== "success" || payload.data === undefined) {
    throw new EndpointContextApiError(payload.error_code ?? "endpoint_unavailable", response.status);
  }
  return payload.data;
}
export function fetchEndpointFleet(cursor: string | null = null, signal?: AbortSignal) {
  return read<AdminEndpointFleet>(`/devices?limit=250${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { signal });
}
export function fetchEndpointDeviceContext(id: string, signal?: AbortSignal) { return read<AdminEndpointContext>(`/devices/${encodeURIComponent(id)}`, { signal }); }
export function refreshEndpointContext(id: string, profiles: ReadonlyArray<SafeContextProfile>) {
  return read<ContextRefreshResult>(`/devices/${encodeURIComponent(id)}/context/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profiles }) });
}
export function fetchEndpointCollection(id: string, signal?: AbortSignal) { return read<EndpointCollectionDetails>(`/context/collections/${encodeURIComponent(id)}`, { signal }); }
export function fetchEndpointHistory(id: string, profile: "baseline_v1" | "inventory_v1", signal?: AbortSignal) { return read<EndpointContextHistory>(`/devices/${encodeURIComponent(id)}/context/history?profile=${profile}&limit=20`, { signal }); }
export function compareEndpointHistory(id: string, before: string, after: string) { return read<DeviceContextDiffV1>(`/devices/${encodeURIComponent(id)}/context/compare?${new URLSearchParams({ before, after })}`); }
export function endpointErrorText(error: unknown): string {
  const code = error instanceof EndpointContextApiError ? error.code : "endpoint_unavailable";
  return ({ AUTH_REQUIRED: "Требуется авторизация Helpdesk", FORBIDDEN: "Недостаточно прав в Helpdesk", endpoint_not_found: "Устройство не найдено", endpoint_forbidden: "Доступ к данным Endpoint запрещён", endpoint_unauthorized: "Авторизация сервиса Endpoint недоступна", endpoint_invalid_projection: "Endpoint вернул некорректные данные" } as Record<string, string>)[code] ?? "Endpoint недоступен. Статус неизвестен (UNKNOWN).";
}
