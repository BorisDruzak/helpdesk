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
      position: "R7 Engineer",
      workplace_label: "Desk R7",
      internal_extension: "1234",
      manager_person_id: "manager-1",
      manager_name: "R7 Manager",
      production_context: {
        position: "R7 Engineer",
        workplace_label: "Desk R7",
        internal_extension: "1234",
        manager_person_id: "manager-1",
        manager_name: "R7 Manager",
      },
      profile_completion: {
        complete: false,
        status: "required",
        required_fields: [
          { key: "full_name", label: "ФИО" },
          { key: "department_id", label: "Подразделение" },
          { key: "location_id", label: "Локация" },
          { key: "phone", label: "Телефон или внутренний номер" },
        ],
        missing_fields: [
          { key: "department_id", label: "Подразделение" },
          { key: "phone", label: "Телефон или внутренний номер" },
        ],
        setup_path: "/app/requester/profile/setup",
        blocks: {
          ticket_create: true,
          ticket_preview: true,
          knowledge_requester_actions: true,
          device_binding_confirmation: true,
        },
      },
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

const registryPayloadWithApprovalDiff = {
  ...registryPayload,
  registration_claims: [
    {
      claim_id: "claim-1",
      device_id: "device-1",
      asset_id: "asset-1",
      person_id: "person-claim",
      person_name: "Анна Смирнова",
      status: "conflict",
      claim_type: "self_reported",
      relationship_type: "primary_user",
      confidence: 0.9,
      submitted_at: "2026-06-13T12:00:00Z",
      user_confirmed_at: "2026-06-13T12:05:00Z",
      conflict_reason: "active_primary_user_exists",
      profile_snapshot: {
        hostname: "PC-01",
        full_name: "Анна Смирнова",
        login: "anna",
        email: "anna@example.test",
        department_id: "dept-1",
        location_id: "loc-1",
      },
    },
  ],
  active_bindings: [
    {
      binding_id: "binding-1",
      device_id: "device-1",
      asset_id: "asset-1",
      hostname: "PC-01",
      person_id: "person-1",
      person_name: "Иван Петров",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      source_claim_id: "old-claim",
      confirmed_at: "2026-06-12T09:00:00Z",
      confirmed_by_admin: "admin",
    },
  ],
  bindings: [
    {
      binding_id: "binding-1",
      device_id: "device-1",
      asset_id: "asset-1",
      hostname: "PC-01",
      person_id: "person-1",
      person_name: "Иван Петров",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      source_claim_id: "old-claim",
      confirmed_at: "2026-06-12T09:00:00Z",
      confirmed_by_admin: "admin",
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

const accessSummaryPayload = {
  version: "test",
  users: [
    {
      user_login: "ivan@example.test",
      actor_role: "user",
      role_label: "Пользователь",
      is_active: true,
      groups: ["support_l1"],
      queue_count: 1,
    },
  ],
  queues: [
    {
      queue_id: 1,
      queue_code: "support",
      queue_name: "Support",
      is_active: true,
      members_count: 1,
    },
  ],
  access_groups: [
    {
      group_id: 10,
      code: "support_l1",
      name: "Support L1",
      description: "Первая линия поддержки",
      is_active: true,
      permissions: ["tickets.view"],
      members: ["ivan@example.test"],
      queue_grants: [
        {
          queue_id: 1,
          queue_code: "support",
          queue_name: "Support",
          role_in_queue: "member",
        },
      ],
    },
  ],
  notes: ["Тестовая сводка RBAC"],
};

const registryPoliciesPayload = {
  defaults: {
    registration: {
      require_user_confirmation: true,
      require_admin_confirmation: true,
      auto_approve_first_binding: false,
      allow_shared_devices: true,
      allow_responsible_binding: true,
      max_primary_devices_per_person: 3,
      stale_after_days: 90,
      department_mode: "allow_pending_request",
      location_mode: "allow_pending_request",
    },
    account_sessions: {
      confirmed_binding_ttl_hours: null,
      verified_other_account_ttl_hours: 24,
      registration_pending_ttl_hours: 72,
      allow_other_account_login: true,
      other_account_requires_reason: true,
      other_account_requires_admin_approval: true,
      allow_other_account_on_shared_or_responsible: true,
    },
    ticket_visibility: {
      owner_can_see_historical_tickets: true,
      other_account_only_own_session_tickets: true,
    },
  },
  effective: {
    registration: {
      require_user_confirmation: true,
      require_admin_confirmation: true,
      auto_approve_first_binding: false,
      allow_shared_devices: true,
      allow_responsible_binding: true,
      max_primary_devices_per_person: 3,
      stale_after_days: 90,
      department_mode: "allow_pending_request",
      location_mode: "allow_pending_request",
    },
    account_sessions: {
      confirmed_binding_ttl_hours: null,
      verified_other_account_ttl_hours: 24,
      registration_pending_ttl_hours: 72,
      allow_other_account_login: true,
      other_account_requires_reason: true,
      other_account_requires_admin_approval: true,
      allow_other_account_on_shared_or_responsible: true,
    },
    ticket_visibility: {
      owner_can_see_historical_tickets: true,
      other_account_only_own_session_tickets: true,
    },
  },
  changed_from_defaults: {},
  warnings: [],
  validation: {
    "registration.max_primary_devices_per_person": { type: "integer", minimum: 1, maximum: 50, nullable: false },
    "registration.stale_after_days": { type: "integer", minimum: 1, maximum: 3650, nullable: false },
    "registration.department_mode": { type: "enum", values: ["allow_pending_request", "optional", "required_existing"] },
    "registration.location_mode": { type: "enum", values: ["allow_pending_request", "optional", "required_existing"] },
    "account_sessions.confirmed_binding_ttl_hours": { type: "integer", minimum: 1, maximum: 87600, nullable: true },
    "account_sessions.verified_other_account_ttl_hours": { type: "integer", minimum: 1, maximum: 8760, nullable: false },
    "account_sessions.registration_pending_ttl_hours": { type: "integer", minimum: 1, maximum: 8760, nullable: false },
  },
  requires_restart: false,
  restart_required_fields: [],
};

const registryProfileSchemaPayload = {
  schema: {
    schema_key: "requester_profile",
    version: "test",
    storage: {
      system_fields: "registry_people",
      identities: "registry_person_identities",
      custom_fields: "registry_people.metadata_json.profile_custom_fields",
    },
    fields: [
      {
        key: "full_name",
        label: "ФИО",
        type: "text",
        required: true,
        visible: true,
        system: true,
        custom: false,
        editable: true,
        can_delete: false,
        can_hide: false,
        target_kind: "registry_person_field",
        storage_target: "registry_people.full_name",
        help_text: null,
        validation: {},
      },
      {
        key: "position",
        label: "Должность",
        type: "text",
        required: false,
        visible: true,
        system: false,
        custom: false,
        editable: true,
        can_delete: false,
        can_hide: true,
        target_kind: "registry_person_metadata",
        storage_target: "registry_people.metadata_json.position",
        help_text: null,
        validation: {},
      },
    ],
    custom_fields: [],
    system_fields: ["full_name"],
    editable_optional_fields: ["position"],
    required_fields: [{ key: "full_name", label: "ФИО" }],
    warnings: [],
  },
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
  let currentRegistryPayload: unknown;

  beforeEach(() => {
    currentRegistryPayload = registryPayload;
    fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/web/admin/registry/account-login-requests")) {
        return jsonResponse({ items: [] });
      }
      if (url === "/api/web/admin/registry") {
        return jsonResponse(currentRegistryPayload);
      }
      if (url === "/api/web/admin/registry/people/person-1" && init?.method === "PATCH") {
        return jsonResponse({ person: { person_id: "person-1", display_name: "Иван Петров", status: "active" } });
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
      if (url === "/api/web/admin/access/summary") {
        return jsonResponse(accessSummaryPayload);
      }
      if (url === "/api/web/admin/registry/policies") {
        if (init?.method === "PATCH") {
          return jsonResponse(registryPoliciesPayload);
        }
        return jsonResponse(registryPoliciesPayload);
      }
      if (url === "/api/web/admin/registry/policies/preview") {
        return jsonResponse({
          ...registryPoliciesPayload,
          dry_run: true,
          changed_from_defaults: {
            "registration.department_mode": { default: "allow_pending_request", effective: "required_existing" },
            "registration.location_mode": { default: "allow_pending_request", effective: "optional" },
          },
          effective: {
            ...registryPoliciesPayload.effective,
            registration: {
              ...registryPoliciesPayload.effective.registration,
              department_mode: "required_existing",
              location_mode: "optional",
            },
          },
        });
      }
      if (url === "/api/web/admin/registry/profile-schema") {
        if (init?.method === "PUT") {
          return jsonResponse({ ...registryProfileSchemaPayload, updated: true });
        }
        return jsonResponse(registryProfileSchemaPayload);
      }
      if (url === "/api/web/admin/registry/profile-schema/preview") {
        return jsonResponse({ ...registryProfileSchemaPayload, dry_run: true });
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

  it("shows production context in the people registry", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Пользователи" }));

    expect(await screen.findByText(/R7 Engineer/)).toBeInTheDocument();
    expect(screen.getByText(/Desk R7/)).toBeInTheDocument();
    expect(screen.getByText(/1234/)).toBeInTheDocument();
    expect(screen.getByText(/R7 Manager/)).toBeInTheDocument();
  });

  it("shows requester profile completion status in the people registry", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Пользователи" }));

    expect(await screen.findByText("Нужно заполнить профиль")).toBeInTheDocument();
    expect(screen.getByText("Не хватает: Подразделение, Телефон или внутренний номер")).toBeInTheDocument();
  });

  it("submits production context fields from the person edit dialog", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Пользователи" }));
    fireEvent.click((await screen.findAllByRole("button", { name: "Править" }))[0]);

    fireEvent.change(await screen.findByLabelText("Должность"), { target: { value: "Lead Engineer" } });
    fireEvent.change(screen.getByLabelText("Рабочее место"), { target: { value: "Desk 12" } });
    fireEvent.change(screen.getByLabelText("Внутренний номер"), { target: { value: "4567" } });
    fireEvent.change(screen.getByLabelText("ID руководителя"), { target: { value: "manager-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    const saveCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => url === "/api/web/admin/registry/people/person-1" && init?.method === "PATCH");
      expect(call).toBeTruthy();
      return call;
    });
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      position: "Lead Engineer",
      workplace_label: "Desk 12",
      internal_extension: "4567",
      manager_person_id: "manager-1",
    });
  });

  it("uses a bulk dialog with department picker and preview before apply", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Устройства" }));
    fireEvent.click(await screen.findByLabelText("Выбрать устройство PC-01"));
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

  it("allows adding access groups as audience members", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: /Аудитории/ }));
    expect(await screen.findByText("ИТ сотрудники")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Тип участника"), { target: { value: "access_group" } });
    expect(screen.getByRole("option", { name: "Группа доступа" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "support_l1 · Support L1" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Участник"), { target: { value: "support_l1" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить участника" }));
    fireEvent.change(screen.getByLabelText("Причина изменения аудитории"), { target: { value: "Добавляем RBAC-группу как факт таргетинга" } });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр состава" }));
    expect(await screen.findByText("Людей в аудитории: 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить участников" }));

    const saveCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => url === "/api/web/admin/registry/audience-groups/aud-1/members" && init?.method === "PUT");
      expect(call).toBeTruthy();
      return call;
    });
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      members: [
        expect.objectContaining({
          member_type: "access_group",
          member_id: "support_l1",
          include_children: false,
        }),
      ],
    });
  });

  it("shows access groups as a registry summary with a link to the canonical RBAC editor", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: /Группы доступа/ }));

    expect(await screen.findByText("Support L1")).toBeInTheDocument();
    expect(screen.getByText("Первая линия поддержки")).toBeInTheDocument();
    expect(screen.getByText("Права: 1")).toBeInTheDocument();
    expect(screen.getByText("Участники: 1")).toBeInTheDocument();
    expect(screen.getByText("Очереди: 1")).toBeInTheDocument();
    expect(screen.getByText("Тестовая сводка RBAC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть RBAC-редактор" })).toHaveAttribute("href", "/app/admin/access");
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/web\/admin\/access\/groups/),
      expect.objectContaining({ method: expect.stringMatching(/POST|PUT|PATCH|DELETE/) }),
    );
  });

  it("shows an approval diff for registration claims before admin actions", async () => {
    currentRegistryPayload = registryPayloadWithApprovalDiff;
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Заявки" }));

    expect(await screen.findByText("Дифф подтверждения")).toBeInTheDocument();
    expect(screen.getByText("Текущая привязка: Иван Петров · Основной пользователь")).toBeInTheDocument();
    expect(screen.getByText("Заявлено: Анна Смирнова")).toBeInTheDocument();
    expect(screen.getByText("Подразделение: ИТ")).toBeInTheDocument();
    expect(screen.getByText("Локация: Кабинет 101")).toBeInTheDocument();
    expect(screen.getByText("Идентичность: anna@example.test / anna")).toBeInTheDocument();
    expect(screen.getByText("Тип привязки: Основной пользователь")).toBeInTheDocument();
    expect(screen.getByText("Блокер: уже есть активный основной пользователь")).toBeInTheDocument();
    expect(screen.queryByText("Блокер: active_primary_user_exists")).not.toBeInTheDocument();
  });

  it("exposes department and location modes as first-class registration policy controls", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Политики · P1" }));

    const departmentMode = await screen.findByLabelText(/Режим подразделения/);
    const locationMode = screen.getByLabelText(/Режим локации/);
    expect(departmentMode).toHaveValue("allow_pending_request");
    expect(locationMode).toHaveValue("allow_pending_request");
    expect(screen.getAllByText("Разрешить pending-заявку").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Только существующие значения").length).toBeGreaterThan(0);

    fireEvent.change(departmentMode, { target: { value: "required_existing" } });
    fireEvent.change(locationMode, { target: { value: "optional" } });
    expect(screen.getAllByText("Режим подразделения").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Режим локации").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
    expect(await screen.findByText("Серверная проверка")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Причина изменения политики"), {
      target: { value: "Ужесточаем регистрацию по справочникам" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/policies",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining('"department_mode":"required_existing"'),
      })
    ));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/policies",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining('"location_mode":"optional"'),
      })
    );
  });

  it("edits requester profile schema with protected system fields and controlled custom storage", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Схема профиля · P1" }));

    expect(await screen.findByText("Системные поля защищены")).toBeInTheDocument();
    expect(screen.getByText("Нельзя скрыть или удалить")).toBeInTheDocument();
    expect(screen.getByText(/registry_people\.full_name/)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("cost_center"), { target: { value: "cost_center" } });
    fireEvent.change(screen.getByPlaceholderText("Центр затрат"), { target: { value: "Центр затрат" } });
    fireEvent.click(screen.getByLabelText("Обязательное поле"));
    fireEvent.click(screen.getByRole("button", { name: "Добавить поле" }));

    expect(screen.getByText(/registry_people\.metadata_json\.profile_custom_fields\.cost_center/)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Например: вводим обязательный центр затрат"), {
      target: { value: "Вводим обязательный центр затрат для маршрутизации" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
    expect(await screen.findByText("Серверная проверка")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Сохранить схему" }));

    const saveCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => url === "/api/web/admin/registry/profile-schema" && init?.method === "PUT");
      expect(call).toBeTruthy();
      return call;
    });
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      custom_fields: [
        expect.objectContaining({
          key: "cost_center",
          label: "Центр затрат",
          required: true,
          storage_target: "registry_people.metadata_json.profile_custom_fields.cost_center",
          audit_behavior: "profile_custom_field_change",
        }),
      ],
      reason: "Вводим обязательный центр затрат для маршрутизации",
    });
  });
});
