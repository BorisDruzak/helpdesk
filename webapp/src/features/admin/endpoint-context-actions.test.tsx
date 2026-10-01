import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchEndpointCollection, refreshEndpointContext, fetchEndpointHistory, compareEndpointHistory } from "./endpoint-context-api";
import { EndpointContextRefresh, EndpointContextHistory } from "./endpoint-context-actions";
import type { EndpointContextCollection } from "./endpoint-context-types";
vi.mock("./endpoint-context-api", async (original) => ({...await original<typeof import("./endpoint-context-api")>(), fetchEndpointCollection: vi.fn(), refreshEndpointContext: vi.fn(), fetchEndpointHistory: vi.fn(), compareEndpointHistory: vi.fn()}));
const id = "b101d111-1a11-4b11-8c11-123456789012";
const collection: EndpointContextCollection = {id: "c101d111-1a11-4b11-8c11-123456789012", device_id: id, profile: "inventory_v1", status: "requested", requested_at: "2026-10-01T00:00:00Z", completed_at: null, result_received_at: null, failure_code: null};
function view() {
  const cache = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const invalidation = vi.spyOn(cache, "invalidateQueries");
  render(<QueryClientProvider client={cache}><EndpointContextRefresh deviceId={id}/></QueryClientProvider>);
  return invalidation;
}
describe("Context collection lifecycle", () => {
  afterEach(() => vi.clearAllMocks());
  it("preserves partial errors and rereads context only after provider completed", async () => {
    vi.mocked(refreshEndpointContext).mockResolvedValue({request_id: "test", status: "partial", results: [{profile: "inventory_v1", collection, error_code: null}, {profile: "health_v1", collection: null, error_code: "endpoint_unavailable"}]});
    vi.mocked(fetchEndpointCollection).mockResolvedValue({collection: {...collection, status: "completed"}, snapshot: null});
    const invalidate = view();
    expect(invalidate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", {name: "Запросить обновление"}));
    expect(await screen.findByText(/Часть запросов не принята/)).toBeInTheDocument();
    expect(await screen.findByText(/Завершено/)).toBeInTheDocument();
    expect(screen.getByText(/Запрос не принят: endpoint_unavailable/)).toBeInTheDocument();
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({queryKey: ["endpoint-device", id]}));
    expect(fetchEndpointCollection).toHaveBeenCalledWith(collection.id, expect.any(AbortSignal));
  });
  it.each(["failed", "expired"] as const)("keeps %s terminal without falsely refreshing successful context", async status => {
    vi.mocked(refreshEndpointContext).mockResolvedValue({request_id: "test", status: "requested", results: [{profile: "inventory_v1", collection, error_code: null}]});
    vi.mocked(fetchEndpointCollection).mockResolvedValue({collection: {...collection, status, failure_code: "collection_timeout"}, snapshot: null});
    const invalidate = view();
    fireEvent.click(screen.getByRole("button", {name: "Запросить обновление"}));
    expect(await screen.findByText(/Код ошибки Endpoint: collection_timeout/)).toBeInTheDocument();
    expect(invalidate).not.toHaveBeenCalled();
  });
  it("clears a historical diff when the selected pair changes", async () => {
    const snapshots = ["a", "b", "c"].map((value, index) => ({id: value, profile: "inventory_v1" as const,
      collected_at: `2026-10-0${index + 1}T00:00:00Z`, semantic_hash: null, warnings: [],
      sections: {system: {}, hardware: {}, memory: {module_count: 0, modules: []}, storage: {physical_devices: []}, interfaces: []}}));
    vi.mocked(fetchEndpointHistory).mockResolvedValue({snapshots});
    vi.mocked(compareEndpointHistory).mockResolvedValue({schema_version: "device_context_diff_v1", profile: "inventory_v1", from_hash: "a".repeat(64), to_hash: "b".repeat(64), changes: [{code: "RAM_CHANGED", summary: "Previous pair difference"}]});
    render(<QueryClientProvider client={new QueryClient()}><EndpointContextHistory deviceId={id}/></QueryClientProvider>);
    const before = await screen.findByLabelText("Исходное наблюдение");
    fireEvent.change(before, {target: {value: "a"}});
    fireEvent.change(screen.getByLabelText("Новое наблюдение"), {target: {value: "b"}});
    fireEvent.click(screen.getByRole("button", {name: "Сравнить"}));
    expect(await screen.findByText("Previous pair difference")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Новое наблюдение"), {target: {value: "c"}});
    expect(screen.queryByText("Previous pair difference")).not.toBeInTheDocument();
    expect(compareEndpointHistory).toHaveBeenCalledTimes(1);
  });
  it("shows the actual historical semantic hash and observation warnings", async () => {
    const hash = "a".repeat(64);
    vi.mocked(fetchEndpointHistory).mockResolvedValue({snapshots: [{id: "snapshot", profile: "inventory_v1", collected_at: "2026-10-01T00:00:00Z", semantic_hash: hash, warnings: ["probe_unavailable"], sections: {system: {}, hardware: {}, memory: {module_count: 0, modules: []}, storage: {physical_devices: []}, interfaces: []}}]});
    render(<QueryClientProvider client={new QueryClient()}><EndpointContextHistory deviceId={id}/></QueryClientProvider>);
    expect(await screen.findByText(hash)).toBeInTheDocument();
    expect(screen.getByText(/probe_unavailable/)).toBeInTheDocument();
    expect(screen.queryByRole("button", {name: "Сравнить"})).not.toBeInTheDocument();
  });

});
