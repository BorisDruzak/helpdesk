import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { MemoryRouter } from "react-router-dom";

import { AdminRegistryPage } from "./registry-page";

const registryPayload = {
  summary: {
    assets: 1,
    people: 1,
    locations: 1,
    departments: 1,
    services: 0,
    vendors: 0,
    registrations_pending: 0,
    registrations_conflicts: 0,
    unregistered_devices: 0,
    active_bindings: 0,
    stale_bindings: 0,
    data_quality_issues: 0,
    suggestions: 0,
    ui_users: 1,
    ui_users_linked: 0,
    ui_users_unlinked: 1,
  },
  assets: [
    {
      id: "asset-1",
      asset_type: "computer",
      name: "Office PC",
      hostname: "PC-01",
      serial_number: null,
      inventory_number: null,
      status: "active",
      source: "agent",
      device_id: "device-1",
      assigned_person_id: null,
      location_id: "loc-1",
      department_id: null,
      service_id: null,
      vendor_id: null,
      owner_name: null,
      registration_status: "unregistered",
      active_binding_id: null,
      active_person_id: null,
      active_person_name: null,
      pending_claim_count: 0,
      last_claim_at: null,
      current_os_user: null,
      department_name: null,
      location_name: "Кабинет 101",
      service_name: null,
      vendor_name: null,
      ticket_count: 0,
      last_seen_at: null,
      updated_at: null,
    },
  ],
  people: [
    {
      id: "person-1",
      person_id: "person-1",
      display_name: "Иван Петров",
      full_name: "Петров Иван",
      phone: null,
      email: "ivan@example.test",
      login: "ivan",
      department_id: null,
      location_id: "loc-1",
      department_name: null,
      location_name: "Кабинет 101",
      source: "manual",
      status: "active",
      updated_at: null,
    },
  ],
  locations: [
    {
      id: "loc-1",
      location_id: "loc-1",
      building: "HQ",
      floor: "1",
      room: "101",
      display_name: "Кабинет 101",
      source: "manual",
      status: "active",
      users_count: 1,
      devices_count: 1,
      updated_at: null,
    },
  ],
  departments: [
    {
      id: "dept-1",
      department_id: "dept-1",
      code: "it",
      name: "ИТ",
      source: "manual",
      status: "active",
      users_count: 0,
      devices_count: 0,
      updated_at: null,
    },
  ],
  services: [],
  vendors: [],
  data_quality: [],
  suggestions: [],
  registration_claims: [],
  active_bindings: [],
  bindings: [],
  account_sessions: [],
  account_login_requests: [],
  ui_users: [
    {
      user_login: "ivan@example.test",
      actor_role: "user",
      is_active: true,
      failed_attempts: 0,
      locked_until: null,
      last_login_at: null,
      created_at: null,
      updated_at: null,
      linked_person_id: null,
      linked_person_name: null,
      linked_identity_id: null,
      linked_identity_verified: false,
    },
  ],
};

const audienceGroupsPayload = {
  groups: [
    {
      audience_group_id: "aud-1",
      code: "it_staff",
      name: "ИТ сотрудники",
      description: "Сотрудники ИТ",
      source: "manual",
      status: "active",
      metadata_json: {},
      created_at: null,
      updated_at: null,
      created_by: "admin",
      updated_by: "admin",
    },
  ],
};

function jsonResponse(data: unknown) {
  return Promise.resolve(new Response(JSON.stringify({ status: "success", data }), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  }));
}

function renderRegistry() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminRegistryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminRegistryPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/web/admin/registry/account-login-requests")) {
        return jsonResponse({ items: [] });
      }
      if (url === "/api/web/admin/registry") {
        return jsonResponse(registryPayload);
      }
      if (url === "/api/web/admin/registry/audience-groups") {
        if (init?.method === "POST") {
          return jsonResponse({ group: audienceGroupsPayload.groups[0] });
        }
        return jsonResponse(audienceGroupsPayload);
      }
      if (url === "/api/web/admin/registry/audience-groups/aud-1/members") {
        if (init?.method === "PUT") {
          return jsonResponse({ members: [{ member_type: "department_tree", member_id: "dept-1", include_children: true }] });
        }
        return jsonResponse({ members: [] });
      }
      if (url === "/api/web/admin/registry/audience-groups/aud-1/preview-members") {
        return jsonResponse({
          preview: {
            audience_group_id: "aud-1",
            code: "it_staff",
            member_count: 1,
            person_count: 1,
            people: [{ person_id: "person-1", display_name: "Иван Петров", full_name: null, email: "ivan@example.test", department_id: "dept-1", location_id: "loc-1", status: "active" }],
            warnings: [],
          },
        });
      }
      if (url === "/api/web/admin/registry/bulk/preview") {
        return jsonResponse({
          operation: "devices.assign_department",
          dry_run: true,
          requires_confirmation: true,
          counts: { requested: 1, successful: 1, failed: 0, changes: 1 },
          results: [{ id: "device-1", success: true }],
          changes: [{ kind: "registry_asset", action: "update", object_id: "asset-1" }],
          warnings: [],
          blockers: [],
        });
      }
      if (url === "/api/web/admin/registry/bulk/devices/assign-department") {
        return jsonResponse({
          bulk_operation_id: "bulk-1",
          operation: "devices.assign_department",
          summary: { selected: 1, success: 1, failed: 0 },
          items: [{ id: "device-1", status: "success" }],
        });
      }
      return Promise.resolve(new Response(JSON.stringify({ status: "error", error: `unexpected ${url}` }), {
        headers: { "Content-Type": "application/json" },
        status: 500,
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not use window.prompt in registry operator UI", () => {
    expect(readFileSync("src/pages/admin/registry-page.tsx", "utf-8")).not.toContain("window.prompt");
    expect(readFileSync("src/features/admin/registry/registry-quality-tab.tsx", "utf-8")).not.toContain("window.prompt");
  });

  it("uses a bulk dialog with department picker and preview before apply", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Устройства" }));
    fireEvent.click(await screen.findByLabelText("Select device PC-01"));
    fireEvent.click(screen.getByRole("button", { name: "Назначить подразделение" }));

    expect(screen.getByRole("heading", { name: "Массовая операция" })).toBeInTheDocument();
    expect(screen.getByText("Выберите подразделение")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Подразделение"), { target: { value: "dept-1" } });
    fireEvent.change(screen.getByLabelText("Причина"), { target: { value: "Плановая нормализация реестра" } });
    expect(screen.getByRole("button", { name: "Применить" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
    expect(await screen.findByText("Предпросмотр изменений")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/bulk/devices/assign-department",
      expect.objectContaining({ method: "POST" })
    ));
  });

  it("manages audience group members with preview before save", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: /Аудитории/ }));
    expect(await screen.findByText("ИТ сотрудники")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Тип участника"), { target: { value: "department_tree" } });
    fireEvent.change(screen.getByLabelText("Участник"), { target: { value: "dept-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить участника" }));
    fireEvent.change(screen.getByLabelText("Причина изменения аудитории"), { target: { value: "Настройка видимости базы знаний" } });
    expect(screen.getByRole("button", { name: "Сохранить участников" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр состава" }));
    expect(await screen.findByText("Людей в аудитории: 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить участников" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/audience-groups/aud-1/members",
      expect.objectContaining({ method: "PUT" })
    ));
  });
});
