

import {type WorkflowProfileItem, type WorkflowProfileDraft, type WorkflowTransitionEntry, type WorkflowTransitionsJson} from './settings-types';
import {csvToList} from './settings-form-model';

export function listToCsv(value: string[] | undefined): string {
  return (value ?? []).join(", ");
}

export function transitionTarget(entry: WorkflowTransitionEntry): string {
  if (typeof entry === "string") {
    return entry;
  }
  return String(entry.to ?? entry.to_status ?? entry.target ?? "").trim();
}

export function normalizeTransitionRows(value: unknown): WorkflowTransitionEntry[] {
  if (Array.isArray(value)) {
    return value
      .map((entry) => {
        if (typeof entry === "string") {
          return entry.trim();
        }
        return entry && typeof entry === "object" ? ({ ...(entry as Record<string, unknown>) } as Record<string, unknown>) : "";
      })
      .filter((entry) => transitionTarget(entry).length > 0);
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([to, gate]) => (gate && typeof gate === "object" ? { to, ...(gate as Record<string, unknown>) } : to))
      .filter((entry) => transitionTarget(entry).length > 0);
  }
  return [];
}

export function parseWorkflowTransitionsJson(value: string): WorkflowTransitionsJson {
  const parsed = JSON.parse(value || "{}") as Record<string, unknown>;
  return Object.fromEntries(Object.entries(parsed).map(([from, rows]) => [from, normalizeTransitionRows(rows)]));
}

export function findTransitionBuilderDefaults(profile: WorkflowProfileItem) {
  const transitions = profile.transitions as Record<string, WorkflowTransitionEntry[]>;
  const from =
    Object.prototype.hasOwnProperty.call(transitions, "in_progress")
      ? "in_progress"
      : Object.keys(transitions)[0] ?? "new";
  const rows = normalizeTransitionRows(transitions[from]);
  const entry = rows.find((item) => transitionTarget(item) === "resolved") ?? rows[0];
  const target = transitionTarget(entry) || "resolved";
  const gate = entry && typeof entry === "object" ? entry : {};
  const actions = gate.actions && typeof gate.actions === "object" ? (gate.actions as Record<string, unknown>) : {};
  return {
    from,
    to: target,
    allowedRoles: listToCsv(Array.isArray(gate.allowed_roles) ? (gate.allowed_roles as string[]) : []),
    requiredFields: listToCsv(Array.isArray(gate.required_fields) ? (gate.required_fields as string[]) : []),
    requiredComment: String(gate.required_comment ?? ""),
    requireApproval: Boolean(gate.require_approval),
    requireEvidence: Boolean(gate.require_evidence),
    notify: listToCsv(Array.isArray(actions.notify) ? (actions.notify as string[]) : []),
    slaAction: String(actions.sla ?? ""),
    approvalAction: String(actions.approval ?? ""),
    logFields: listToCsv(Array.isArray(gate.log_fields) ? (gate.log_fields as string[]) : []),
    trigger: String(gate.trigger ?? ""),
    auto: Boolean(gate.auto),
  };
}

export function buildTransitionRuleFromDraft(draft: WorkflowProfileDraft): Record<string, unknown> {
  const rule: Record<string, unknown> = { to: draft.transition_builder_to.trim() };
  const allowedRoles = csvToList(draft.transition_builder_allowed_roles_text);
  const requiredFields = csvToList(draft.transition_builder_required_fields_text);
  const notify = csvToList(draft.transition_builder_notify_text);
  const slaAction = draft.transition_builder_sla_action.trim();
  const approvalAction = draft.transition_builder_approval_action.trim();
  const logFields = csvToList(draft.transition_builder_log_fields_text);
  if (allowedRoles.length) {
    rule.allowed_roles = allowedRoles;
  }
  if (requiredFields.length) {
    rule.required_fields = requiredFields;
  }
  if (draft.transition_builder_required_comment) {
    rule.required_comment = draft.transition_builder_required_comment;
  }
  if (draft.transition_builder_require_approval) {
    rule.require_approval = true;
  }
  if (draft.transition_builder_require_evidence) {
    rule.require_evidence = true;
  }
  if (logFields.length) {
    rule.log_fields = logFields;
  }
  if (draft.transition_builder_trigger.trim()) {
    rule.trigger = draft.transition_builder_trigger.trim();
  }
  if (draft.transition_builder_auto) {
    rule.auto = true;
  }
  const actions: Record<string, unknown> = {};
  if (notify.length) {
    actions.notify = notify;
  }
  if (slaAction) {
    actions.sla = slaAction;
  }
  if (approvalAction) {
    actions.approval = approvalAction;
  }
  if (Object.keys(actions).length) {
    rule.actions = actions;
  }
  return rule;
}

export function applyWorkflowTransitionRule(profile: WorkflowProfileDraft): WorkflowProfileDraft {
  const from = profile.transition_builder_from.trim();
  const to = profile.transition_builder_to.trim();
  if (!from || !to) {
    return profile;
  }
  const transitions = parseWorkflowTransitionsJson(profile.transitions_json);
  const rule = buildTransitionRuleFromDraft(profile);
  const rows = normalizeTransitionRows(transitions[from]);
  let replaced = false;
  const nextRows = rows.map((entry) => {
    if (transitionTarget(entry) !== to) {
      return entry;
    }
    replaced = true;
    return rule;
  });
  if (!replaced) {
    nextRows.push(rule);
  }
  transitions[from] = nextRows;
  return {
    ...profile,
    transitions_json: JSON.stringify(transitions, null, 2),
  };
}

export function buildWorkflowProfileDraft(profile: WorkflowProfileItem): WorkflowProfileDraft {
  const builder = findTransitionBuilderDefaults(profile);
  return {
    ticket_type: profile.ticket_type,
    label: profile.label,
    purpose: profile.purpose,
    requires_approval: profile.requires_approval,
    requires_change_plan: profile.requires_change_plan,
    requires_action_log: profile.requires_action_log,
    suggested_path_text: listToCsv(profile.suggested_path),
    allowed_statuses_text: listToCsv(profile.allowed_statuses),
    required_create_fields_text: listToCsv(profile.required_create_fields),
    required_resolve_fields_text: listToCsv(profile.required_resolve_fields),
    evidence_required_for_priorities_text: listToCsv(profile.evidence_required_for_priorities),
    transitions_json: JSON.stringify(profile.transitions ?? {}, null, 2),
    transition_builder_from: builder.from,
    transition_builder_to: builder.to,
    transition_builder_allowed_roles_text: builder.allowedRoles,
    transition_builder_required_fields_text: builder.requiredFields,
    transition_builder_required_comment: builder.requiredComment,
    transition_builder_require_approval: builder.requireApproval,
    transition_builder_require_evidence: builder.requireEvidence,
    transition_builder_notify_text: builder.notify,
    transition_builder_sla_action: builder.slaAction,
    transition_builder_approval_action: builder.approvalAction,
    transition_builder_log_fields_text: builder.logFields,
    transition_builder_trigger: builder.trigger,
    transition_builder_auto: builder.auto,
  };
}

export function buildWorkflowProfilePayload(drafts: WorkflowProfileDraft[]): WorkflowProfileItem[] {
  return drafts.map((draft) => ({
    ticket_type: draft.ticket_type.trim(),
    label: draft.label.trim() || draft.ticket_type.trim(),
    purpose: draft.purpose.trim() || draft.ticket_type.trim(),
    suggested_path: csvToList(draft.suggested_path_text),
    allowed_statuses: csvToList(draft.allowed_statuses_text),
    required_create_fields: csvToList(draft.required_create_fields_text),
    required_resolve_fields: csvToList(draft.required_resolve_fields_text),
    requires_approval: draft.requires_approval,
    requires_change_plan: draft.requires_change_plan,
    requires_action_log: draft.requires_action_log,
    evidence_required_for_priorities: csvToList(draft.evidence_required_for_priorities_text),
    transitions: parseWorkflowTransitionsJson(draft.transitions_json),
  }));
}

export function createWorkflowProfileDraft(index: number): WorkflowProfileDraft {
  return {
    ticket_type: `custom_${index}`,
    label: "New ticket type",
    purpose: "custom_process",
    requires_approval: false,
    requires_change_plan: false,
    requires_action_log: false,
    suggested_path_text: "new, queued, in_progress, resolved, closed",
    allowed_statuses_text:
      "new, queued, assigned, in_progress, waiting_on_user, waiting_on_internal_team, waiting_on_vendor, waiting_on_approval, scheduled, resolved, closed, canceled",
    required_create_fields_text: "",
    required_resolve_fields_text: "public_summary",
    evidence_required_for_priorities_text: "",
    transitions_json: JSON.stringify(
      {
        new: ["queued", "canceled"],
        queued: ["assigned", "in_progress", "canceled"],
        assigned: ["in_progress", "canceled"],
        in_progress: ["resolved", "canceled"],
        resolved: ["closed"],
        closed: [],
        canceled: [],
      },
      null,
      2
    ),
    transition_builder_from: "in_progress",
    transition_builder_to: "resolved",
    transition_builder_allowed_roles_text: "",
    transition_builder_required_fields_text: "resolution_code",
    transition_builder_required_comment: "public",
    transition_builder_require_approval: false,
    transition_builder_require_evidence: false,
    transition_builder_notify_text: "",
    transition_builder_sla_action: "",
    transition_builder_approval_action: "",
    transition_builder_log_fields_text: "",
    transition_builder_trigger: "",
    transition_builder_auto: false,
  };
}

export function formatBooleanFlag(value: boolean): string {
  return value ? "Включено" : "Выключено";
}

export function validDurationRows<T extends {priority: string}>(rows: T[], first: keyof T, second: keyof T) {
  return rows.filter(row => row[first] != null || row[second] != null).map(row => {
    if (row[first] == null || row[second] == null || !Number.isSafeInteger(row[first]) || !Number.isSafeInteger(row[second]) || Number(row[first]) <= 0 || Number(row[second]) <= 0) {
      throw new Error(`${row.priority}: укажите оба срока больше нуля или оставьте оба пустыми.`);
    }
    return row as T & Record<typeof first | typeof second, number>;
  });
}
