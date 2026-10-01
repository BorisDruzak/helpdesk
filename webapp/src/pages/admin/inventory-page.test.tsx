import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchEndpointFleet, EndpointContextApiError } from "../../features/admin/endpoint-context-api";
import { AdminInventoryPage } from "./inventory-page";
vi.mock("../../features/admin/endpoint-context-api", async (original) => ({...await original<typeof import("../../features/admin/endpoint-context-api")>(), fetchEndpointFleet: vi.fn()}));
const mocked = vi.mocked(fetchEndpointFleet);
const id = "b101d111-1a11-4b11-8c11-123456789012";
const item = {device: {id, device_identifier: "WIN", display_name: "Windows", retired_at: null, last_seen_at: null, online: true}, profiles: [], inventory_summary: null,
  registry: {status: "unmapped" as const, bindings: []}};
function view() { return render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><MemoryRouter><AdminInventoryPage/></MemoryRouter></QueryClientProvider>); }
describe("Endpoint fleet", () => {
  afterEach(() => vi.clearAllMocks());
  it("keeps unmapped devices visible and opens the exact Endpoint UUID", async () => {
    mocked.mockResolvedValue({items: [item], next_cursor: null, technical_source: "endpoint", business_source: "registry"});
    view();
    expect(await screen.findByRole("link", {name: "Windows"})).toHaveAttribute("href", `/app/admin/device?device=${id}`);
    expect(screen.getByText("Связь не подтверждена")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Токены/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Статус устройства"), {target: {value: "offline"}});
    expect(screen.queryByRole("link", {name: "Windows"})).not.toBeInTheDocument();
  });
  it("uses the provider cursor for subsequent pages without fetching detail per row", async () => {
    mocked.mockResolvedValueOnce({items: [item], next_cursor: id, technical_source: "endpoint", business_source: "registry"}).mockResolvedValueOnce({items: [], next_cursor: null, technical_source: "endpoint", business_source: "registry"});
    view();
    await screen.findByRole("link", {name: "Windows"});
    fireEvent.click(screen.getByRole("button", {name: "Далее"}));
    await screen.findByText("Endpoint не вернул устройств.");
    expect(mocked.mock.calls[1][0]).toBe(id);
  });
  it("shows provider error and UNKNOWN instead of empty offline inventory", async () => {
    mocked.mockRejectedValue(new EndpointContextApiError("endpoint_unavailable", 503));
    view();
    expect(await screen.findByRole("alert")).toHaveTextContent("UNKNOWN");
    expect(screen.queryByText("Endpoint не вернул устройств.")).not.toBeInTheDocument();
  });
});
