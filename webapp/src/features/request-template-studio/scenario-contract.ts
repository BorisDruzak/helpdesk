/** Additive schema v1. The server validates and executes every transition. */
export type ScenarioScalar = string | boolean | number | null;
export type ScenarioAnswer = ScenarioScalar | string[];
export type ScenarioAttachment = { asset_id: string; name: string; mime_type: string; size_bytes: number; url: string };
export type ScenarioRichNode = { type: string; text?: string; attrs?: Record<string, unknown>; marks?: { type: string; attrs?: Record<string, unknown> }[]; content?: ScenarioRichNode[] };
export type ScenarioRichDocument = { type: "doc"; content: ScenarioRichNode[] };
export type ScenarioSource =
  | { source: "answer"; field: string }
  | { source: "current_result"; field?: null };
export type ScenarioCondition =
  | (ScenarioSource & { op: "eq" | "neq" | "gt" | "gte" | "lt" | "lte"; value: ScenarioScalar })
  | (ScenarioSource & { op: "in"; value: ScenarioScalar[] })
  | (ScenarioSource & { op: "exists" })
  | { op: "and" | "or"; conditions: ScenarioCondition[] }
  | { op: "not"; condition: ScenarioCondition };
export type ScenarioRole = "display_only" | "priority_impact" | "priority_urgency" | "priority_importance" | "routing_field" | "diagnostic_input" | "approval_subject" | "closure_evidence" | "reporting_dimension" | "passport_fact" | "visibility_public";
export type ScenarioFieldType = "text" | "textarea" | "select" | "multi_select" | "radio" | "checkbox" | "number" | "date" | "datetime" | "phone" | "email" | "url" | "user_picker" | "department_picker" | "location_picker" | "device_picker" | "service_picker";
export type ScenarioField = {
  key: string;
  type: ScenarioFieldType;
  label: string;
  required?: boolean;
  placeholder?: string;
  help_text?: string;
  help_document?: ScenarioRichDocument | null;
  help_attachments?: ScenarioAttachment[];
  options?: { value: string; label: string }[];
  visible_when?: ScenarioCondition | null;
  required_when?: ScenarioCondition | null;
  validation?: { min_length?: number | null; max_length?: number | null; min_value?: number | null; max_value?: number | null; optional_when_legacy_missing?:boolean };
  process_mapping?: { roles?: ScenarioRole[]; fact_key?: string | null; effects?: {value:ScenarioScalar;facts:ScenarioProcessingFacts}[] };
  allow_unknown?: boolean;
  group?: string | null;
  group_title?: string | null;
  aliases?: string[];
};
export type ScenarioProcessingFacts = {impact?:"single_user"|"multiple_users"|"department"|null;urgency?:"can_work"|"degraded"|"blocked"|null;importance?:"normal"|"important"|"critical"|null};
export type ScenarioBranchProcessing = {route?:string|null;sla_profile?:string|null;approval_required?:boolean|null};
export type ScenarioSlaProfile = {title:string;first_response_minutes:number;resolution_minutes:number;time_basis?:"calendar"|"business";calendar_id?:number|null};
export type ScenarioRoute = {title:string;queue_code:string};
export type ScenarioProcessing = {sla_profiles:Record<string,ScenarioSlaProfile>;routes:Record<string,ScenarioRoute>;defaults:{route:string;sla_profile:string};assignment_mode?:"last_matching_branch"};
export type ScenarioTransition = { to: string; when?: ScenarioCondition | null; priority?: number | null; processing_facts?:ScenarioProcessingFacts|null;processing?:ScenarioBranchProcessing|null; button?: { key: string; label: string } | null };
type BlockBase = { id: string; title: string; transitions?: ScenarioTransition[]; transition_mode?: "automatic" | "buttons" };
// Common editor envelopes may carry transitions; the strict server DTO rejects them on policy attachments.
export type ScenarioOlaTargets = { ack_minutes: number; processing_minutes: number };
export type ScenarioBlock = BlockBase & (
  | { kind: "form_page"; layout?: "single" | "group" | "section"; fields: ScenarioField[] }
  | { kind: "instruction"; content: { format?: "markdown" | "plain"; body: string; attachments?: ScenarioAttachment[]; rich_document?: ScenarioRichDocument | null }; acknowledgment_required?: boolean }
  | { kind: "navigation" }
  | { kind: "sla"; processing_facts?: ScenarioProcessingFacts | null; sla_profile?: string | null; policy_ref?: string | null }
  | { kind: "sla_attachment"; attached_to?: string | null; processing_facts?: ScenarioProcessingFacts | null; sla_profile?: string | null; policy_ref?: string | null; ola_targets?: ScenarioOlaTargets | null; ola_policy_ref?: string | null }
  | { kind: "ola_attachment"; attached_to?: string | null; targets?: ScenarioOlaTargets | null; policy_ref?: string | null }
  | { kind: "routing_attachment"; attached_to?: string | null; route?: string | null; policy_ref?: string | null }
  | { kind: "decision" }
  | { kind: "resolution_check" }
  | { kind: "diagnostic"; capability?: string; require_consent?: boolean; timeout_seconds?: number; execution_mode?: "unavailable" }
  | { kind: "review" }
  | { kind: "submit_ticket"; ola_targets?: ScenarioOlaTargets | null; ola_policy_ref?: string | null; route?: string | null; routing_policy_ref?: string | null; sla_profile?: string | null; policy_ref?: string | null }
  | { kind: "finish"; message?: string }
);
export type ScenarioPolicyKind = "priority" | "routing" | "sla" | "ola" | "approval" | "notification" | "closure" | "visibility";
export type ScenarioEntryPoint = {
  key: string; title: string; description?: string; category_id?: string | null;
  synonyms?: string[]; visibility?: "public" | "internal" | "restricted";
  enabled?: boolean; target_block_id: string; reported_symptom?: string;
};
export type PendingCatalogEntrance = { key:string; title:string; position:{x:number;y:number} };
export type ScenarioEditorLayout = { positions?: Record<string, { x: number; y: number }>; pending_entrances?: PendingCatalogEntrance[] };
export type ScenarioDraftDefinition = {
  schema_version?: 1 | 2 | 3 | 4;
  execution_semantics?: 1 | 2 | 3;
  scenario_key: string;
  service_code: string;
  offering_full_code: string;
  category_id?: string | null;
  title: string;
  description?: string;
  publish_offering?: boolean;
  entry_block_id?: string | null;
  entry_points?: ScenarioEntryPoint[];
  editor_layout?: ScenarioEditorLayout;
  blocks?: ScenarioBlock[];
  process_binding: { request_template_key: string; priority_source?: "existing_server_policy_runtime"; policy_refs?: Partial<Record<ScenarioPolicyKind, string>> };
  processing?:ScenarioProcessing|null;
};
export type ScenarioDefinition = Omit<ScenarioDraftDefinition, "entry_block_id" | "blocks"> & {
  entry_block_id: string;
  blocks: ScenarioBlock[];
};
export type ScenarioAnswerRequest = {
  expected_block_id: string;
  revision: number;
  answers?: Record<string, ScenarioAnswer>;
  current_result?: "yes" | "no" | "unknown" | "acknowledged" | "request_ticket" | null;
  action_key?: string | null;
};
