export type RequestFormFieldOption = {
  value: string;
  label: string;
};

export type RequestFormField = {
  key: string;
  label: string;
  type:
    | "text"
    | "textarea"
    | "select"
    | "multi_select"
    | "radio"
    | "checkbox"
    | "number"
    | "date"
    | "datetime"
    | "user_picker"
    | "department_picker"
    | "location_picker"
    | "device_picker"
    | "service_picker"
    | "url"
    | "phone"
    | "email";
  required?: boolean;
  placeholder?: string | null;
  help_text?: string | null;
  options?: RequestFormFieldOption[];
  validation?: Record<string, unknown> | null;
  visible_when?: {
    field?: string;
    equals?: string | boolean | number | null;
    in?: Array<string | boolean | number | null>;
  } | null;
};

export type RequestFormOnBehalfPolicy = {
  allowed?: boolean;
  label?: string;
  affected_person_required?: boolean;
  reason_required?: boolean;
  allowed_scope?: string;
  diagnostic_target?: string;
  knowledge_visibility?: string;
  support_visibility?: string;
  no_primary_agent_behavior?: string;
  support_override_allowed?: boolean;
};

export type RequestFormAvailabilityPolicy = {
  available_without_completed_profile?: boolean;
  available_without_agent_binding?: boolean;
  requires_manual_triage?: boolean;
  contact_required?: boolean;
  allowed_for_anonymous?: boolean;
};

export type RequestFormDefinition = {
  key: string;
  request_template_key?: string | null;
  title: string;
  description?: string | null;
  request_kind?: string | null;
  on_behalf_policy?: RequestFormOnBehalfPolicy | null;
  availability_policy?: RequestFormAvailabilityPolicy | null;
  available_without_completed_profile?: boolean;
  available_without_agent_binding?: boolean;
  requires_manual_triage?: boolean;
  contact_required?: boolean;
  allowed_for_anonymous?: boolean;
  fields: RequestFormField[];
};

export type RequestFormPack = {
  pack_key: string;
  version: string;
  forms: RequestFormDefinition[];
};

export type ServiceCatalogOffering = {
  offering_code: string;
  full_code: string;
  title: string;
  description?: string | null;
  request_type_label?: string | null;
  request_template_key?: string | null;
  expected_response?: string | null;
  expected_resolution?: string | null;
  approval_required?: boolean;
  diagnostic_consent_required?: boolean;
  requires_attachment?: boolean;
};

export type ServiceCatalogService = {
  service_code: string;
  title: string;
  description?: string | null;
  icon?: string | null;
  offerings: ServiceCatalogOffering[];
};

export type ServiceCatalogCurrent = {
  catalog_version: string;
  services: ServiceCatalogService[];
  fallback?: ServiceCatalogOffering & { service_code?: string | null; service_title?: string | null };
};

export type ServiceCatalogPreviewPayload = {
  device_id?: string;
  service_code?: string;
  offering_code?: string;
  offering_full_code?: string;
  request_template_key?: string;
  form_key?: string;
  form_pack_key?: string;
  form_pack_version?: string;
  form_payload?: Record<string, unknown>;
  requester_context?: Record<string, unknown>;
  device_metadata?: Record<string, unknown>;
  description?: string;
  diagnostic_consent?: Record<string, unknown>;
  ticket_context?: RequesterOnBehalfTicketContext;
};

export type RequesterTicketPreviewPayload = ServiceCatalogPreviewPayload & {
  device_id?: string;
};

export type RequesterContextPreview = {
  profile?: {
    display_name?: string | null;
    full_name?: string | null;
    phone?: string | null;
    internal_extension?: string | null;
    department?: string | null;
    location?: string | null;
    position?: string | null;
    workplace_label?: string | null;
  } | null;
  device?: {
    device_id?: string | null;
    label?: string | null;
    relationship_type?: string | null;
    asset_name?: string | null;
    asset_type?: string | null;
  } | null;
  form_prefill?: Record<string, string | number | boolean | null>;
  routing_facts?: Record<string, string | number | boolean | null>;
  summary?: Array<{ label: string; value?: string | null }>;
};

export type RequesterTicketContextPreview = {
  schema?: string | null;
  summary?: {
    created_on_behalf?: boolean;
    affected?: string | null;
    reason?: string | null;
  };
  diagnostic_target?: {
    label?: string | null;
    available?: boolean;
    status?: string | null;
    reason?: string | null;
    text?: string | null;
  };
  form?: Record<string, string | number | boolean | null>;
};

export type ServiceCatalogSafePreview = {
  ok: boolean;
  service: { code?: string | null; title?: string | null };
  offering: { code?: string | null; full_code?: string | null; title?: string | null };
  request_type_label?: string | null;
  public_status_after_create?: string | null;
  expected_first_response?: string | null;
  expected_resolution?: string | null;
  approval: { required: boolean; text?: string | null };
  diagnostics: { required: boolean; consent_required: boolean; text?: string | null };
  next_action?: string | null;
  warnings: string[];
  blockers: string[];
  would_create_ticket: false;
  requester_context?: RequesterContextPreview;
  ticket_context?: RequesterTicketContextPreview;
};

export type PublicTicket = {
  ticket_id: string;
  ticket_code?: string | null;
  title?: string | null;
  description?: string | null;
  status?: string | null;
  status_label?: string | null;
  requester_status?: string | null;
  requester_status_label?: string | null;
  public_status?: string | null;
  public_status_label?: string | null;
  resolution_confirmation_pending?: boolean | null;
};

export type RequesterTicketActions = {
  can_send_message?: boolean;
  can_attach_files?: boolean;
  can_confirm_solution?: boolean;
  can_rate_solution?: boolean;
  can_reopen?: boolean;
};

export type PublicTicketConfirmationRequest = {
  request_id?: string | null;
  options?: Array<{
    id?: string | null;
    label?: string | null;
  }>;
};

export type PublicTicketAttachment = {
  artifact_id: string;
  type?: string | null;
  mime_type?: string | null;
  kind?: string | null;
  name?: string | null;
  url?: string | null;
};

export type PublicTicketMessage = {
  message_id?: string | null;
  event_id?: string | null;
  from_role?: string | null;
  sender_role?: string | null;
  text?: string | null;
  ts?: string | null;
  created_at?: string | null;
  metadata?: {
    confirmation_request?: PublicTicketConfirmationRequest;
  } | null;
  attachment_refs?: string[];
  attachments?: PublicTicketAttachment[];
};

export type PublicTicketEvent = {
  id?: string | number | null;
  event_id?: string | number | null;
  type?: string | null;
  event_type?: string | null;
  ts?: string | null;
  created_at?: string | null;
  requester_timeline_text?: string | null;
  requester_timeline_kind?: string | null;
  requester_timeline_payload?: Record<string, unknown> | null;
  requester_timeline_icon?: string | null;
  requester_timeline_style?: string | null;
};

export type RequesterConsentStatus = "pending" | "approved" | "denied" | "expired" | "superseded" | "canceled";

export type RequesterConsent = {
  consent_id: string;
  subject_type: string;
  subject_id: string;
  ticket_id?: string | null;
  device_id?: string | null;
  requester_person_id?: string | null;
  requester_binding_id?: string | null;
  requested_by_actor_id?: string | null;
  requested_by_role?: string | null;
  risk_level?: string | null;
  policy_snapshot?: Record<string, unknown>;
  risk_explanation?: string | null;
  requested_action_payload_redacted?: Record<string, unknown>;
  title?: string | null;
  description?: string | null;
  reason?: string | null;
  status: RequesterConsentStatus | string;
  expires_at?: string | null;
  decided_by_actor_id?: string | null;
  decided_by_role?: string | null;
  decided_from_surface?: string | null;
  decided_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RequesterConsentDecisionResult = {
  consent: RequesterConsent;
};

export type PublicTicketCreatePayload = {
  title: string;
  description: string;
  user_display_name: string;
  requester_profile?: {
    full_name?: string | null;
    building?: string | null;
    room?: string | null;
    phone?: string | null;
  };
  urgency: boolean;
  importance: boolean;
  urgency_reason?: string | null;
  importance_reason?: string | null;
  form_key?: string;
  form_pack_key?: string;
  form_pack_version?: string;
  form_payload?: Record<string, unknown>;
  ticket_type?: string;
  service_code?: string;
  offering_code?: string;
  offering_full_code?: string;
  request_template_key?: string;
};

export type PublicTicketCreateResult = {
  ticket: PublicTicket;
  public_access_code?: string | null;
  public_token?: string | null;
  public_token_expires_at?: string | null;
};

export type RequesterDevice = {
  device_id: string;
  binding_id?: string | null;
  relationship_type?: string | null;
  binding_status?: string | null;
  hostname?: string | null;
  os?: string | null;
  agent_version?: string | null;
  last_seen_at?: string | null;
  online?: boolean | null;
  asset_id?: string | null;
  asset_name?: string | null;
  asset_type?: string | null;
  asset_status?: string | null;
  department_id?: string | null;
  location_id?: string | null;
  open_ticket_count?: number;
  available_actions?: {
    create_ticket?: boolean;
    view_tickets?: boolean;
  };
};

export type RequesterProfile = {
  person_id: string;
  display_name?: string | null;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  internal_extension?: string | null;
  department_id?: string | null;
  location_id?: string | null;
  status?: string | null;
  position?: string | null;
  workplace_label?: string | null;
  preferred_contact_method?: string | null;
  custom_fields?: Record<string, string | boolean | number | null>;
};

export type RequesterProfileSchemaField = {
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
  section?: string | null;
  order?: number | null;
  width?: string | null;
  target_kind?: string;
  storage_target?: string;
  help_text?: string | null;
  validation?: Record<string, unknown>;
  options?: Array<string | { value: string; label: string }>;
  audit_behavior?: string;
};

export type RequesterProfileSchema = {
  schema_key: string;
  version?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
  fields: RequesterProfileSchemaField[];
  custom_fields?: RequesterProfileSchemaField[];
  required_fields?: Array<{ key: string; label: string }>;
  system_fields?: string[];
  editable_optional_fields?: string[];
  warnings?: string[];
};

export type RequesterProfileCompletion = {
  complete: boolean;
  status: "complete" | "required" | string;
  required_fields: Array<{ key: string; label: string }>;
  missing_fields: Array<{ key: string; label: string }>;
  setup_path: string;
  blocks?: Record<string, boolean>;
};

export type RequesterProfileUpdatePayload = {
  person_id?: string;
  full_name: string;
  department_id: string;
  location_id: string;
  phone: string;
  internal_extension?: string;
  position?: string;
  workplace_label?: string;
  preferred_contact_method?: string;
  custom_fields?: Record<string, string | boolean | number | null>;
};

export type RequesterProfileUpdateResult = {
  profile: RequesterProfile;
  profile_completion: RequesterProfileCompletion;
  profile_policy: RequesterProfileDetail["profile_policy"];
  profile_schema?: RequesterProfileSchema;
};

export type RequesterRegistryOption = {
  value: string;
  label: string;
};

export type RequesterRegistryOptionsPayload = {
  departments?: RequesterRegistryOption[];
  locations?: RequesterRegistryOption[];
};

export type RequesterOnBehalfTicketContext = {
  affected_person_id?: string;
  on_behalf_reason?: string;
  affected_person_lookup?: string;
};

export type RequesterOnBehalfPerson = {
  person_id: string;
  display_name: string;
  full_name?: string | null;
  email?: string | null;
  department?: {
    id?: string | null;
    name?: string | null;
  } | null;
  location?: {
    id?: string | null;
    display_name?: string | null;
  } | null;
  primary_agent?: {
    status?: "available" | "missing" | "ambiguous" | string;
    online?: boolean | null;
  } | null;
};

export type RequesterOnBehalfPeopleSearchResult = {
  people: RequesterOnBehalfPerson[];
};

export type RequesterIdentity = {
  identity_id?: string | null;
  provider: string;
  identifier: string;
  verified?: boolean;
  source?: string | null;
  last_seen_at?: string | null;
  created_at?: string | null;
};

export type AuthenticatedRequesterTicket = PublicTicket & {
  device_id?: string | null;
  next_action_owner?: string | null;
  requester_person_id?: string | null;
  requester_binding_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  priority_class?: string | null;
  public_access_url?: string | null;
  actions?: RequesterTicketActions;
};

export type RequesterAccountSummary = {
  login?: string | null;
  display_name?: string | null;
  email?: string | null;
  linked_profile: boolean;
};

export type RequesterDeviceDetail = {
  device: RequesterDevice;
  recent_tickets?: AuthenticatedRequesterTicket[];
};

export type RequesterProfileDetail = {
  profile?: RequesterProfile | null;
  requester_context?: RequesterContextPreview;
  account_summary?: RequesterAccountSummary;
  devices: RequesterDevice[];
  active_bindings: Array<{
    binding_id?: string | null;
    device_id?: string | null;
    relationship_type?: string | null;
    status?: string | null;
  }>;
  pending_registration_claims: RequesterPendingRegistrationClaim[];
  profile_policy: {
    editable: boolean;
    editable_fields: string[];
    change_request_required: boolean;
  };
  profile_completion?: RequesterProfileCompletion;
  profile_schema?: RequesterProfileSchema;
};

export type RequesterPendingRegistrationClaim = {
  claim_id?: string | null;
  device_id?: string | null;
  status?: string | null;
  submitted_at?: string | null;
};

export type RequesterBootstrapNextAction = {
  key: string;
  label: string;
  href: string;
  ticket_code?: string | null;
};

export type RequesterBootstrap = {
  workspace: "requester";
  profile?: RequesterProfile | null;
  profile_completion?: RequesterProfileCompletion;
  profile_schema?: RequesterProfileSchema;
  requester_context?: RequesterContextPreview;
  devices: RequesterDevice[];
  primary_device?: RequesterDevice | null;
  primary_device_resolution?: {
    status?: "available" | "missing" | "ambiguous" | string;
    reason_code?: string | null;
    source?: string | null;
    candidate_count?: number;
    candidates?: Array<{
      device_id?: string | null;
      binding_id?: string | null;
      relationship_type?: string | null;
    }>;
  };
  active_bindings: Array<{
    binding_id?: string | null;
    device_id?: string | null;
    relationship_type?: string | null;
    status?: string | null;
  }>;
  pending_registration_claims: RequesterPendingRegistrationClaim[];
  open_ticket_count: number;
  tickets_requiring_user_action_count: number;
  next_actions?: RequesterBootstrapNextAction[];
  pending_consent_count: number;
  recent_tickets: AuthenticatedRequesterTicket[];
  feature_flags?: Record<string, boolean>;
  policies?: Record<string, unknown>;
};

export type RequesterTicketCreatePayload = {
  device_id?: string;
  title: string;
  description: string;
  user_display_name?: string;
  urgency?: boolean;
  importance?: boolean;
  urgency_reason?: string;
  importance_reason?: string;
  form_key?: string;
  form_pack_key?: string;
  form_pack_version?: string;
  form_payload?: Record<string, unknown>;
  ticket_type?: string;
  service_code?: string;
  offering_code?: string;
  offering_full_code?: string;
  request_template_key?: string;
  diagnostic_consent?: Record<string, unknown>;
  ticket_context?: RequesterOnBehalfTicketContext;
};

export type RequesterTicketCreateResult = {
  ticket: AuthenticatedRequesterTicket;
  ticket_id: string;
  ticket_code?: string | null;
  public_access_code?: string | null;
  public_access_url?: string | null;
};

export type RequesterTicketClaimPublicResult = {
  ticket: AuthenticatedRequesterTicket;
  ticket_id: string;
  claimed: boolean;
  requester_person_id?: string | null;
};

export type RequesterTicketDetail = {
  ticket: AuthenticatedRequesterTicket;
  messages?: PublicTicketMessage[];
  events?: PublicTicketEvent[];
};

export type RequesterTicketMessageResult = {
  message_id: string;
  event_id?: string | number | null;
  attachments_count?: number;
};

export type RequesterAttachmentUploadResult = {
  artifact_id: string;
  filename?: string | null;
  url?: string | null;
  size?: number | null;
  sha256?: string | null;
  mime_type?: string | null;
  kind?: string | null;
};

export type RequesterTicketCloseResult = {
  ticket: AuthenticatedRequesterTicket;
};

export type PublicTicketAuthorizeResult = {
  ticket_id: string;
  public_token: string;
  public_token_expires_at?: string | null;
};

export type PublicTicketDetail = {
  ticket: PublicTicket;
  messages: PublicTicketMessage[];
  events?: PublicTicketEvent[];
};

export type PublicTicketFeedbackPayload = {
  rating: number;
  problem_resolved?: boolean | null;
  resolution_confirmed?: boolean | null;
  response_time_satisfaction?: number | null;
  communication_satisfaction?: number | null;
  quality_satisfaction?: number | null;
  reason_codes?: string[];
  comment?: string | null;
  source_surface?: "public_ticket_page" | "requester_portal";
};

export type PublicTicketFeedbackResult = {
  ok: boolean;
  feedback_id: string;
  message?: string;
  reopen_available: boolean;
};

export type RequesterTicketFeedbackPayload = PublicTicketFeedbackPayload;

export type RequesterTicketFeedbackResult = PublicTicketFeedbackResult;

export type PublicTicketReopenPayload = {
  reason_code: string;
  reason_comment?: string | null;
  linked_feedback_id?: string | null;
};

export type PublicTicketReopenResult = {
  ok?: boolean;
  ticket_id: string;
  ticket_status: string;
  reopen_id: string;
};

export type RequesterTicketReopenPayload = PublicTicketReopenPayload;

export type RequesterTicketReopenResult = PublicTicketReopenResult;
