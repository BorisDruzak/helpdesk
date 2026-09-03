import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AdminRegistryPayload } from "../api";
import { RegistryOverviewTab } from "./registry-overview-tab";

const registryPayload: AdminRegistryPayload = {
  summary: {
    assets: 3,
    people: 2,
    locations: 0,
    departments: 0,
    services: 0,
    vendors: 0,
    registrations_pending: 1,
    registrations_conflicts: 1,
    unregistered_devices: 1,
    active_bindings: 1,
    stale_bindings: 0,
    data_quality_issues: 2,
    suggestions: 0,
    sessions_active: 1,
    ui_users_unlinked: 1,
  },
  assets: [
    {
      id: "asset-orphan",
      asset_type: "computer",
      name: "Orphan PC",
      hostname: "ORPHAN-PC",
      serial_number: null,
      inventory_number: null,
      status: "active",
      source: "agent",
      device_id: "device-orphan",
      assigned_person_id: null,
      location_id: null,
      department_id: null,
      service_id: null,
      vendor_id: null,
      owner_name: null,
      registration_status: "unregistered",
      active_binding_id: null,
      active_person_id: null,
      active_person_name: null,
      active_bindings: [],
      active_sessions_count: 0,
      active_tickets_count: 0,
      pending_claim_count: 0,
      last_claim_at: null,
      current_os_user: null,
      department_name: null,
      location_name: null,
      service_name: null,
      vendor_name: null,
      ticket_count: 0,
      last_seen_at: null,
      updated_at: null,
    },
    {
      id: "asset-owned",
      asset_type: "computer",
      name: "Owned PC",
      hostname: "OWNED-PC",
      serial_number: null,
      inventory_number: null,
      status: "active",
      source: "agent",
      device_id: "device-owned",
      assigned_person_id: "person-owner",
      location_id: null,
      department_id: null,
      service_id: null,
      vendor_id: null,
      owner_name: "Current Owner",
      registration_status: "active",
      active_binding_id: "binding-active",
      active_person_id: "person-owner",
      active_person_name: "Current Owner",
      active_sessions_count: 1,
      active_tickets_count: 0,
      pending_claim_count: 1,
      last_claim_at: "2026-06-16T08:00:00Z",
      current_os_user: "owner",
      department_name: null,
      location_name: null,
      service_name: null,
      vendor_name: null,
      ticket_count: 0,
      last_seen_at: null,
      updated_at: null,
    },
  ],
  people: [
    {
      id: "person-no-primary",
      person_id: "person-no-primary",
      display_name: "No Primary User",
      full_name: "No Primary User",
      phone: null,
      email: "no-primary@example.test",
      login: "no-primary",
      profile_completion: {
        complete: false,
        status: "required",
        required_fields: [{ key: "phone", label: "Телефон" }],
        missing_fields: [{ key: "phone", label: "Телефон" }],
        setup_path: "/app/requester/profile/setup",
        blocks: { ticket_create: true },
      },
      department_id: null,
      location_id: null,
      department_name: null,
      location_name: null,
      identities: [],
      primary_device_count: 0,
      shared_device_count: 0,
      responsible_device_count: 0,
      active_ticket_count: 0,
      active_session_count: 0,
      source: "manual",
      status: "active",
      updated_at: null,
    },
    {
      id: "person-owner",
      person_id: "person-owner",
      display_name: "Current Owner",
      full_name: "Current Owner",
      phone: null,
      email: "owner@example.test",
      login: "owner",
      profile_completion: {
        complete: true,
        status: "complete",
        required_fields: [],
        missing_fields: [],
        setup_path: "/app/requester/profile/setup",
        blocks: {},
      },
      department_id: null,
      location_id: null,
      department_name: null,
      location_name: null,
      identities: [],
      primary_device_count: 1,
      shared_device_count: 0,
      responsible_device_count: 0,
      active_ticket_count: 0,
      active_session_count: 1,
      source: "manual",
      status: "active",
      updated_at: null,
    },
  ],
  locations: [],
  departments: [],
  services: [],
  vendors: [],
  data_quality: [
    {
      issue_key: "duplicate-person-1",
      kind: "duplicate_person",
      severity: "warning",
      title: "Duplicate identity",
      description: "owner@example.test",
      object_type: "person",
      object_id: "person-owner",
      person_id: "person-owner",
      duplicate_person_ids: ["person-no-primary"],
    },
    {
      issue_key: "conflict-1",
      kind: "registration_conflict",
      severity: "danger",
      title: "Registration conflict",
      description: "Needs transfer",
      object_type: "claim",
      object_id: "claim-transfer",
      device_id: "device-owned",
      claim_id: "claim-transfer",
    },
  ],
  suggestions: [],
  registration_claims: [
    {
      claim_id: "claim-pending",
      device_id: "device-pending",
      asset_id: null,
      person_id: "person-no-primary",
      person_name: "No Primary User",
      status: "pending_admin_review",
      claim_type: "self_reported",
      relationship_type: "primary_user",
      confidence: 0.8,
      submitted_at: "2026-06-16T08:00:00Z",
      conflict_reason: null,
      profile_snapshot: { hostname: "PENDING-PC" },
    },
    {
      claim_id: "claim-transfer",
      device_id: "device-owned",
      asset_id: "asset-owned",
      person_id: "person-no-primary",
      person_name: "No Primary User",
      status: "conflict",
      claim_type: "self_reported",
      relationship_type: "primary_user",
      confidence: 0.7,
      submitted_at: "2026-06-16T08:30:00Z",
      conflict_reason: "active_primary_user_exists",
      profile_snapshot: { hostname: "OWNED-PC" },
    },
  ],
  active_bindings: [
    {
      binding_id: "binding-active",
      device_id: "device-owned",
      asset_id: "asset-owned",
      hostname: "OWNED-PC",
      person_id: "person-owner",
      person_name: "Current Owner",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      confirmed_at: "2026-06-15T08:00:00Z",
      confirmed_by_admin: "admin",
      active_sessions_count: 0,
    },
  ],
  bindings: [
    {
      binding_id: "binding-active",
      device_id: "device-owned",
      asset_id: "asset-owned",
      hostname: "OWNED-PC",
      person_id: "person-owner",
      person_name: "Current Owner",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      confirmed_at: "2026-06-15T08:00:00Z",
      confirmed_by_admin: "admin",
    },
    {
      binding_id: "binding-old",
      device_id: "device-owned",
      asset_id: "asset-owned",
      hostname: "OWNED-PC",
      person_id: "person-no-primary",
      person_name: "No Primary User",
      relationship_type: "primary_user",
      status: "transferred",
      source: "registration_claim",
      confirmed_at: "2026-06-14T08:00:00Z",
      confirmed_by_admin: "admin",
    },
  ],
  account_login_requests: [],
  ui_users: [
    {
      user_login: "orphan-ui",
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

describe("RegistryOverviewTab", () => {
  it("shows scenario-first registration and ownership queues", () => {
    render(<RegistryOverviewTab registry={registryPayload} onFixIssue={vi.fn()} onSelect={vi.fn()} />);

    expect(screen.getByText("Центр регистрации и привязок")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Очереди по сценариям" })).toBeInTheDocument();

    const expectedQueues = [
      "Ожидают привязки устройства",
      "Смена владельца и конфликты",
      "Пользователи без основного агента",
      "Устройства без владельца",
      "Профиль не заполнен",
      "Дубли идентичностей",
    ];
    for (const queue of expectedQueues) {
      expect(screen.getByRole("heading", { name: queue })).toBeInTheDocument();
    }

    expect(within(screen.getByTestId("registry-queue-ui-account-link")).getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Связать UI-аккаунт с персоной")).toBeInTheDocument();
    expect(screen.getByText("Сброс / смена UI-пароля")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть RBAC-пользователей" })).toHaveAttribute("href", "/app/admin/access");
    expect(screen.queryByText("Сессии после передачи устройства")).not.toBeInTheDocument();
  });

  it("opens device, person, claim and duplicate detail targets from queues", () => {
    const onSelect = vi.fn();
    const onFixIssue = vi.fn();
    render(<RegistryOverviewTab registry={registryPayload} onFixIssue={onFixIssue} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: "Открыть заявку claim-pending из очереди Ожидают привязки устройства" }));
    expect(onSelect).toHaveBeenCalledWith({ kind: "claim", id: "claim-pending" });

    fireEvent.click(screen.getByRole("button", { name: "Открыть пользователя person-no-primary из очереди Пользователи без основного агента" }));
    expect(onSelect).toHaveBeenCalledWith({ kind: "person", id: "person-no-primary" });

    fireEvent.click(screen.getByRole("button", { name: "Открыть устройство device-orphan из очереди Устройства без владельца" }));
    expect(onSelect).toHaveBeenCalledWith({ kind: "device", id: "device-orphan" });

    fireEvent.click(screen.getByRole("button", { name: "Открыть проблему duplicate-person-1 из очереди Дубли идентичностей" }));
    expect(onFixIssue).toHaveBeenCalledWith(expect.objectContaining({ issue_key: "duplicate-person-1" }));
  });
});
