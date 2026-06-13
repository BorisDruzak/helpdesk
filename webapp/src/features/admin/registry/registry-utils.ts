import type { AdminRegistryPayload } from "../api";

export type RegistryTabKey =
  | "overview"
  | "devices"
  | "people"
  | "bindings"
  | "requests"
  | "account_sessions"
  | "quality"
  | "locations"
  | "departments"
  | "access_groups"
  | "audience_groups"
  | "policies";

export type RegistrySelection =
  | { kind: "device"; id: string }
  | { kind: "person"; id: string }
  | { kind: "binding"; id: string }
  | { kind: "session"; id: string }
  | { kind: "claim"; id: string }
  | null;

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function statusTone(value: string | null | undefined): "brand" | "danger" | "info" | "neutral" | "success" | "warning" {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (["active", "verified", "admin_confirmed", "approved"].includes(normalized)) {
    return "success";
  }
  if (["pending", "self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "pending_verification"].includes(normalized)) {
    return "warning";
  }
  if (["conflict", "rejected", "revoked", "expired", "stale"].includes(normalized)) {
    return "danger";
  }
  if (normalized === "agent") {
    return "brand";
  }
  if (normalized) {
    return "info";
  }
  return "neutral";
}

export function filterRegistryPayload(value: AdminRegistryPayload, query: string): AdminRegistryPayload {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return value;
  }
  const includes = (...parts: Array<string | number | null | undefined>) =>
    parts.filter((part) => part !== null && part !== undefined).join(" ").toLowerCase().includes(normalized);
  return {
    ...value,
    assets: value.assets.filter((asset) =>
      includes(asset.name, asset.hostname, asset.device_id, asset.owner_name, asset.active_person_name, asset.department_name, asset.location_name, asset.active_binding_id)
    ),
    people: value.people.filter((person) =>
      includes(person.display_name, person.full_name, person.login, person.phone, person.email, person.department_name, person.location_name, person.person_id)
      || (value.ui_users ?? []).some((user) => user.linked_person_id === person.person_id && includes(user.user_login, user.actor_role))
    ),
    registration_claims: value.registration_claims.filter((claim) =>
      includes(claim.claim_id, claim.device_id, claim.person_name, claim.person_id, claim.status, claim.relationship_type, claim.conflict_reason)
    ),
    active_bindings: value.active_bindings.filter((binding) =>
      includes(binding.binding_id, binding.device_id, binding.hostname, binding.person_id, binding.person_name, binding.relationship_type, binding.status)
    ),
    bindings: (value.bindings ?? value.active_bindings).filter((binding) =>
      includes(binding.binding_id, binding.device_id, binding.hostname, binding.person_id, binding.person_name, binding.relationship_type, binding.status)
    ),
    account_sessions: (value.account_sessions ?? []).filter((session) =>
      includes(session.session_id, session.device_id, session.person_id, session.display_name, session.login, session.account_mode, session.verification_status, session.base_binding_id)
    ),
    account_login_requests: (value.account_login_requests ?? []).filter((request) =>
      includes(request.request_id, request.device_id, request.matched_person_id, request.base_binding_id, request.status, String(request.requested_account?.login ?? ""))
    ),
    ui_users: (value.ui_users ?? []).filter((user) =>
      includes(user.user_login, user.actor_role, user.linked_person_id, user.linked_person_name)
    ),
    locations: value.locations.filter((location) => includes(location.display_name, location.building, location.floor, location.room)),
    departments: value.departments.filter((department) => includes(department.name, department.code)),
    services: value.services.filter((service) => includes(service.name, service.code, service.support_queue)),
    vendors: value.vendors.filter((vendor) => includes(vendor.name, vendor.code, vendor.contact_name, vendor.phone, vendor.email)),
    data_quality: value.data_quality.filter((issue) =>
      includes(issue.kind, issue.title, issue.description, issue.object_id, issue.device_id, issue.person_id, issue.binding_id, issue.claim_id)
    ),
  };
}
