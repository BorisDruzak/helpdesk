export type RequestFormFieldOption = {
  value: string;
  label: string;
};

export type RequestFormField = {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "radio" | "checkbox" | "number" | "date";
  required?: boolean;
  placeholder?: string | null;
  help_text?: string | null;
  options?: RequestFormFieldOption[];
  visible_when?: {
    field?: string;
    equals?: string | boolean | number | null;
    in?: Array<string | boolean | number | null>;
  } | null;
};

export type RequestFormDefinition = {
  key: string;
  title: string;
  description?: string | null;
  request_kind?: string | null;
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
};

export type KnowledgeSuggestionItem = {
  item_id: string;
  slug: string;
  type: string;
  title: string;
  summary?: string | null;
  snippet?: string | null;
  quality_label?: string | null;
  freshness_label?: string | null;
  version_id?: string | null;
  reason?: string | null;
  visibility?: string | null;
  actions?: string[];
};

export type KnowledgeSuggestResult = {
  suggestions: KnowledgeSuggestionItem[];
  known_errors?: KnowledgeSuggestionItem[];
  workarounds?: KnowledgeSuggestionItem[];
  rollout?: {
    enabled?: boolean;
    show_before_form?: boolean;
    require_suggestions_before_submit?: boolean;
    allow_skip?: boolean;
    min_suggestions?: number;
    max_suggestions?: number;
    show_known_errors?: boolean;
    show_quality_badge?: boolean;
    show_review_freshness?: boolean;
    api_unavailable_behavior?: string;
    no_suggestions_behavior?: string;
    bypass_applied?: boolean;
    bypass_reason?: string | null;
  };
};

export type KnowledgeAttempt = {
  item_id: string;
  version_id?: string | null;
  result: "viewed" | "helpful" | "not_helpful" | "deflected" | "skipped";
  surface: "requester_portal" | "agent_gui" | "support_workspace";
  timestamp: string;
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

export type PublicTicketConfirmationRequest = {
  request_id?: string | null;
  options?: Array<{
    id?: string | null;
    label?: string | null;
  }>;
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
  knowledge_attempts?: KnowledgeAttempt[];
};

export type PublicTicketCreateResult = {
  ticket: PublicTicket;
  public_access_code?: string | null;
  public_token?: string | null;
  public_token_expires_at?: string | null;
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
