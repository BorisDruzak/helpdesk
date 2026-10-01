import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchEndpointFleet, EndpointContextApiError } from "../../features/admin/endpoint-context-api";
import { AdminInventoryPage } from "./inventory-page";
import type { AdminEndpointFleetItem } from "../../features/admin/endpoint-context-types";
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
    expect(screen.queryByText("Не добавлено в реестр")).not.toBeInTheDocument();
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
  it("filters exact provider and Registry fields without additional provider requests", async () => {
    const fresh: AdminEndpointFleetItem = {
      ...item,
      inventory_summary: {hostname: "Fresh Windows", platform: "windows"},
      profiles: [{profile: "inventory_v1", status: "completed", last_collected_at: new Date().toISOString()}],
      registry: {status: "mapped", department: "Finance", location: "Room 214", bindings: [{binding_id: "b", person_id: "p", display_name: "Owner", relationship_type: "primary_user", department_id: null, department: null, location_id: null, location: null}]},
    };
    const stale: AdminEndpointFleetItem = {...fresh, device: {...item.device, id: "stale-id", online: false, retired_at: "2026-01-01T00:00:00Z"}, inventory_summary: {hostname: "Retired Linux", platform: "linux"}, profiles: [{profile: "inventory_v1", status: "completed", last_collected_at: "2020-01-01T00:00:00Z"}], registry: {status: "mapped", department: "IT", location: "Room 215", bindings: []}};
    mocked.mockResolvedValue({items: [fresh, stale, {...item, device: {...item.device, id: "empty-id", online: false}}], next_cursor: null, technical_source: "endpoint", business_source: "registry"});
    view();
    await screen.findByRole("link", {name: "Fresh Windows"});
    expect(screen.getByText("Без inventory context").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Устаревший inventory context").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Без Registry-привязки").nextElementSibling).toHaveTextContent("1");
    for (const [label, value, visible] of [
      ["Платформа", "linux", "Retired Linux"], ["Расположение", "Room 214", "Fresh Windows"],
      ["Связь с Registry", "unmapped", "Windows"], ["Связь пользователя", "primary_user", "Fresh Windows"],
      ["Актуальность inventory", "stale", "Retired Linux"], ["Lifecycle устройства", "retired", "Retired Linux"],
    ]) {
      fireEvent.change(screen.getByLabelText(label), {target: {value}});
      expect(screen.getAllByRole("link", {name: /^(Fresh Windows|Retired Linux|Windows)$/})).toHaveLength(1);
      expect(screen.getByRole("link", {name: visible})).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(label), {target: {value: "all"}});
    }
    fireEvent.change(screen.getByLabelText("Поиск на странице"), {target: {value: id}});
    expect(screen.getByRole("link", {name: "Fresh Windows"})).toBeInTheDocument();
    expect(screen.queryByRole("link", {name: "Retired Linux"})).not.toBeInTheDocument();
    expect(mocked).toHaveBeenCalledTimes(1);
  });
  it("keeps truncated relationship projections as disclosed candidates without inferring Registry absence", async () => {
    mocked.mockResolvedValue({items: [{...item, registry: {status: "mapped", bindings_truncated: true, bindings: [{binding_id: "b", person_id: "p", display_name: "Owner", relationship_type: "owner", department_id: null, department: null, location_id: null, location: null}]}}], next_cursor: null, technical_source: "endpoint", business_source: "registry"});
    view();
    await screen.findByRole("link", {name: "Windows"});
    fireEvent.change(screen.getByLabelText("Связь пользователя"), {target: {value: "shared_user"}});
    expect(screen.getByRole("link", {name: "Windows"})).toBeInTheDocument();
    expect(screen.getByText(/Тип связи требует проверки/)).toBeInTheDocument();
    expect(screen.queryByText("Не добавлено в реестр")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Связь пользователя"), {target: {value: "none"}});
    expect(screen.queryByRole("link", {name: "Windows"})).not.toBeInTheDocument();
  });
});
