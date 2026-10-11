/** Additive schema v1. The server validates and executes every transition. */
export type ScenarioScalar = string | boolean | number | null;
export type ScenarioAnswer = ScenarioScalar | string[];
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
  options?: { value: string; label: string }[];
  visible_when?: ScenarioCondition | null;
  required_when?: ScenarioCondition | null;
  validation?: { min_length?: number | null; max_length?: number | null; min_value?: number | null; max_value?: number | null };
  process_mapping?: { roles?: ScenarioRole[]; fact_key?: string | null };
  allow_unknown?: boolean;
  group?: string | null;
  group_title?: string | null;
  aliases?: string[];
};
export type ScenarioTransition = { to: string; when?: ScenarioCondition | null; priority?: number | null };
type BlockBase = { id: string; title: string; transitions?: ScenarioTransition[] };
export type ScenarioBlock = BlockBase & (
  | { kind: "form_page"; layout?: "single" | "group" | "section"; fields: ScenarioField[] }
  | { kind: "instruction"; content: { format?: "markdown" | "plain"; body: string }; acknowledgment_required?: boolean }
  | { kind: "decision" }
  | { kind: "resolution_check" }
  | { kind: "diagnostic"; capability?: string; require_consent?: boolean; timeout_seconds?: number; execution_mode?: "unavailable" }
  | { kind: "review" }
  | { kind: "submit_ticket" }
  | { kind: "finish"; message?: string }
);
export type ScenarioPolicyKind = "priority" | "routing" | "sla" | "ola" | "approval" | "notification" | "closure" | "visibility";
export type ScenarioDraftDefinition = {
  schema_version?: 1;
  scenario_key: string;
  service_code: string;
  offering_full_code: string;
  category_id?: string | null;
  title: string;
  description?: string;
  publish_offering?: boolean;
  entry_block_id?: string | null;
  blocks?: ScenarioBlock[];
  process_binding: { request_template_key: string; priority_source?: "existing_server_policy_runtime"; policy_refs?: Partial<Record<ScenarioPolicyKind, string>> };
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
};
