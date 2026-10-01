export type AdminBootstrapPayload = {
  workspace: string;
  features: string[];
  observer: {
    quick_endpoint: string;
    traces_endpoint: string;
  };
};

export type AdminRegistryPayload = {
  summary: {
    assets: number;
    people: number;
    locations: number;
    departments: number;
    services: number;
    vendors: number;
    registrations_pending: number;
    registrations_conflicts: number;
    unregistered_devices: number;
    active_bindings: number;
    stale_bindings: number;
    data_quality_issues: number;
    suggestions: number;
    devices_total?: number;
    devices_registered?: number;
    devices_unregistered?: number;
    people_total?: number;
    bindings_active?: number;
    ui_users?: number;
    ui_users_linked?: number;
    ui_users_unlinked?: number;
    claims_pending?: number;
    claims_conflict?: number;
    shared_devices?: number;
    quality_issues?: number;
  };
  assets: Array<{
    id: string;
    asset_type: string;
    name: string | null;
    hostname: string | null;
    serial_number: string | null;
    inventory_number: string | null;
    status: string;
    source: string;
    device_id: string | null;
    assigned_person_id: string | null;
    location_id: string | null;
    department_id: string | null;
    service_id: string | null;
    vendor_id: string | null;
    owner_name: string | null;
    registration_status: string | null;
    binding_type?: string | null;
    active_binding_id: string | null;
    active_person_id: string | null;
    active_person_name: string | null;
    responsible_person_id?: string | null;
    responsible_person_name?: string | null;
    active_bindings?: AdminDeviceUserBinding[];
    active_tickets_count?: number;
    pending_claim_count: number;
    last_claim_at: string | null;
    current_os_user: string | null;
    latest_presence_user?: string | null;
    latest_presence_at?: string | null;
    os?: string | null;
    agent_version?: string | null;
    can_bind?: boolean;
    can_transfer?: boolean;
    can_revoke?: boolean;
    department_name: string | null;
    location_name: string | null;
    service_name: string | null;
    vendor_name: string | null;
    ticket_count: number;
    last_seen_at: string | null;
    updated_at: string | null;
  }>;
  people: Array<{
    id: string;
    person_id: string;
    display_name: string;
    full_name: string | null;
    phone: string | null;
    email: string | null;
    login?: string | null;
    position?: string | null;
    workplace_label?: string | null;
    internal_extension?: string | null;
    manager_person_id?: string | null;
    manager_name?: string | null;
    production_context?: {
      position?: string | null;
      workplace_label?: string | null;
      internal_extension?: string | null;
      manager_person_id?: string | null;
      manager_name?: string | null;
      department_id?: string | null;
      department_name?: string | null;
      location_id?: string | null;
      location_name?: string | null;
    };
    profile_completion?: {
      complete: boolean;
      status: "complete" | "required" | string;
      required_fields: Array<{ key: string; label: string }>;
      missing_fields: Array<{ key: string; label: string }>;
      setup_path: string;
      blocks: Record<string, boolean>;
    };
    department_id: string | null;
    location_id: string | null;
    department_name: string | null;
    location_name: string | null;
    identities?: AdminRegistryPersonIdentity[];
    identity_count?: number;
    verified_identity_count?: number;
    primary_device_count?: number;
    shared_device_count?: number;
    responsible_device_count?: number;
    active_ticket_count?: number;
    active_session_count?: number;
    last_seen_at?: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  locations: Array<{
    id: string;
    location_id?: string;
    building: string | null;
    floor: string | null;
    room: string | null;
    display_name: string;
    source: string;
    status: string;
    notes?: string | null;
    users_count?: number;
    devices_count?: number;
    metadata_json?: Record<string, unknown>;
    updated_at: string | null;
  }>;
  departments: Array<{
    id: string;
    department_id?: string;
    code: string | null;
    name: string;
    parent_id?: string | null;
    manager_person_id?: string | null;
    manager_name?: string | null;
    support_queue?: string | null;
    source: string;
    status: string;
    notes?: string | null;
    users_count?: number;
    devices_count?: number;
    metadata_json?: Record<string, unknown>;
    updated_at: string | null;
  }>;
  services: Array<{
    id: string;
    code: string | null;
    name: string;
    support_queue: string | null;
    owner_person_id: string | null;
    owner_person_name?: string | null;
    criticality?: string | null;
    audience?: string | null;
    audience_group_id?: string | null;
    vendor_id: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  vendors: Array<{
    id: string;
    code: string | null;
    name: string;
    contact_name: string | null;
    phone: string | null;
    email: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  data_quality: Array<{
    issue_key: string;
    issue_state?: string | null;
    issue_state_reason?: string | null;
    kind: string;
    severity: "danger" | "info" | "neutral" | "success" | "warning";
    title: string;
    description: string;
    object_type: string;
    object_id: string;
    device_id?: string | null;
    person_id?: string | null;
    department_id?: string | null;
    location_id?: string | null;
    binding_id?: string | null;
    claim_id?: string | null;
    duplicate_person_ids?: string[];
  }>;
  suggestions: Array<{
    kind: string;
    confidence: number;
    title: string;
    description: string;
    object_type: string;
    object_id: string;
  }>;
  registration_claims: AdminRegistrationClaim[];
  active_bindings: AdminDeviceUserBinding[];
  bindings?: AdminDeviceUserBinding[];
  password_reset_requests?: AdminPasswordResetRequest[];
  ui_users?: AdminRegistryUiUser[];
};

export type AdminRegistryPersonIdentity = {
  identity_id: string;
  person_id: string;
  provider: string;
  identifier: string;
  normalized_identifier: string;
  verified: boolean;
  source: string;
  last_seen_at: string | null;
};

export type AdminRegistryUiUser = {
  user_login: string;
  actor_role: string;
  is_active: boolean;
  failed_attempts: number;
  locked_until: string | null;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  linked_person_id: string | null;
  linked_person_name: string | null;
  linked_identity_id: string | null;
  linked_identity_verified: boolean;
};

export type AdminRegistryAudienceGroup = {
  audience_group_id: string;
  code: string;
  name: string;
  description: string | null;
  source: string;
  status: string;
  metadata_json: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  created_by: string | null;
  updated_by: string | null;
};

export type AdminRegistryAudienceMemberType =
  | "person"
  | "department"
  | "department_tree"
  | "location"
  | "access_group"
  | "role"
  | "service";

export type AdminRegistryAudienceGroupMember = {
  membership_id?: string;
  audience_group_id?: string;
  member_type: AdminRegistryAudienceMemberType;
  member_id: string;
  include_children?: boolean;
  valid_from?: string | null;
  valid_to?: string | null;
  source?: string;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AdminRegistryAudiencePreview = {
  audience_group_id: string;
  code: string;
  member_count: number;
  person_count: number;
  people: Array<{
    person_id: string;
    display_name: string;
    full_name: string | null;
    email: string | null;
    department_id: string | null;
    location_id: string | null;
    status: string;
  }>;
  warnings: Array<{
    code: string;
    message: string;
    member?: Record<string, unknown>;
  }>;
};

export type AdminRegistrationClaim = {
  claim_id: string;
  device_id: string;
  asset_id: string | null;
  person_id: string | null;
  person_name: string | null;
  status: string;
  claim_type: string;
  source?: string | null;
  relationship_type: string;
  confidence: number | null;
  submitted_at: string | null;
  user_confirmed_at?: string | null;
  conflict_reason: string | null;
  profile_snapshot: Record<string, unknown>;
};

export type AdminDeviceUserBinding = {
  binding_id: string;
  device_id: string;
  asset_id: string | null;
  hostname?: string | null;
  person_id: string;
  person_name: string | null;
  relationship_type: string;
  status: string;
  source?: string | null;
  source_claim_id?: string | null;
  confirmed_at: string | null;
  confirmed_by_admin: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  last_seen_at?: string | null;
  revoked_at?: string | null;
  revoked_by?: string | null;
  revoke_reason?: string | null;
};

export type AdminRegistryOperationPreview = {
  operation: string;
  dry_run: boolean;
  requires_confirmation?: boolean;
  counts?: Record<string, number>;
  results?: Array<Record<string, unknown>>;
  changes: Array<{
    kind: string;
    action: string;
    object_id?: string | null;
    before?: unknown;
    after?: unknown;
    severity?: "danger" | "destructive" | "info" | "neutral" | "success" | "warning" | string;
  }>;
  warnings?: string[];
  blockers?: string[];
  ticket_policy?: Record<string, string>;
  [key: string]: unknown;
};

export type AdminRegistryOperationResultItem = {
  id?: string | number | null;
  row?: number;
  entity_type?: string;
  status: "success" | "error" | "skipped";
  error_code?: string | null;
  message?: string | null;
  before?: unknown;
  after?: unknown;
};

export type AdminRegistryBulkItem = {
  id: string;
  status: "success" | "error";
  error_code?: string;
  error?: string;
};

export type AdminRegistryBulkResponse = {
  bulk_operation_id: string;
  operation: string;
  summary: {
    selected: number;
    success: number;
    failed: number;
  };
  items: AdminRegistryBulkItem[];
  results?: Array<Record<string, unknown>>;
};

export type AdminRegistryImportType =
  | "people"
  | "locations"
  | "departments"
  | "device_inventory_mapping"
  | "audience_groups"
  | "audience_group_members";

export type AdminRegistryImportPreview = AdminRegistryOperationPreview & {
  import_type: AdminRegistryImportType;
  preview_id: string;
  operation_id?: string;
  status?: "success" | "partial_success" | "error";
  summary?: Record<string, number>;
  items?: AdminRegistryOperationResultItem[];
  events?: string[];
  rows_total: number;
  row_errors: Array<{
    row: number;
    field?: string;
    message: string;
  }>;
  duplicate_keys: Array<{
    row: number;
    key: string;
    value: string;
    message: string;
  }>;
};

export type AdminRegistrationTimelineItem = {
  event_id: string;
  claim_id: string | null;
  binding_id: string | null;
  device_id: string;
  person_id: string | null;
  event_type: string;
  actor_id: string | null;
  actor_role: string | null;
  event_at: string | null;
  payload: Record<string, unknown>;
};

export type AdminPasswordResetRequest = {
  request_id: string;
  login: string;
  status: string;
  requested_at: string | null;
  completed_at: string | null;
  completed_by: string | null;
  resolution_note: string | null;
};

export type AdminRegistryPolicyPayload = {
  defaults: Record<string, Record<string, unknown>>;
  effective: {
    registration: {
      require_user_confirmation: boolean;
      require_admin_confirmation: boolean;
      auto_approve_first_binding: boolean;
      allow_shared_devices: boolean;
      allow_responsible_binding: boolean;
      max_primary_devices_per_person: number;
      stale_after_days: number;
      department_mode: "allow_pending_request" | "optional" | "required_existing";
      location_mode: "allow_pending_request" | "optional" | "required_existing";
    };
    ticket_visibility: {
      owner_can_see_historical_tickets: boolean;
      other_account_only_own_session_tickets: boolean;
    };
    diagnostic_target: {
      allow_single_active_binding_fallback: boolean;
    };
  };
  changed_from_defaults: Record<string, { default: unknown; effective: unknown }>;
  warnings: Array<{ field: string; severity: "warning" | "error" | string; message: string }>;
  validation: Record<string, { type: string; minimum?: number; maximum?: number; nullable?: boolean; values?: string[] }>;
  requires_restart: boolean;
  restart_required_fields: string[];
  dry_run?: boolean;
};

export type AdminRegistryProfileSchemaField = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  visible?: boolean;
  system?: boolean;
  custom?: boolean;
  editable?: boolean;
  can_delete?: boolean;
  can_hide?: boolean;
  target_kind?: string;
  storage_target?: string;
  help_text?: string | null;
  validation?: Record<string, unknown>;
  options?: Array<string | { value: string; label: string }>;
  audit_behavior?: string;
};

export type AdminRegistryProfileSchema = {
  schema_key: string;
  version?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
  storage?: Record<string, string>;
  fields: AdminRegistryProfileSchemaField[];
  custom_fields?: AdminRegistryProfileSchemaField[];
  required_fields?: Array<{ key: string; label: string }>;
  system_fields?: string[];
  editable_optional_fields?: string[];
  warnings?: string[];
};

export type AdminRegistryProfileSchemaPayload = {
  schema: AdminRegistryProfileSchema;
  updated?: boolean;
  dry_run?: boolean;
};

export type AdminRegistryProfileSchemaUpdatePayload = {
  field_overrides: Record<string, Pick<AdminRegistryProfileSchemaField, "help_text" | "required" | "visible" | "validation">>;
  custom_fields: AdminRegistryProfileSchemaField[];
  reason?: string;
};

export type AdminRegistryTimelineItem = {
  event_id: string;
  source?: "registry_admin" | "registration" | "account" | string;
  object_type?: string | null;
  object_id?: string | null;
  event_type: string;
  canonical_event_type?: string | null;
  summary?: string | null;
  actor_id?: string | null;
  actor_role?: string | null;
  reason?: string | null;
  related_device_id?: string | null;
  related_person_id?: string | null;
  device_id?: string | null;
  person_id?: string | null;
  binding_id?: string | null;
  claim_id?: string | null;
  session_id?: string | null;
  request_id?: string | null;
  ticket_id?: string | null;
  event_at: string | null;
  payload: Record<string, unknown>;
  related?: Record<string, unknown>;
  changes?: Array<Record<string, unknown>>;
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class AdminWorkspaceApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminWorkspaceApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export async function fetchAdminRegistrationClaims(status?: string): Promise<{ items: AdminRegistrationClaim[] }> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  const response = await fetch(`/api/web/admin/registry/registrations${params.toString() ? `?${params}` : ""}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить заявки регистрации");
}

export async function approveAdminRegistrationClaim(
  claimId: string,
  replaceExisting = false,
  adminOverrideUserConfirmation = false,
  reason?: string
): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/registrations/${encodeURIComponent(claimId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      replace_existing: replaceExisting,
      admin_override_user_confirmation: adminOverrideUserConfirmation,
      reason,
    })
  });
  await readSuccessResponse(response, "Не удалось подтвердить регистрацию");
}

export async function rejectAdminRegistrationClaim(claimId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/registrations/${encodeURIComponent(claimId)}/reject`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason })
  });
  await readSuccessResponse(response, "Не удалось отклонить регистрацию");
}

export async function revokeAdminDeviceUserBinding(bindingId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/bindings/${encodeURIComponent(bindingId)}/revoke`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason })
  });
  await readSuccessResponse(response, "Не удалось отозвать привязку");
}

export async function bindAdminRegistryDevicePerson(payload: {
  device_id: string;
  person_id: string;
  relationship_type: "primary_user" | "shared_user" | "responsible" | "temporary_user";
  replace_existing?: boolean;
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(payload.device_id)}/bind-person`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_id: payload.person_id,
      relationship_type: payload.relationship_type,
      replace_existing: Boolean(payload.replace_existing),
      reason: payload.reason,
    }),
  });
  await readSuccessResponse(response, "Не удалось привязать пользователя к устройству");
}

export async function transferAdminRegistryDeviceOwner(payload: {
  device_id: string;
  new_person_id: string;
  old_binding_action: "transferred" | "revoked" | "keep_as_shared";
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(payload.device_id)}/transfer-owner`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      new_person_id: payload.new_person_id,
      old_binding_action: payload.old_binding_action,
      reason: payload.reason,
    }),
  });
  await readSuccessResponse(response, "Не удалось передать устройство другому пользователю");
}

export async function previewAdminRegistryDeviceOwnerTransfer(payload: {
  device_id: string;
  new_person_id: string;
  old_binding_action: "transferred" | "revoked" | "keep_as_shared";
}): Promise<AdminRegistryOperationPreview> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(payload.device_id)}/transfer-owner/preview`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      new_person_id: payload.new_person_id,
      old_binding_action: payload.old_binding_action,
    }),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр передачи устройства");
}

export async function addAdminRegistrySharedUser(payload: {
  device_id: string;
  person_id: string;
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(payload.device_id)}/shared-users`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ person_id: payload.person_id, reason: payload.reason }),
  });
  await readSuccessResponse(response, "Не удалось добавить общего пользователя");
}

export async function assignAdminRegistryResponsible(payload: {
  device_id: string;
  person_id: string;
  replace_existing?: boolean;
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(payload.device_id)}/responsible`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_id: payload.person_id,
      replace_existing: payload.replace_existing ?? true,
      reason: payload.reason,
    }),
  });
  await readSuccessResponse(response, "Не удалось назначить ответственного");
}

export async function fetchAdminDeviceRegistrationTimeline(deviceId: string): Promise<{ items: AdminRegistrationTimelineItem[] }> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(deviceId)}/registration-timeline`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить историю регистрации");
}

export async function fetchAdminPasswordResetRequests(status?: string): Promise<{ items: AdminPasswordResetRequest[] }> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  const response = await fetch(`/api/web/admin/registry/password-reset-requests${params.toString() ? `?${params}` : ""}`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить заявки на смену пароля");
}

export async function completeAdminPasswordResetRequest(
  requestId: string,
  payload: { password: string; reason: string },
): Promise<AdminPasswordResetRequest> {
  const response = await fetch(`/api/web/admin/registry/password-reset-requests/${encodeURIComponent(requestId)}/complete`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось сменить пароль по заявке");
}

export async function createAdminRegistryPerson(payload: {
  full_name?: string | null;
  display_name: string;
  email?: string | null;
  phone?: string | null;
  position?: string | null;
  workplace_label?: string | null;
  internal_extension?: string | null;
  manager_person_id?: string | null;
  department_id?: string | null;
  location_id?: string | null;
  status?: string | null;
  reason?: string | null;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/people", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось создать пользователя");
}

export async function updateAdminRegistryPerson(personId: string, payload: {
  full_name?: string | null;
  display_name?: string | null;
  email?: string | null;
  phone?: string | null;
  position?: string | null;
  workplace_label?: string | null;
  internal_extension?: string | null;
  manager_person_id?: string | null;
  department_id?: string | null;
  location_id?: string | null;
  status?: string | null;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/people/${encodeURIComponent(personId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось обновить пользователя");
}

export async function archiveAdminRegistryPerson(personId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/people/${encodeURIComponent(personId)}/archive`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  await readSuccessResponse(response, "Не удалось архивировать пользователя");
}

export async function createAdminRegistryPersonIdentity(personId: string, payload: {
  provider: string;
  identifier: string;
  verified: boolean;
  reason?: string | null;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/people/${encodeURIComponent(personId)}/identities`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось добавить identity");
}

export async function updateAdminRegistryPersonIdentity(identityId: string, payload: {
  verified?: boolean;
  source?: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/identities/${encodeURIComponent(identityId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось обновить identity");
}

export async function linkAdminRegistryUiUserPerson(userLogin: string, payload: {
  person_id: string;
  reason?: string | null;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/ui-users/${encodeURIComponent(userLogin)}/link-person`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось привязать UI аккаунт");
}

export async function disableAdminRegistryUiUser(userLogin: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/ui-users/${encodeURIComponent(userLogin)}/disable`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  await readSuccessResponse(response, "Не удалось отключить вход в UI аккаунт");
}

export async function deleteAdminRegistryPersonIdentity(identityId: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/identities/${encodeURIComponent(identityId)}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await readSuccessResponse(response, "Не удалось удалить identity");
}

export async function createAdminRegistryLocation(payload: {
  building?: string | null;
  floor?: string | null;
  room?: string | null;
  display_name?: string | null;
  status?: string | null;
  notes?: string | null;
  reason: string;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/locations", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось создать локацию");
}

export async function updateAdminRegistryLocation(locationId: string, payload: {
  building?: string | null;
  floor?: string | null;
  room?: string | null;
  display_name?: string | null;
  status?: string | null;
  notes?: string | null;
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/locations/${encodeURIComponent(locationId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось обновить локацию");
}

export async function archiveAdminRegistryLocation(locationId: string, reason: string, force = false): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/locations/${encodeURIComponent(locationId)}/archive`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, force }),
  });
  await readSuccessResponse(response, "Не удалось архивировать локацию");
}

export async function mergeAdminRegistryLocations(payload: {
  master_location_id: string;
  duplicate_location_id: string;
  reason: string;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/locations/merge", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось объединить локации");
}

export async function previewAdminRegistryLocationsMerge(payload: {
  master_location_id: string;
  duplicate_location_id: string;
}): Promise<AdminRegistryOperationPreview> {
  const response = await fetch("/api/web/admin/registry/locations/merge/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр слияния локаций");
}

export async function createAdminRegistryDepartment(payload: {
  code?: string | null;
  name: string;
  parent_id?: string | null;
  manager_person_id?: string | null;
  support_queue?: string | null;
  status?: string | null;
  notes?: string | null;
  reason: string;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/departments", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось создать подразделение");
}

export async function updateAdminRegistryDepartment(departmentId: string, payload: {
  code?: string | null;
  name?: string | null;
  parent_id?: string | null;
  manager_person_id?: string | null;
  support_queue?: string | null;
  status?: string | null;
  notes?: string | null;
  reason: string;
}): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/departments/${encodeURIComponent(departmentId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось обновить подразделение");
}

export async function archiveAdminRegistryDepartment(departmentId: string, reason: string, force = false): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/departments/${encodeURIComponent(departmentId)}/archive`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, force }),
  });
  await readSuccessResponse(response, "Не удалось архивировать подразделение");
}

export async function mergeAdminRegistryDepartments(payload: {
  master_department_id: string;
  duplicate_department_id: string;
  reason: string;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/departments/merge", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось объединить подразделения");
}

export async function previewAdminRegistryDepartmentsMerge(payload: {
  master_department_id: string;
  duplicate_department_id: string;
}): Promise<AdminRegistryOperationPreview> {
  const response = await fetch("/api/web/admin/registry/departments/merge/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр слияния подразделений");
}

export async function fetchAdminRegistryPolicies(): Promise<AdminRegistryPolicyPayload> {
  const response = await fetch("/api/web/admin/registry/policies", { credentials: "same-origin" });
  return readSuccessResponse(response, "Не удалось загрузить политики реестра");
}

export async function updateAdminRegistryPolicies(payload: {
  policies: AdminRegistryPolicyPayload["effective"];
  reason: string;
}): Promise<AdminRegistryPolicyPayload> {
  const response = await fetch("/api/web/admin/registry/policies", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось сохранить политики реестра");
}

export async function previewAdminRegistryPolicies(policies: AdminRegistryPolicyPayload["effective"]): Promise<AdminRegistryPolicyPayload> {
  const response = await fetch("/api/web/admin/registry/policies/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policies }),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр политик реестра");
}

export async function resetAdminRegistryPolicies(reason: string): Promise<AdminRegistryPolicyPayload> {
  const response = await fetch("/api/web/admin/registry/policies/reset", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return readSuccessResponse(response, "Не удалось сбросить политики реестра");
}

export async function fetchAdminRegistryProfileSchema(): Promise<AdminRegistryProfileSchemaPayload> {
  const response = await fetch("/api/web/admin/registry/profile-schema", { credentials: "same-origin" });
  return readSuccessResponse(response, "Не удалось загрузить схему профиля");
}

export async function saveAdminRegistryProfileSchema(
  payload: AdminRegistryProfileSchemaUpdatePayload,
): Promise<AdminRegistryProfileSchemaPayload> {
  const response = await fetch("/api/web/admin/registry/profile-schema", {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось сохранить схему профиля");
}

export async function previewAdminRegistryProfileSchema(
  payload: AdminRegistryProfileSchemaUpdatePayload,
): Promise<AdminRegistryProfileSchemaPayload> {
  const response = await fetch("/api/web/admin/registry/profile-schema/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр схемы профиля");
}

export async function mergeAdminRegistryPeople(payload: {
  master_person_id: string;
  duplicate_person_id: string;
  field_strategy?: Record<string, "master" | "duplicate">;
  reason: string;
}): Promise<void> {
  const response = await fetch("/api/web/admin/registry/people/merge", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await readSuccessResponse(response, "Не удалось объединить пользователей");
}

export async function previewAdminRegistryPeopleMerge(payload: {
  master_person_id: string;
  duplicate_person_id: string;
  field_strategy?: Record<string, "master" | "duplicate">;
}): Promise<AdminRegistryOperationPreview> {
  const response = await fetch("/api/web/admin/registry/people/merge/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр слияния пользователей");
}

export async function previewAdminRegistryBulk(payload: {
  operation: "devices.assign_location" | "devices.assign_department" | "people.assign_department";
  ids: string[];
  payload?: Record<string, unknown>;
}): Promise<AdminRegistryOperationPreview> {
  const response = await fetch("/api/web/admin/registry/bulk/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр массовой операции");
}

export async function bulkAssignAdminRegistryDeviceLocation(payload: {
  ids: string[];
  location_id: string;
  reason: string;
}): Promise<AdminRegistryBulkResponse> {
  const response = await fetch("/api/web/admin/registry/bulk/devices/assign-location", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: payload.ids, payload: { location_id: payload.location_id }, reason: payload.reason }),
  });
  return readSuccessResponse(response, "Не удалось массово назначить локацию");
}

export async function bulkAssignAdminRegistryDeviceDepartment(payload: {
  ids: string[];
  department_id: string;
  reason: string;
}): Promise<AdminRegistryBulkResponse> {
  const response = await fetch("/api/web/admin/registry/bulk/devices/assign-department", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: payload.ids, payload: { department_id: payload.department_id }, reason: payload.reason }),
  });
  return readSuccessResponse(response, "Не удалось массово назначить подразделение устройствам");
}

export async function bulkAssignAdminRegistryPeopleDepartment(payload: {
  ids: string[];
  department_id: string;
  reason: string;
}): Promise<AdminRegistryBulkResponse> {
  const response = await fetch("/api/web/admin/registry/bulk/people/assign-department", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: payload.ids, payload: { department_id: payload.department_id }, reason: payload.reason }),
  });
  return readSuccessResponse(response, "Не удалось массово назначить подразделение пользователям");
}

export async function fetchAdminRegistryTimeline(objectType: string, objectId: string): Promise<{ items: AdminRegistryTimelineItem[] }> {
  const response = await fetch(`/api/web/admin/registry/timeline/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить timeline");
}

export async function previewAdminRegistryImport(payload: {
  type: AdminRegistryImportType;
  csv_text: string;
}): Promise<AdminRegistryImportPreview> {
  const response = await fetch("/api/web/admin/registry/import/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: payload.type, format: "csv", csv_text: payload.csv_text }),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр импорта реестра");
}

export async function applyAdminRegistryImport(payload: {
  type: AdminRegistryImportType;
  csv_text: string;
  preview_id: string;
  reason: string;
}): Promise<AdminRegistryImportPreview> {
  const response = await fetch("/api/web/admin/registry/import/apply", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: payload.type,
      format: "csv",
      csv_text: payload.csv_text,
      preview_id: payload.preview_id,
      reason: payload.reason,
    }),
  });
  return readSuccessResponse(response, "Не удалось применить импорт реестра");
}

export async function updateAdminRegistryQualityIssue(payload: {
  issue_key: string;
  action: "ignore" | "snooze" | "resolve";
  reason: string;
  days?: number;
}): Promise<{ override: Record<string, unknown> }> {
  const response = await fetch(`/api/web/admin/registry/quality/${encodeURIComponent(payload.issue_key)}/${payload.action}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: payload.reason, days: payload.days }),
  });
  return readSuccessResponse(response, "Не удалось обновить статус проблемы качества");
}

export function adminRegistryExportUrl(
  type:
    | "devices"
    | "people"
    | "bindings"
    | "locations"
    | "departments"
    | "quality"
    | "audience_groups"
    | "audience_group_members"
    | "knowledge_audience_rules",
  format = "csv",
): string {
  const params = new URLSearchParams({ type, format });
  return `/api/web/admin/registry/export?${params.toString()}`;
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

async function readSuccessResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminWorkspaceApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

export async function fetchAdminBootstrap(): Promise<AdminBootstrapPayload> {
  const response = await fetch("/api/web/admin/bootstrap", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить рабочее место администрирования");
}

export async function fetchAdminRegistry(): Promise<AdminRegistryPayload> {
  const response = await fetch("/api/web/admin/registry", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реестры");
}

export async function fetchAdminRegistryAudienceGroups(includeArchived = false): Promise<{ groups: AdminRegistryAudienceGroup[] }> {
  const params = includeArchived ? "?include_archived=true" : "";
  const response = await fetch(`/api/web/admin/registry/audience-groups${params}`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить аудитории реестра");
}

export async function createAdminRegistryAudienceGroup(payload: {
  code: string;
  name: string;
  description?: string | null;
  source?: string;
  reason: string;
}): Promise<{ group: AdminRegistryAudienceGroup }> {
  const response = await fetch("/api/web/admin/registry/audience-groups", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось создать аудиторию");
}

export async function updateAdminRegistryAudienceGroup(audienceGroupId: string, payload: {
  code?: string;
  name?: string;
  description?: string | null;
  source?: string;
  reason: string;
}): Promise<{ group: AdminRegistryAudienceGroup }> {
  const response = await fetch(`/api/web/admin/registry/audience-groups/${encodeURIComponent(audienceGroupId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось обновить аудиторию");
}

export async function archiveAdminRegistryAudienceGroup(audienceGroupId: string, reason: string): Promise<{ group: AdminRegistryAudienceGroup }> {
  const response = await fetch(`/api/web/admin/registry/audience-groups/${encodeURIComponent(audienceGroupId)}/archive`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return readSuccessResponse(response, "Не удалось архивировать аудиторию");
}

export async function fetchAdminRegistryAudienceGroupMembers(audienceGroupId: string): Promise<{ members: AdminRegistryAudienceGroupMember[] }> {
  const response = await fetch(`/api/web/admin/registry/audience-groups/${encodeURIComponent(audienceGroupId)}/members`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить участников аудитории");
}

export async function setAdminRegistryAudienceGroupMembers(audienceGroupId: string, payload: {
  members: AdminRegistryAudienceGroupMember[];
  reason: string;
}): Promise<{ members: AdminRegistryAudienceGroupMember[] }> {
  const response = await fetch(`/api/web/admin/registry/audience-groups/${encodeURIComponent(audienceGroupId)}/members`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось сохранить участников аудитории");
}

export async function previewAdminRegistryAudienceGroupMembers(audienceGroupId: string, members?: AdminRegistryAudienceGroupMember[]): Promise<{ preview: AdminRegistryAudiencePreview }> {
  const response = await fetch(`/api/web/admin/registry/audience-groups/${encodeURIComponent(audienceGroupId)}/preview-members`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(members ? { members } : {}),
  });
  return readSuccessResponse(response, "Не удалось построить предпросмотр аудитории");
}
