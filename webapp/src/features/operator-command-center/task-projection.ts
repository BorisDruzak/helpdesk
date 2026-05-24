import type { CommandCenterItem, CommandCenterSection, CommandCenterSeverity } from "./api";

export type SupportActionTaskType =
  | "triage_unassigned"
  | "reply_user"
  | "sla_rescue"
  | "ola_rescue"
  | "operator_next_action"
  | "approval_followup"
  | "consent_waiting"
  | "operation_failed"
  | "diagnostics_needed"
  | "agent_offline"
  | "closure_blocker"
  | "similar_spike";

export type SupportActionTask = {
  id: string;
  ticketId: string;
  ticketNumber?: string | null;
  title: string;
  taskType: SupportActionTaskType;
  actionLabel: string;
  severity: CommandCenterSeverity;
  status: string;
  priority?: string | null;
  queue?: string | null;
  assignee?: string | null;
  requesterName?: string | null;
  serviceCode?: string | null;
  offeringCode?: string | null;
  dueAt?: string | null;
  updatedAt?: string | null;
  reason: string;
  reasonBadges: string[];
  sectionKeys: CommandCenterSection["key"][];
  sourceItems: CommandCenterItem[];
  primaryItem: CommandCenterItem;
  href: string;
  sortScore: number;
};

export type SupportActionTaskFilter = {
  taskTypes?: SupportActionTaskType[];
  sectionKeys?: CommandCenterSection["key"][];
  query?: string;
  severity?: CommandCenterSeverity | "all";
  unassignedOnly?: boolean;
};

export type KanbanActionColumnKey =
  | "intake"
  | "needs_operator"
  | "waiting"
  | "operations"
  | "closure"
  | "similar"
  | "sla";

export type KanbanActionColumn = {
  key: KanbanActionColumnKey;
  title: string;
  tasks: SupportActionTask[];
};

const SECTION_PRIORITY: Record<CommandCenterSection["key"], number> = {
  sla_risk: 10,
  ola_risk: 15,
  failed_operation: 20,
  unread_user_messages: 30,
  operator_action: 40,
  pending_consent: 50,
  pending_approval: 55,
  agent_offline_active: 60,
  diagnostics_recommended: 65,
  closure_blocked: 70,
  similar_tickets_spike: 75,
  new_unassigned: 80,
};

const TASK_TYPE_BY_SECTION: Record<CommandCenterSection["key"], SupportActionTaskType> = {
  new_unassigned: "triage_unassigned",
  operator_action: "operator_next_action",
  unread_user_messages: "reply_user",
  sla_risk: "sla_rescue",
  ola_risk: "ola_rescue",
  pending_approval: "approval_followup",
  pending_consent: "consent_waiting",
  failed_operation: "operation_failed",
  agent_offline_active: "agent_offline",
  diagnostics_recommended: "diagnostics_needed",
  closure_blocked: "closure_blocker",
  similar_tickets_spike: "similar_spike",
};

const ACTION_LABEL_BY_TYPE: Record<SupportActionTaskType, string> = {
  triage_unassigned: "Взять в работу",
  reply_user: "Ответить пользователю",
  sla_rescue: "Спасти SLA",
  ola_rescue: "Спасти OLA",
  operator_next_action: "Выполнить действие",
  approval_followup: "Проверить согласование",
  consent_waiting: "Проверить consent",
  operation_failed: "Повторить операцию",
  diagnostics_needed: "Запустить диагностику",
  agent_offline: "Проверить agent offline",
  closure_blocker: "Снять блокер закрытия",
  similar_spike: "Проверить всплеск",
};

const SEVERITY_WEIGHT: Record<CommandCenterSeverity, number> = {
  critical: -20,
  warning: -8,
  info: 0,
};

const PRIORITY_WEIGHT: Record<string, number> = {
  P0: -35,
  P1: -25,
  P2: -10,
  P3: 0,
};

type TaskSourceEntry = {
  section: CommandCenterSection;
  item: CommandCenterItem;
  score: number;
};

function taskGroupKey(sectionKey: CommandCenterSection["key"], item: CommandCenterItem) {
  if (sectionKey === "similar_tickets_spike" && item.similar_group?.group_key) {
    return `similar_spike:${item.similar_group.group_key}`;
  }
  return `ticket:${item.ticket_id}`;
}

function timerStateScore(item: CommandCenterItem) {
  const states = [item.sla?.state, item.ola?.state];
  if (states.includes("breached")) {
    return -100;
  }
  if (states.includes("risk")) {
    return -50;
  }
  return 0;
}

function dynamicSectionScore(section: CommandCenterSection, item: CommandCenterItem) {
  let score = SECTION_PRIORITY[section.key] ?? 999;
  score += SEVERITY_WEIGHT[section.severity] ?? 0;
  score += timerStateScore(item);
  if (item.operation?.status === "failed" || item.operation?.error_summary) {
    score -= 40;
  }
  if ((item.unread_user_messages ?? 0) > 0) {
    score -= 25;
  }
  score += PRIORITY_WEIGHT[String(item.priority ?? "").toUpperCase()] ?? 0;
  return score;
}

function highestSeverity(severities: CommandCenterSeverity[]): CommandCenterSeverity {
  if (severities.includes("critical")) {
    return "critical";
  }
  if (severities.includes("warning")) {
    return "warning";
  }
  return "info";
}

function getTaskDueAt(item: CommandCenterItem) {
  return item.sla?.due_at ?? item.ola?.due_at ?? item.next_action_due_at ?? null;
}

function getUpdatedAt(items: CommandCenterItem[]) {
  return items
    .map((item) => item.updated_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => right.localeCompare(left))[0] ?? null;
}

function compareEntries(left: TaskSourceEntry, right: TaskSourceEntry) {
  if (left.score !== right.score) {
    return left.score - right.score;
  }
  return SECTION_PRIORITY[left.section.key] - SECTION_PRIORITY[right.section.key];
}

function uniqueValues<T>(values: T[]) {
  return [...new Set(values)];
}

function buildTaskFromEntries(groupKey: string, entries: TaskSourceEntry[]): SupportActionTask {
  const sortedEntries = [...entries].sort(compareEntries);
  const primaryEntry = sortedEntries[0];
  const primaryItem = primaryEntry.item;
  const taskType = TASK_TYPE_BY_SECTION[primaryEntry.section.key];
  const sourceItems = entries.map((entry) => entry.item);
  const sectionKeys = uniqueValues(sortedEntries.map((entry) => entry.section.key));
  const reasonBadges = uniqueValues(sortedEntries.map((entry) => entry.section.title));
  const severity = highestSeverity(entries.map((entry) => entry.section.severity));
  const similarKey = primaryItem.similar_group?.group_key;

  return {
    id: groupKey.replace("ticket:", "").replace("similar_spike:", "similar_spike:"),
    ticketId: primaryItem.ticket_id,
    ticketNumber: primaryItem.ticket_number,
    title: primaryItem.title,
    taskType,
    actionLabel: ACTION_LABEL_BY_TYPE[taskType],
    severity,
    status: primaryItem.status,
    priority: primaryItem.priority,
    queue: primaryItem.queue,
    assignee: primaryItem.assignee,
    requesterName: primaryItem.requester_name,
    serviceCode: primaryItem.service_code,
    offeringCode: primaryItem.offering_code,
    dueAt: getTaskDueAt(primaryItem),
    updatedAt: getUpdatedAt(sourceItems),
    reason: primaryItem.reason,
    reasonBadges,
    sectionKeys,
    sourceItems,
    primaryItem,
    href:
      taskType === "similar_spike" && similarKey
        ? primaryItem.href || `/app/tickets?search=${encodeURIComponent(similarKey)}`
        : primaryItem.href,
    sortScore: primaryEntry.score,
  };
}

function compareTasks(left: SupportActionTask, right: SupportActionTask) {
  if (left.sortScore !== right.sortScore) {
    return left.sortScore - right.sortScore;
  }
  const leftUpdated = left.updatedAt ?? "";
  const rightUpdated = right.updatedAt ?? "";
  if (leftUpdated !== rightUpdated) {
    return rightUpdated.localeCompare(leftUpdated);
  }
  return left.id.localeCompare(right.id);
}

export function buildSupportActionTasks(sections: CommandCenterSection[]): SupportActionTask[] {
  const groups = new Map<string, TaskSourceEntry[]>();

  for (const section of sections) {
    for (const item of section.items) {
      const key = taskGroupKey(section.key, item);
      const entries = groups.get(key) ?? [];
      entries.push({ section, item, score: dynamicSectionScore(section, item) });
      groups.set(key, entries);
    }
  }

  return [...groups.entries()].map(([groupKey, entries]) => buildTaskFromEntries(groupKey, entries)).sort(compareTasks);
}

export function filterSupportActionTasks(tasks: SupportActionTask[], filter: SupportActionTaskFilter = {}) {
  const taskTypes = filter.taskTypes?.length ? new Set(filter.taskTypes) : null;
  const sectionKeys = filter.sectionKeys?.length ? new Set(filter.sectionKeys) : null;
  const normalizedQuery = filter.query?.trim().toLowerCase() ?? "";

  return tasks.filter((task) => {
    if (taskTypes && !taskTypes.has(task.taskType)) {
      return false;
    }
    if (sectionKeys && !task.sectionKeys.some((key) => sectionKeys.has(key))) {
      return false;
    }
    if (filter.severity && filter.severity !== "all" && task.severity !== filter.severity) {
      return false;
    }
    if (filter.unassignedOnly && task.assignee) {
      return false;
    }
    if (!normalizedQuery) {
      return true;
    }
    const haystack = [
      task.ticketNumber,
      task.ticketId,
      task.title,
      task.requesterName,
      task.queue,
      task.assignee,
      task.serviceCode,
      task.offeringCode,
      task.actionLabel,
      task.reason,
      ...task.reasonBadges,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

const KANBAN_COLUMNS: Array<{ key: KanbanActionColumnKey; title: string; types: SupportActionTaskType[] }> = [
  { key: "intake", title: "Intake", types: ["triage_unassigned"] },
  { key: "needs_operator", title: "Needs operator", types: ["reply_user", "operator_next_action"] },
  { key: "waiting", title: "Waiting / Approval", types: ["approval_followup", "consent_waiting"] },
  { key: "operations", title: "Operations / Diagnostics", types: ["operation_failed", "diagnostics_needed", "agent_offline"] },
  { key: "closure", title: "Closure", types: ["closure_blocker"] },
  { key: "similar", title: "Similar spike", types: ["similar_spike"] },
  { key: "sla", title: "SLA risk", types: ["sla_rescue", "ola_rescue"] },
];

export function groupSupportActionTasksForKanban(tasks: SupportActionTask[]): KanbanActionColumn[] {
  return KANBAN_COLUMNS.map((column) => ({
    key: column.key,
    title: column.title,
    tasks: filterSupportActionTasks(tasks, { taskTypes: column.types }),
  }));
}
