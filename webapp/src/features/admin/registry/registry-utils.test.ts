import { describe, expect, it } from "vitest";

import type { AdminRegistryPayload } from "../api";
import { filterRegistryPayload, formatDateTime } from "./registry-utils";

const registryPayload: AdminRegistryPayload = {
  summary: {
    assets: 1,
    people: 1,
    locations: 0,
    departments: 0,
    services: 0,
    vendors: 0,
    registrations_pending: 1,
    registrations_conflicts: 1,
    unregistered_devices: 1,
    active_bindings: 1,
    stale_bindings: 1,
    data_quality_issues: 1,
    suggestions: 0,
  },
  assets: [
    {
      id: "asset-1",
      asset_type: "computer",
      name: "Accounting PC",
      hostname: "ACC-17",
      serial_number: null,
      inventory_number: null,
      status: "active",
      source: "agent",
      device_id: "dev-acc-17",
      assigned_person_id: "person-1",
      location_id: null,
      department_id: null,
      service_id: null,
      vendor_id: null,
      owner_name: "Иван Петров",
      registration_status: "admin_confirmed",
      active_binding_id: "binding-primary-1",
      active_person_id: "person-1",
      active_person_name: "Иван Петров",
      pending_claim_count: 1,
      last_claim_at: null,
      current_os_user: "petrov",
      department_name: "Finance",
      location_name: "Cabinet 302",
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
      full_name: "Петров Иван Сергеевич",
      phone: "+70000000000",
      email: "petrov@example.test",
      login: "petrov",
      department_id: null,
      location_id: null,
      department_name: "Finance",
      location_name: "Cabinet 302",
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
      issue_key: "binding_stale:binding:binding-primary-1",
      kind: "binding_stale",
      severity: "warning",
      title: "Привязка устарела",
      description: "Проверьте владельца",
      object_type: "binding",
      object_id: "binding-primary-1",
      device_id: "dev-acc-17",
      binding_id: "binding-primary-1",
    },
  ],
  suggestions: [],
  registration_claims: [
    {
      claim_id: "claim-conflict-1",
      device_id: "dev-acc-17",
      asset_id: "asset-1",
      person_id: "person-1",
      person_name: "Иван Петров",
      status: "conflict",
      claim_type: "agent_reported",
      relationship_type: "primary_user",
      confidence: 0.9,
      submitted_at: null,
      conflict_reason: "primary_user_exists",
      profile_snapshot: {},
    },
  ],
  active_bindings: [
    {
      binding_id: "binding-primary-1",
      device_id: "dev-acc-17",
      asset_id: "asset-1",
      hostname: "ACC-17",
      person_id: "person-1",
      person_name: "Иван Петров",
      relationship_type: "primary_user",
      status: "active",
      source: "admin",
      confirmed_at: null,
      confirmed_by_admin: "admin",
    },
  ],
  bindings: [],
  account_login_requests: [
    {
      request_id: "login-request-1",
      device_id: "dev-acc-17",
      requested_account: { login: "other-user" },
      matched_person_id: "person-1",
      base_binding_id: "binding-primary-1",
      base_person_id: "person-1",
      status: "pending",
      verification_method: "admin_review",
      reason: null,
      requested_at: null,
      reviewed_by: null,
      reviewed_at: null,
      rejection_reason: null,
      resulting_session_id: null,
    },
  ],
};

describe("registry utilities", () => {
  it("keeps the no-data fallback readable in Russian", () => {
    expect(formatDateTime(null)).toBe("Нет данных");
  });

  it("filters registry payload across device, person, binding and quality fields", () => {
    expect(filterRegistryPayload(registryPayload, "ACC-17").assets).toHaveLength(1);
    expect(filterRegistryPayload(registryPayload, "petrov").people).toHaveLength(1);
    expect(filterRegistryPayload(registryPayload, "binding-primary-1").active_bindings).toHaveLength(1);
    expect(filterRegistryPayload(registryPayload, "binding_stale").data_quality).toHaveLength(1);
    expect(filterRegistryPayload(registryPayload, "missing").assets).toHaveLength(0);
  });
});
