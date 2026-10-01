import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchEndpointDeviceContext, EndpointContextApiError } from "../../features/admin/endpoint-context-api";
import { AdminDevicePage } from "./device-page";

vi.mock("../../features/admin/endpoint-context-api", async (original) => ({
  ...await original<typeof import("../../features/admin/endpoint-context-api")>(), fetchEndpointDeviceContext: vi.fn(),
}));
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({session: {actor_role: "admin"}}) }));
const mocked = vi.mocked(fetchEndpointDeviceContext);
const id = "b101d111-1a11-4b11-8c11-123456789012";
function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function view(search: string) {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/app/admin/device${search}`]}><AdminDevicePage/><Location/></MemoryRouter></QueryClientProvider>);
}
describe("Endpoint exact detail", () => {
  afterEach(() => vi.clearAllMocks());
  it("keeps the requested UUID on not found without choosing another device", async () => {
    mocked.mockRejectedValue(new EndpointContextApiError("endpoint_not_found", 404));
    view(`?device=${id}`);
    expect(await screen.findByText("Устройство не найдено")).toBeInTheDocument();
    expect(mocked.mock.calls[0][0]).toBe(id);
    expect(screen.getByTestId("location")).toHaveTextContent(`?device=${id}`);
  });
  it("does not fetch for missing or malformed device parameters", async () => {
    view("?device=bad-id");
    expect(screen.getByText("Укажите корректный идентификатор устройства")).toBeInTheDocument();
    expect(mocked).not.toHaveBeenCalled();
  });
  it("shows UNKNOWN instead of offline on provider failure", async () => {
    mocked.mockRejectedValue(new EndpointContextApiError("endpoint_unavailable", 503));
    view(`?device=${id}`);
    expect(await screen.findByText(/Статус неизвестен/)).toBeInTheDocument();
    expect(screen.queryByText("OFFLINE")).not.toBeInTheDocument();
  });
  it("renders only observed profile tabs and actual inventory sections", async () => {
    mocked.mockResolvedValue({device: {id, device_identifier: "WIN", display_name: "Exact Windows", online: false, last_seen_at: null, retired_at: null}, profiles: [{profile: "inventory_v1", status: "completed", last_collected_at: "2026-10-01T00:00:00Z"}], snapshots: [{id: "s", profile: "inventory_v1", collected_at: "2026-10-01T00:00:00Z", semantic_hash: null, warnings: [], sections: {system: {hostname: "WIN", os_name: "Windows"}, hardware: {cpu_model: "Real CPU"}, memory: {module_count: 0, modules: [], total_bytes: 8589934592}, storage: {physical_devices: []}, interfaces: []}}], registry: {status: "unmapped", bindings: []}, technical_source: "endpoint", business_source: "registry"});
    view(`?device=${id}`);
    expect(await screen.findByRole("heading", {name: "Exact Windows"})).toBeInTheDocument();
    expect(screen.queryByRole("button", {name: "Здоровье"})).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name: "Сессия"})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "Система"}));
    expect(screen.getByText("Real CPU")).toBeInTheDocument();
    expect(screen.getByText("8 ГБ")).toBeInTheDocument();
  });

});
