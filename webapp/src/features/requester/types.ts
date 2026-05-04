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
};
