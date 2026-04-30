import { AlertTriangle, Bell, CheckCircle2, GitBranch, Plus, RefreshCcw, ShieldCheck, Trash2, Workflow } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { startTransition, useEffect, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import {
  createWebSettingsCalendar,
  createWebSettingsQueue,
  createWebSettingsResolutionCode,
  createWebSettingsRoutingRule,
  createWebSettingsSlaPolicy,
  deleteWebSettingsQueueMember,
  deleteWebSettingsResolutionCode,
  fetchNotifications,
  fetchNotificationSettings,
  fetchTechAlerts,
  fetchWebSettingsPayload,
  saveNotificationPreferences,
  saveWebSettingsWorkflowProfiles,
  saveWebSettingsOlaTargets,
  saveWebSettingsPriorityMatrix,
  saveWebSettingsSlaTargets,
  setWebSettingsDefaultSlaPolicy,
  updateWebSettingsCalendar,
  updateWebSettingsQueue,
  updateWebSettingsResolutionCode,
  updateWebSettingsRoutingRule,
  updateWebSettingsSlaPolicy,
  upsertWebSettingsQueueMember,
  type WebSettingsPayload,
} from "../../features/settings/api";
import { getTicketStageLabel, getTicketStageTone } from "../../features/tickets/status-presentation";


type SettingsTab =
  | "overview"
  | "tickets"
  | "notifications"
  | "queues"
  | "routing"
  | "sla"
  | "calendars"
  | "resolution"
  | "audit";
type QueueItem = WebSettingsPayload["queues"][number];
type RoutingRuleItem = WebSettingsPayload["routing_rules"][number];
type SlaPolicyItem = WebSettingsPayload["sla_policies"][number];
type CalendarItem = WebSettingsPayload["calendars"][number];
type ResolutionCodeItem = WebSettingsPayload["resolution_codes"][number];

type ActionFeedback =
  | {
      tone: "error" | "success";
      text: string;
    }
  | null;

type QueueDraft = {
  code: string;
  name: string;
  is_triage: boolean;
  is_active: boolean;
  auto_assign_enabled: boolean;
};

type RoutingDraft = {
  enabled: boolean;
  priority_order: number;
  target_queue_id: number;
};

type RoutingConditionBuilder = {
  field: string;
  op: string;
  value_text: string;
  null_state: "true" | "false";
};

type PolicyDraft = {
  name: string;
  timezone: string;
  calendar_id: string;
  is_default: boolean;
  is_active: boolean;
  business_hours_mode: "calendar" | "always_on";
};

type CalendarDayDraft = {
  day: number;
  enabled: boolean;
  start: string;
  end: string;
};

type CalendarHolidayDraft = {
  id: string;
  date: string;
};

type CalendarDraft = {
  code: string;
  name: string;
  timezone: string;
  is_active: boolean;
  weekly_hours: CalendarDayDraft[];
  holidays: CalendarHolidayDraft[];
};

type ResolutionDraft = {
  code: string;
  name: string;
  is_active: boolean;
  sort_order: number;
};

type OlaDraftRow = {
  priority: string;
  ack_min: number;
  processing_min: number;
};

type SlaTargetDraftRow = {
  priority: string;
  first_response_min: number;
  resolution_min: number;
};

type PriorityMatrixDraftRow = {
  impact: number;
  urgency: number;
  priority: string;
};

type WorkflowProfileItem = WebSettingsPayload["ticket_settings"]["workflow_profiles"][number];

type WorkflowProfileDraft = Omit<
  WorkflowProfileItem,
  | "suggested_path"
  | "allowed_statuses"
  | "required_create_fields"
  | "required_resolve_fields"
  | "evidence_required_for_priorities"
  | "transitions"
> & {
  suggested_path_text: string;
  allowed_statuses_text: string;
  required_create_fields_text: string;
  required_resolve_fields_text: string;
  evidence_required_for_priorities_text: string;
  transitions_json: string;
};

const TAB_ITEMS = [
  { value: "overview", label: "Обзор" },
  { value: "tickets", label: "Тикеты" },
  { value: "notifications", label: "Уведомления" },
  { value: "queues", label: "Очереди" },
  { value: "routing", label: "Маршрутизация" },
  { value: "sla", label: "Сроки" },
  { value: "calendars", label: "Календари" },
  { value: "resolution", label: "Коды решения" },
  { value: "audit", label: "Аудит" },
] as const;

const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;
const PRIORITY_OPTIONS = ["P0", "P1", "P2", "P3"] as const;
const IMPACT_VALUES = [0, 1, 2, 3] as const;
const CALENDAR_DAYS = [
  { day: 0, key: "mon", label: "Пн" },
  { day: 1, key: "tue", label: "Вт" },
  { day: 2, key: "wed", label: "Ср" },
  { day: 3, key: "thu", label: "Чт" },
  { day: 4, key: "fri", label: "Пт" },
  { day: 5, key: "sat", label: "Сб" },
  { day: 6, key: "sun", label: "Вс" },
] as const;
const NOTIFICATION_CATALOG = [
  {
    eventType: "ticket_message",
    title: "Новые сообщения в тикетах",
    description: "Оператор или пользователь добавил публичное сообщение.",
  },
  {
    eventType: "internal_note",
    title: "Внутренние комментарии",
    description: "Служебные заметки поддержки; можно заглушить отдельным переключателем.",
  },
  {
    eventType: "status_changed",
    title: "Изменение статуса",
    description: "Тикет перешёл в работу, ожидание, решение или закрытие.",
  },
  {
    eventType: "assignment_changed",
    title: "Назначение исполнителя",
    description: "Тикет назначен на пользователя или очередь.",
  },
  {
    eventType: "sla_breached",
    title: "Срок ответа или решения нарушен",
    description: "Watchdog создал уведомление о просрочке реакции или решения.",
  },
  {
    eventType: "mention",
    title: "Упоминания",
    description: "Адресные события, которые лучше оставлять включёнными.",
  },
] as const;

const TECH_ALERT_CATALOG = [
  "connection_request_stuck_pending",
  "connection_request_token_limit",
  "agent_update_failed",
  "observer_degradation",
  "inventory_duplicate_env_uuid",
] as const;


function formatDateTime(value: string | null | undefined): string {
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


function prettyJson(value: unknown): string {
  if (!value) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}


function readBusinessHoursMode(value: Record<string, unknown> | null | undefined): PolicyDraft["business_hours_mode"] {
  return value?.mode === "calendar" ? "calendar" : "always_on";
}


function buildBusinessHoursJson(mode: PolicyDraft["business_hours_mode"]): Record<string, unknown> | null {
  return mode === "calendar" ? { mode: "calendar" } : null;
}


function defaultCalendarHours(): CalendarDayDraft[] {
  return CALENDAR_DAYS.map((item) => ({
    day: item.day,
    enabled: item.day < 5,
    start: "09:00",
    end: "18:00",
  }));
}


function dayIndexFromKey(value: string): number | null {
  const normalized = value.toLowerCase().slice(0, 3);
  const found = CALENDAR_DAYS.find((item) => item.key === normalized);
  return found?.day ?? null;
}


function readCalendarHours(value: unknown): CalendarDayDraft[] {
  const rows = defaultCalendarHours().map((row) => ({ ...row, enabled: false }));
  const applySlot = (day: number | null, start: unknown, end: unknown) => {
    if (day == null || day < 0 || day > 6) {
      return;
    }
    rows[day] = {
      day,
      enabled: true,
      start: String(start ?? "09:00"),
      end: String(end ?? "18:00"),
    };
  };

  if (Array.isArray(value)) {
    for (const slot of value) {
      if (!slot || typeof slot !== "object") {
        continue;
      }
      const item = slot as Record<string, unknown>;
      const rawDay = item.day;
      const day = typeof rawDay === "number" ? rawDay : typeof rawDay === "string" ? dayIndexFromKey(rawDay) : null;
      applySlot(day, item.start, item.end);
    }
    return rows;
  }

  if (value && typeof value === "object") {
    for (const [key, ranges] of Object.entries(value as Record<string, unknown>)) {
      const day = dayIndexFromKey(key);
      const firstRange = Array.isArray(ranges) ? ranges[0] : null;
      if (Array.isArray(firstRange)) {
        applySlot(day, firstRange[0], firstRange[1]);
      }
    }
    return rows;
  }

  return defaultCalendarHours();
}


function buildCalendarHoursJson(rows: CalendarDayDraft[]): Record<string, unknown> {
  return Object.fromEntries(
    rows
      .filter((row) => row.enabled)
      .map((row) => {
        const dayKey = CALENDAR_DAYS.find((item) => item.day === row.day)?.key ?? String(row.day);
        return [dayKey, [[row.start || "09:00", row.end || "18:00"]]];
      }),
  );
}


function createHolidayDraft(date = "", index = 0): CalendarHolidayDraft {
  return {
    id: `${date || "new"}:${index}:${Math.random().toString(16).slice(2)}`,
    date,
  };
}


function readHolidayRows(value: unknown): CalendarHolidayDraft[] {
  const fromDates = (dates: unknown[]) =>
    dates
      .map((item, index) => createHolidayDraft(String(item ?? "").trim(), index))
      .filter((item) => item.date);

  if (Array.isArray(value)) {
    return fromDates(value);
  }
  if (value && typeof value === "object") {
    const source = value as Record<string, unknown>;
    const dates = source.dates ?? source.holidays ?? source.items;
    if (Array.isArray(dates)) {
      return fromDates(dates.map((item) => (item && typeof item === "object" ? (item as Record<string, unknown>).date : item)));
    }
  }
  return [];
}


function buildHolidaysJson(rows: CalendarHolidayDraft[]): Record<string, unknown> {
  return {
    dates: rows
      .map((item) => item.date.trim())
      .filter(Boolean),
  };
}


function buildQueueDraft(queue: QueueItem | null): QueueDraft {
  return {
    code: queue?.code ?? "",
    name: queue?.name ?? "",
    is_triage: queue?.is_triage ?? false,
    is_active: queue?.is_active ?? true,
    auto_assign_enabled: queue?.auto_assign_enabled ?? true,
  };
}


function buildRoutingDraft(rule: RoutingRuleItem | null, fallbackQueueId: number | null): RoutingDraft {
  return {
    enabled: rule?.enabled ?? true,
    priority_order: rule?.priority_order ?? 100,
    target_queue_id: rule?.target_queue_id ?? fallbackQueueId ?? 0,
  };
}


function isLeafRoutingCondition(value: Record<string, unknown> | null | undefined): value is {
  field: string;
  op: string;
  value: unknown;
} {
  return Boolean(
    value &&
      typeof value.field === "string" &&
      typeof value.op === "string" &&
      Object.prototype.hasOwnProperty.call(value, "value")
  );
}


function buildRoutingConditionBuilder(
  condition: Record<string, unknown> | null | undefined,
  fallbackField: string
): RoutingConditionBuilder {
  if (!isLeafRoutingCondition(condition)) {
    return {
      field: fallbackField,
      op: "eq",
      value_text: "",
      null_state: "true",
    };
  }
  const op = condition.op;
  if (op === "in" || op === "nin") {
    return {
      field: condition.field,
      op,
      value_text: Array.isArray(condition.value) ? condition.value.map((item) => String(item ?? "")).join(", ") : "",
      null_state: "true",
    };
  }
  if (op === "is_null") {
    return {
      field: condition.field,
      op,
      value_text: "",
      null_state: condition.value === false ? "false" : "true",
    };
  }
  return {
    field: condition.field,
    op,
    value_text: condition.value == null ? "" : String(condition.value),
    null_state: "true",
  };
}


function buildRoutingConditionJson(builder: RoutingConditionBuilder): Record<string, unknown> {
  const field = builder.field.trim();
  const op = builder.op.trim() || "eq";
  if (!field) {
    return {};
  }
  if (op === "in" || op === "nin") {
    return {
      field,
      op,
      value: builder.value_text
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    };
  }
  if (op === "is_null") {
    return {
      field,
      op,
      value: builder.null_state === "true",
    };
  }
  return {
    field,
    op,
    value: builder.value_text.trim(),
  };
}


function buildPolicyDraft(policy: SlaPolicyItem | null): PolicyDraft {
  return {
    name: policy?.name ?? "",
    timezone: policy?.timezone ?? "UTC",
    calendar_id: policy?.calendar_id ? String(policy.calendar_id) : "",
    is_default: policy?.is_default ?? false,
    is_active: policy?.is_active ?? true,
    business_hours_mode: readBusinessHoursMode(policy?.business_hours_json),
  };
}


function buildCalendarDraft(calendar: CalendarItem | null): CalendarDraft {
  return {
    code: calendar?.code ?? "",
    name: calendar?.name ?? "",
    timezone: calendar?.timezone ?? "UTC",
    is_active: calendar?.is_active ?? true,
    weekly_hours: readCalendarHours(calendar?.weekly_hours_json),
    holidays: readHolidayRows(calendar?.holidays_json),
  };
}


function buildResolutionDraft(code: ResolutionCodeItem | null): ResolutionDraft {
  return {
    code: code?.code ?? "",
    name: code?.name ?? "",
    is_active: code?.is_active ?? true,
    sort_order: code?.sort_order ?? 0,
  };
}


function buildOlaDraft(queue: QueueItem | null): OlaDraftRow[] {
  return PRIORITIES.map((priority) => {
    const existing = queue?.ola_targets.find((item) => item.priority === priority);
    return {
      priority,
      ack_min: existing?.ack_min ?? 0,
      processing_min: existing?.processing_min ?? 0,
    };
  });
}


function buildSlaTargetsDraft(policy: SlaPolicyItem | null): SlaTargetDraftRow[] {
  return PRIORITIES.map((priority) => {
    const existing = policy?.targets.find((item) => item.priority === priority);
    return {
      priority,
      first_response_min: existing?.first_response_min ?? 0,
      resolution_min: existing?.resolution_min ?? 0,
    };
  });
}


function buildPriorityMatrixDraft(policy: SlaPolicyItem | null): PriorityMatrixDraftRow[] {
  return IMPACT_VALUES.flatMap((impact) =>
    IMPACT_VALUES.map((urgency) => {
      const existing = policy?.priority_matrix.find((item) => item.impact === impact && item.urgency === urgency);
      return {
        impact,
        urgency,
        priority: existing?.priority ?? "P3",
      };
    })
  );
}


function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}


function listToCsv(value: string[] | undefined): string {
  return (value ?? []).join(", ");
}


function buildWorkflowProfileDraft(profile: WorkflowProfileItem): WorkflowProfileDraft {
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
  };
}


function buildWorkflowProfilePayload(drafts: WorkflowProfileDraft[]): WorkflowProfileItem[] {
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
    transitions: JSON.parse(draft.transitions_json || "{}") as Record<string, string[]>,
  }));
}


function createWorkflowProfileDraft(index: number): WorkflowProfileDraft {
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
  };
}


function SettingsField({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <label className="space-y-2 text-sm font-medium text-slate-800">
      <span>{label}</span>
      {children}
    </label>
  );
}


function PermissionNotice({ text }: { text: string | null }) {
  if (!text) {
    return null;
  }
  return (
    <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
      {text}
    </div>
  );
}


function formatBooleanFlag(value: boolean): string {
  return value ? "Включено" : "Выключено";
}


export function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SettingsTab>("overview");
  const [feedback, setFeedback] = useState<ActionFeedback>(null);

  const settingsQuery = useQuery({
    queryKey: ["web-settings"],
    queryFn: fetchWebSettingsPayload,
    retry: false,
    refetchInterval: 60_000,
  });

  const notificationSettingsQuery = useQuery({
    queryKey: ["notification-settings"],
    queryFn: fetchNotificationSettings,
    enabled: activeTab === "notifications",
    retry: false,
  });

  const notificationsQuery = useQuery({
    queryKey: ["notifications-preview"],
    queryFn: () => fetchNotifications(20),
    enabled: activeTab === "notifications",
    retry: false,
    refetchInterval: 30_000,
  });

  const techAlertsQuery = useQuery({
    queryKey: ["admin-tech-alerts-settings"],
    queryFn: fetchTechAlerts,
    enabled: activeTab === "notifications",
    retry: false,
    refetchInterval: 30_000,
  });

  const payload = settingsQuery.data;
  const canWrite = payload?.capabilities.can_write ?? false;
  const canManageQueues = payload?.capabilities.can_manage_queues ?? canWrite;
  const canManageRouting = payload?.capabilities.can_manage_routing ?? canWrite;
  const queueDeniedReason =
    canManageQueues ? null : payload?.capabilities.manage_queues_denial_reason ?? "Недостаточно прав: settings.manage_queues";
  const routingDeniedReason =
    canManageRouting ? null : payload?.capabilities.manage_routing_denial_reason ?? "Недостаточно прав: settings.manage_routing";

  const [selectedQueueId, setSelectedQueueId] = useState<number | null>(null);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null);
  const [selectedCalendarId, setSelectedCalendarId] = useState<number | null>(null);
  const [selectedResolutionCode, setSelectedResolutionCode] = useState<string | null>(null);

  const selectedQueue = payload?.queues.find((item) => item.id === selectedQueueId) ?? payload?.queues[0] ?? null;
  const selectedRule =
    selectedRuleId === -1
      ? null
      : payload?.routing_rules.find((item) => item.id === selectedRuleId) ?? null;
  const selectedPolicy = payload?.sla_policies.find((item) => item.id === selectedPolicyId) ?? payload?.sla_policies[0] ?? null;
  const selectedCalendar = payload?.calendars.find((item) => item.id === selectedCalendarId) ?? payload?.calendars[0] ?? null;
  const selectedResolution = payload?.resolution_codes.find((item) => item.code === selectedResolutionCode) ?? payload?.resolution_codes[0] ?? null;

  const [queueDraft, setQueueDraft] = useState<QueueDraft>(buildQueueDraft(null));
  const [routingDraft, setRoutingDraft] = useState<RoutingDraft>(buildRoutingDraft(null, null));
  const [routingConditionBuilder, setRoutingConditionBuilder] = useState<RoutingConditionBuilder>({
    field: "request_kind",
    op: "eq",
    value_text: "access",
    null_state: "true",
  });
  const [policyDraft, setPolicyDraft] = useState<PolicyDraft>(buildPolicyDraft(null));
  const [calendarDraft, setCalendarDraft] = useState<CalendarDraft>(buildCalendarDraft(null));
  const [resolutionDraft, setResolutionDraft] = useState<ResolutionDraft>(buildResolutionDraft(null));
  const [olaDraft, setOlaDraft] = useState<OlaDraftRow[]>(buildOlaDraft(null));
  const [slaTargetsDraft, setSlaTargetsDraft] = useState<SlaTargetDraftRow[]>(buildSlaTargetsDraft(null));
  const [priorityMatrixDraft, setPriorityMatrixDraft] = useState<PriorityMatrixDraftRow[]>(buildPriorityMatrixDraft(null));
  const [workflowProfileDrafts, setWorkflowProfileDrafts] = useState<WorkflowProfileDraft[]>([]);
  const [newMemberActorId, setNewMemberActorId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("");

  const notificationPreferences = notificationSettingsQuery.data?.preferences;
  const mutedNotificationTypes = notificationPreferences?.muted_event_types ?? [];

  const notificationMutation = useMutation({
    mutationFn: saveNotificationPreferences,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-settings"] });
      reportSuccess("Настройки уведомлений сохранены.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить настройки уведомлений."),
  });

  function toggleMutedNotification(eventType: string, checked: boolean) {
    const current = new Set(mutedNotificationTypes);
    if (checked) {
      current.delete(eventType);
    } else {
      current.add(eventType);
    }
    notificationMutation.mutate({
      muted_event_types: Array.from(current),
    });
  }

  useEffect(() => {
    if (!payload?.queues.length) {
      setSelectedQueueId(null);
      return;
    }
    if (!selectedQueueId || !payload.queues.some((item) => item.id === selectedQueueId)) {
      setSelectedQueueId(payload.queues[0].id);
    }
  }, [payload?.queues, selectedQueueId]);

  useEffect(() => {
    if (!payload?.routing_rules.length) {
      setSelectedRuleId(null);
      return;
    }
    if (selectedRuleId == null) {
      setSelectedRuleId(payload.routing_rules[0].id);
      return;
    }
    if (selectedRuleId !== -1 && !payload.routing_rules.some((item) => item.id === selectedRuleId)) {
      setSelectedRuleId(payload.routing_rules[0].id);
    }
  }, [payload?.routing_rules, selectedRuleId]);

  useEffect(() => {
    if (!payload?.sla_policies.length) {
      setSelectedPolicyId(null);
      return;
    }
    if (!selectedPolicyId || !payload.sla_policies.some((item) => item.id === selectedPolicyId)) {
      setSelectedPolicyId(payload.sla_policies[0].id);
    }
  }, [payload?.sla_policies, selectedPolicyId]);

  useEffect(() => {
    if (!payload?.calendars.length) {
      setSelectedCalendarId(null);
      return;
    }
    if (!selectedCalendarId || !payload.calendars.some((item) => item.id === selectedCalendarId)) {
      setSelectedCalendarId(payload.calendars[0].id);
    }
  }, [payload?.calendars, selectedCalendarId]);

  useEffect(() => {
    if (!payload?.resolution_codes.length) {
      setSelectedResolutionCode(null);
      return;
    }
    if (!selectedResolutionCode || !payload.resolution_codes.some((item) => item.code === selectedResolutionCode)) {
      setSelectedResolutionCode(payload.resolution_codes[0].code);
    }
  }, [payload?.resolution_codes, selectedResolutionCode]);

  useEffect(() => {
    setQueueDraft(buildQueueDraft(selectedQueue));
    setOlaDraft(buildOlaDraft(selectedQueue));
  }, [selectedQueue]);

  useEffect(() => {
    setRoutingDraft(buildRoutingDraft(selectedRule, payload?.queues[0]?.id ?? null));
    setRoutingConditionBuilder(
      buildRoutingConditionBuilder(
        (selectedRule?.condition_json as Record<string, unknown> | null | undefined) ?? null,
        payload?.routing_builder.fields[0]?.field ?? "request_kind"
      )
    );
  }, [payload?.queues, payload?.routing_builder.fields, selectedRule]);

  useEffect(() => {
    setPolicyDraft(buildPolicyDraft(selectedPolicy));
    setSlaTargetsDraft(buildSlaTargetsDraft(selectedPolicy));
    setPriorityMatrixDraft(buildPriorityMatrixDraft(selectedPolicy));
  }, [selectedPolicy]);

  useEffect(() => {
    setCalendarDraft(buildCalendarDraft(selectedCalendar));
  }, [selectedCalendar]);

  useEffect(() => {
    setResolutionDraft(buildResolutionDraft(selectedResolution));
  }, [selectedResolution]);

  useEffect(() => {
    if (!payload?.ticket_settings.workflow_profiles) {
      setWorkflowProfileDrafts([]);
      return;
    }
    setWorkflowProfileDrafts(payload.ticket_settings.workflow_profiles.map(buildWorkflowProfileDraft));
  }, [payload?.ticket_settings.workflow_profiles]);

  function reportError(error: unknown, fallback: string) {
    setFeedback({
      tone: "error",
      text: error instanceof Error ? error.message : fallback,
    });
  }

  function reportSuccess(text: string) {
    setFeedback({
      tone: "success",
      text,
    });
  }

  async function refreshSettings(text?: string) {
    await queryClient.invalidateQueries({ queryKey: ["web-settings"] });
    if (text) {
      reportSuccess(text);
    }
  }

  const workflowProfilesMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      const profiles = buildWorkflowProfilePayload(workflowProfileDrafts);
      if (!profiles.length) {
        throw new Error("Нужен хотя бы один workflow profile.");
      }
      const ticketTypes = new Set<string>();
      for (const profile of profiles) {
        if (!profile.ticket_type) {
          throw new Error("ticket_type не может быть пустым.");
        }
        if (ticketTypes.has(profile.ticket_type)) {
          throw new Error(`ticket_type дублируется: ${profile.ticket_type}`);
        }
        ticketTypes.add(profile.ticket_type);
      }
      await saveWebSettingsWorkflowProfiles(profiles);
    },
    onSuccess: async () => refreshSettings("Профили процесса сохранены."),
    onError: (error) => reportError(error, "Не удалось сохранить профили процесса."),
  });

  const queueMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!queueDraft.code.trim() || !queueDraft.name.trim()) {
        throw new Error("Для очереди нужны code и name.");
      }
      if (selectedQueue) {
        await updateWebSettingsQueue(selectedQueue.id, queueDraft);
        return { created: false, id: selectedQueue.id };
      }
      const result = await createWebSettingsQueue({
        code: queueDraft.code.trim(),
        name: queueDraft.name.trim(),
        is_triage: queueDraft.is_triage,
        auto_assign_enabled: queueDraft.auto_assign_enabled,
      });
      return { created: true, id: result.queue.id };
    },
    onSuccess: async (result) => {
      if (result.created) {
        setSelectedQueueId(result.id);
      }
      await refreshSettings("Настройки очереди сохранены.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить очередь."),
  });

  const memberMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      if (!newMemberActorId.trim()) {
        throw new Error("Укажите actor_id участника очереди.");
      }
      await upsertWebSettingsQueueMember(selectedQueue.id, newMemberActorId.trim(), {
        role_in_queue: newMemberRole.trim() || null,
      });
    },
    onSuccess: async () => {
      setNewMemberActorId("");
      setNewMemberRole("");
      await refreshSettings("Участник очереди обновлён.");
    },
    onError: (error) => reportError(error, "Не удалось обновить участника очереди."),
  });

  const removeMemberMutation = useMutation({
    mutationFn: async (actorId: string) => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      await deleteWebSettingsQueueMember(selectedQueue.id, actorId);
    },
    onSuccess: async () => {
      await refreshSettings("Участник очереди удалён.");
    },
    onError: (error) => reportError(error, "Не удалось удалить участника очереди."),
  });

  const olaMutation = useMutation({
    mutationFn: async () => {
      if (!canManageQueues) {
        throw new Error(queueDeniedReason ?? "Недостаточно прав: settings.manage_queues");
      }
      if (!selectedQueue) {
        throw new Error("Сначала выберите очередь.");
      }
      await saveWebSettingsOlaTargets(selectedQueue.id, olaDraft);
    },
    onSuccess: async () => {
      await refreshSettings("Внутренние сроки очереди сохранены.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить внутренние сроки очереди."),
  });

  const routingMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!routingDraft.target_queue_id) {
        throw new Error("Для правила нужно выбрать целевую очередь.");
      }
      const conditionJson = buildRoutingConditionJson(routingConditionBuilder);
      const payloadToSave = {
        enabled: routingDraft.enabled,
        priority_order: Number(routingDraft.priority_order),
        target_queue_id: Number(routingDraft.target_queue_id),
        condition_json: conditionJson,
      };
      if (selectedRule) {
        await updateWebSettingsRoutingRule(selectedRule.id, payloadToSave);
        return { created: false, id: selectedRule.id };
      }
      const result = await createWebSettingsRoutingRule(payloadToSave);
      return { created: true, id: result.routing_rule.id };
    },
    onSuccess: async (result) => {
      if (result.created) {
        setSelectedRuleId(result.id);
      }
      await refreshSettings("Правило маршрутизации сохранено.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить правило маршрутизации."),
  });

  const policyMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!policyDraft.name.trim()) {
        throw new Error("У политики сроков должно быть имя.");
      }
      const payloadToSave = {
        name: policyDraft.name.trim(),
        timezone: policyDraft.timezone.trim() || "UTC",
        business_hours_json: buildBusinessHoursJson(policyDraft.business_hours_mode),
        calendar_id: policyDraft.calendar_id ? Number(policyDraft.calendar_id) : null,
        is_default: policyDraft.is_default,
        ...(selectedPolicy ? { is_active: policyDraft.is_active } : {}),
      };
      if (selectedPolicy) {
        await updateWebSettingsSlaPolicy(selectedPolicy.id, payloadToSave);
        if (policyDraft.is_default && !selectedPolicy.is_default) {
          await setWebSettingsDefaultSlaPolicy(selectedPolicy.id);
        }
        return { created: false, id: selectedPolicy.id };
      }
      const result = await createWebSettingsSlaPolicy(payloadToSave);
      return { created: true, id: result.sla_policy.id };
    },
    onSuccess: async (result) => {
      if (result.created) {
        setSelectedPolicyId(result.id);
      }
      await refreshSettings("Политика сроков сохранена.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить политику сроков."),
  });

  const slaTargetsMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedPolicy) {
        throw new Error("Сначала выберите политику сроков.");
      }
      await saveWebSettingsSlaTargets(selectedPolicy.id, slaTargetsDraft);
    },
    onSuccess: async () => {
      await refreshSettings("Сроки ответа и решения сохранены.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить сроки ответа и решения."),
  });

  const priorityMatrixMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedPolicy) {
        throw new Error("Сначала выберите политику сроков.");
      }
      await saveWebSettingsPriorityMatrix(selectedPolicy.id, priorityMatrixDraft);
    },
    onSuccess: async () => {
      await refreshSettings("Матрица приоритетов сохранена.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить матрицу приоритетов."),
  });

  const calendarMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!calendarDraft.code.trim() || !calendarDraft.name.trim()) {
        throw new Error("Для календаря нужны code и name.");
      }
      const payloadToSave = {
        code: calendarDraft.code.trim(),
        name: calendarDraft.name.trim(),
        timezone: calendarDraft.timezone.trim() || "UTC",
        weekly_hours_json: buildCalendarHoursJson(calendarDraft.weekly_hours),
        holidays_json: buildHolidaysJson(calendarDraft.holidays),
        ...(selectedCalendar ? { is_active: calendarDraft.is_active } : {}),
      };
      if (selectedCalendar) {
        await updateWebSettingsCalendar(selectedCalendar.id, payloadToSave);
        return { created: false, id: selectedCalendar.id };
      }
      const result = await createWebSettingsCalendar(payloadToSave);
      return { created: true, id: result.calendar.id };
    },
    onSuccess: async (result) => {
      if (result.created) {
        setSelectedCalendarId(result.id);
      }
      await refreshSettings("Календарь сохранён.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить календарь."),
  });

  const resolutionMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!resolutionDraft.code.trim() || !resolutionDraft.name.trim()) {
        throw new Error("Для кода решения нужны code и name.");
      }
      const payloadToSave = {
        name: resolutionDraft.name.trim(),
        is_active: resolutionDraft.is_active,
        sort_order: Number(resolutionDraft.sort_order),
      };
      if (selectedResolution) {
        await updateWebSettingsResolutionCode(selectedResolution.code, payloadToSave);
        return { created: false, code: selectedResolution.code };
      }
      const result = await createWebSettingsResolutionCode({
        code: resolutionDraft.code.trim(),
        ...payloadToSave,
      });
      return { created: true, code: result.resolution_code.code };
    },
    onSuccess: async (result) => {
      if (result.created) {
        setSelectedResolutionCode(result.code);
      }
      await refreshSettings("Код решения сохранён.");
    },
    onError: (error) => reportError(error, "Не удалось сохранить код решения."),
  });

  const deleteResolutionMutation = useMutation({
    mutationFn: async () => {
      if (!canManageRouting) {
        throw new Error(routingDeniedReason ?? "Недостаточно прав: settings.manage_routing");
      }
      if (!selectedResolution) {
        throw new Error("Сначала выберите код решения.");
      }
      await deleteWebSettingsResolutionCode(selectedResolution.code);
    },
    onSuccess: async () => {
      await refreshSettings("Код решения удалён.");
    },
    onError: (error) => reportError(error, "Не удалось удалить код решения."),
  });

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Button
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => void settingsQuery.refetch()}
            size="sm"
            variant="outline"
          >
            Обновить
          </Button>
        }
        description="Живые настройки ticket-системы поверх старого admin-config контура: очереди, маршрутизация, сроки ответа и решения, календари, внутренние сроки очередей, коды решения и аудит."
        eyebrow="Configuration"
        title="Настройки"
      />

      {feedback ? (
        <div
          className={`rounded-[1.1rem] px-4 py-3 text-sm ${
            feedback.tone === "success" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
          }`}
        >
          {feedback.text}
        </div>
      ) : null}

      {settingsQuery.isLoading ? <p className="text-sm text-slate-500">Собираем реальные настройки ticket-системы…</p> : null}
      {settingsQuery.isError ? (
        <p className="text-sm text-rose-600">
          {settingsQuery.error instanceof Error ? settingsQuery.error.message : "Не удалось загрузить настройки."}
        </p>
      ) : null}

      <Tabs
        items={TAB_ITEMS.map((item) => ({
          value: item.value,
          label: item.label,
        }))}
        onValueChange={(value) => setActiveTab(value as SettingsTab)}
        value={activeTab}
      />

      {payload ? (
        <>
          {activeTab === "overview" ? (
            <div className="space-y-6">
              <div className="grid gap-4 xl:grid-cols-4">
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Очереди</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.queues_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Активных: {payload.overview.active_queues_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Маршрутизация</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.routing_rules_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Активных правил: {payload.overview.active_routing_rules_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Сроки и календари</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.sla_policies_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Календарей: {payload.overview.calendars_count}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-slate-500">Коды и аудит</p>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">{payload.overview.resolution_codes_count}</p>
                    <p className="mt-2 text-sm text-slate-500">Аудит-записей: {payload.overview.audit_records_count}</p>
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
                <Card>
                  <CardHeader>
                    <CardTitle>Текущий operational snapshot</CardTitle>
                    <CardDescription>Быстрая сводка по живым настройкам без возврата в старую admin-страницу.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-2">
                    {payload.queues.slice(0, 4).map((queue) => (
                      <div key={queue.id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{queue.name}</p>
                          <Badge tone={queue.is_active ? "success" : "neutral"}>{queue.code}</Badge>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">
                          Открыто тикетов: {queue.open_tickets_count} • участников: {queue.members.length}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Права на запись</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="text-sm text-slate-500">Роль текущего сеанса</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-950">{payload.capabilities.actor_role}</p>
                    </div>
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="text-sm text-slate-500">Доступ на изменение</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-950">
                        {payload.capabilities.can_write ? "Разрешён" : "Только чтение"}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : null}

          {activeTab === "tickets" ? (
            <div className="space-y-6">
              <div className="grid gap-4 xl:grid-cols-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <Workflow className="h-4 w-4 text-brand-700" />
                      Статусы
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {payload.ticket_settings.internal_statuses.length}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Пользовательских: {payload.ticket_settings.requester_statuses.length}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <ShieldCheck className="h-4 w-4 text-brand-700" />
                      Governance
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {payload.ticket_settings.governance.resolution_validation_mode}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      FSM: {payload.ticket_settings.governance.fsm_mode}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <CheckCircle2 className="h-4 w-4 text-brand-700" />
                      Паспорт решения
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {formatBooleanFlag(payload.ticket_settings.governance.passport_enabled)}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Evidence gate: {formatBooleanFlag(payload.ticket_settings.governance.evidence_gate_enabled)}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <GitBranch className="h-4 w-4 text-brand-700" />
                      Сроки ответа и очередей
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-slate-950">
                      {formatBooleanFlag(payload.ticket_settings.operational_flags.ola_enabled)}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Рабочий календарь для сроков: {formatBooleanFlag(payload.ticket_settings.operational_flags.sla_calendar_enabled)}
                    </p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Схема service desk</CardTitle>
                  <CardDescription>
                    Шаблон обращения → форма → процесс → приоритет → сроки → очередь → паспорт
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {payload.ticket_settings.process_schema.map((item) => (
                      <div key={item.key} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-950">{item.label}</p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{item.meaning}</p>
                          </div>
                          <Badge tone={item.status === "active" ? "success" : "warning"}>{item.status}</Badge>
                        </div>
                        <p className="mt-3 text-xs text-slate-500">{item.source}</p>
                        <code className="mt-2 block text-xs text-slate-400">{item.ui_surface}</code>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)]">
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">Модель приоритета</p>
                          <p className="mt-1 text-sm text-slate-500">
                            Пользователь не выбирает P0/P1/P2/P3 напрямую
                          </p>
                        </div>
                        <Badge tone={payload.ticket_settings.priority_model.direct_user_priority_choice ? "warning" : "success"}>
                          {payload.ticket_settings.priority_model.direct_user_priority_choice ? "Ручной выбор" : "Факты → приоритет"}
                        </Badge>
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-3">
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Влияние</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.impact_levels.join(", ")}</p>
                        </div>
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Срочность</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.urgency_levels.join(", ")}</p>
                        </div>
                        <div className="rounded-[0.9rem] bg-white px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Важность</p>
                          <p className="mt-2 text-sm text-slate-700">{payload.ticket_settings.priority_model.importance_sources.join(", ")}</p>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {payload.ticket_settings.priority_model.modifiers.map((modifier) => (
                          <Badge key={modifier} tone="info">{modifier}</Badge>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <p className="font-semibold text-slate-950">Линии поддержки</p>
                      <div className="mt-3 space-y-3">
                        {payload.ticket_settings.support_lines.map((line) => (
                          <div key={line.code} className="rounded-[0.9rem] bg-white px-3 py-3">
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-semibold text-slate-900">{line.label}</p>
                              <Badge tone={line.status === "active" ? "success" : "warning"}>{line.status}</Badge>
                            </div>
                            <p className="mt-2 text-sm text-slate-600">{line.competence_depth}</p>
                            <code className="mt-2 block text-xs text-slate-400">{line.routing_role}</code>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Профили процесса</CardTitle>
                  <CardDescription>Тип процесса выбирает жизненный цикл и разрешённые переходы статусов.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="info">{workflowProfileDrafts.length} профилей</Badge>
                      <Badge tone="neutral">переходы хранятся как JSON</Badge>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        disabled={!canManageRouting}
                        onClick={() =>
                          setWorkflowProfileDrafts((current) => [
                            ...current,
                            createWorkflowProfileDraft(current.length + 1),
                          ])
                        }
                        variant="secondary"
                      >
                        <Plus className="h-4 w-4" />
                        Новый тип
                      </Button>
                      <Button
                        disabled={!canManageRouting || workflowProfilesMutation.isPending}
                        onClick={() => workflowProfilesMutation.mutate()}
                      >
                        <Workflow className="h-4 w-4" />
                        Сохранить профили процесса
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {workflowProfileDrafts.map((profile, index) => (
                      <div key={`${profile.ticket_type}-${index}`} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-950">{profile.label || profile.ticket_type || `Профиль ${index + 1}`}</p>
                            <p className="mt-1 text-xs text-slate-500">{profile.purpose || "назначение не указано"}</p>
                          </div>
                          <Button
                            disabled={!canManageRouting || workflowProfileDrafts.length <= 1}
                            onClick={() => setWorkflowProfileDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                            variant="ghost"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-3">
                          <SettingsField label="ticket_type">
                            <Input
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, ticket_type: event.currentTarget.value } : item
                                  )
                                )
                              }
                              value={profile.ticket_type}
                            />
                          </SettingsField>
                          <SettingsField label="Название">
                            <Input
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, label: event.currentTarget.value } : item
                                  )
                                )
                              }
                              value={profile.label}
                            />
                          </SettingsField>
                          <SettingsField label="Назначение">
                            <Input
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                setWorkflowProfileDrafts((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, purpose: event.currentTarget.value } : item
                                  )
                                )
                              }
                              value={profile.purpose}
                            />
                          </SettingsField>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-2">
                          {[
                            ["suggested_path_text", "Рекомендуемый путь"],
                            ["allowed_statuses_text", "Разрешённые статусы"],
                            ["required_create_fields_text", "Поля при создании"],
                            ["required_resolve_fields_text", "Поля при решении"],
                            ["evidence_required_for_priorities_text", "Приоритеты с доказательствами"],
                          ].map(([key, label]) => (
                            <SettingsField key={key} label={label}>
                              <Input
                                disabled={!canManageRouting}
                                onChange={(event) =>
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, [key]: event.currentTarget.value } : item
                                    )
                                  )
                                }
                                value={String(profile[key as keyof WorkflowProfileDraft] ?? "")}
                              />
                            </SettingsField>
                          ))}
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-3">
                          {[
                            ["requires_approval", "Требует согласование"],
                            ["requires_change_plan", "Требует план изменений"],
                            ["requires_action_log", "Требует журнал действий"],
                          ].map(([key, label]) => (
                            <label key={key} className="flex items-center gap-3 rounded-[1rem] bg-surface-subtle px-4 py-3 text-sm font-medium text-slate-800">
                              <input
                                checked={Boolean(profile[key as keyof WorkflowProfileDraft])}
                                disabled={!canManageRouting}
                                onChange={(event) =>
                                  setWorkflowProfileDrafts((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, [key]: event.currentTarget.checked } : item
                                    )
                                  )
                                }
                                type="checkbox"
                              />
                              {label}
                            </label>
                          ))}
                        </div>

                        <SettingsField label="Переходы статусов JSON">
                          <textarea
                            className="field-base mt-4 min-h-[220px] w-full px-4 py-3 font-mono text-xs"
                            disabled={!canManageRouting}
                            onChange={(event) =>
                              setWorkflowProfileDrafts((current) =>
                                current.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, transitions_json: event.currentTarget.value } : item
                                )
                              )
                            }
                            value={profile.transitions_json}
                          />
                        </SettingsField>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
                <Card>
                  <CardHeader>
                    <CardTitle>Жизненный цикл тикета</CardTitle>
                    <CardDescription>
                      Канонические внутренние статусы, пользовательское отображение и ответственный за следующий шаг.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[760px] text-left text-sm">
                        <thead className="text-xs uppercase tracking-[0.18em] text-slate-400">
                          <tr>
                            <th className="px-3 py-3">Внутренний статус</th>
                            <th className="px-3 py-3">Для пользователя</th>
                            <th className="px-3 py-3">Чей ход</th>
                            <th className="px-3 py-3">Этап</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {payload.ticket_settings.internal_statuses.map((status) => (
                            <tr key={status.value}>
                              <td className="px-3 py-4">
                                <div className="font-semibold text-slate-950">{status.label}</div>
                                <code className="mt-1 block text-xs text-slate-400">{status.value}</code>
                              </td>
                              <td className="px-3 py-4">
                                <div className="font-medium text-slate-800">{status.requester_label}</div>
                                <code className="mt-1 block text-xs text-slate-400">{status.requester_status}</code>
                              </td>
                              <td className="px-3 py-4">
                                <code className="text-xs text-slate-600">{status.next_action_owner}</code>
                              </td>
                              <td className="px-3 py-4">
                                <div className="flex flex-wrap gap-2">
                                  <Badge tone={getTicketStageTone(status.stage)}>{getTicketStageLabel(status.stage)}</Badge>
                                  {status.waits ? <Badge tone="warning">Wait ledger</Badge> : null}
                                  {status.terminal ? <Badge tone="neutral">Terminal</Badge> : null}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Правила закрытия</CardTitle>
                      <CardDescription>То, что влияет на подтверждаемость решения.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Подтверждение пользователя</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {formatBooleanFlag(payload.ticket_settings.governance.requester_confirmation_required)}
                        </p>
                      </div>
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Автозакрытие после решения</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {payload.ticket_settings.governance.auto_close_hours} ч
                        </p>
                      </div>
                      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                        <p className="text-slate-500">Root cause обязателен для</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {payload.ticket_settings.governance.require_root_cause_priorities.map((priority) => (
                            <Badge key={priority} tone="warning">{priority}</Badge>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Operational flags</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {[
                        ["Admin config API", payload.ticket_settings.operational_flags.admin_config_api_enabled],
                        ["Admin config write", payload.ticket_settings.operational_flags.admin_config_write_enabled],
                        ["Auditor role", payload.ticket_settings.operational_flags.auditor_role_enabled],
                        ["Retention", payload.ticket_settings.operational_flags.retention_enabled],
                        ["Retention dry-run", payload.ticket_settings.operational_flags.retention_dry_run],
                      ].map(([label, value]) => (
                        <div key={String(label)} className="flex items-center justify-between rounded-[1rem] bg-surface-subtle px-4 py-3">
                          <span className="text-slate-500">{label}</span>
                          <Badge tone={value ? "success" : "neutral"}>{formatBooleanFlag(Boolean(value))}</Badge>
                        </div>
                      ))}
                      <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                        <p className="text-slate-500">Take-self queue mode</p>
                        <p className="mt-2 font-semibold text-slate-950">
                          {payload.ticket_settings.operational_flags.take_queue_mode}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          common: {payload.ticket_settings.operational_flags.take_queue_common_code} • test:{" "}
                          {payload.ticket_settings.operational_flags.take_queue_test_code}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle>Пользовательские статусы</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {payload.ticket_settings.requester_statuses.map((item) => (
                      <div key={item.value} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{item.label}</p>
                          <Badge tone="neutral">{item.internal_statuses.length}</Badge>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{item.internal_statuses.join(", ") || "Нет статусов"}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Следующий ответственный</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {payload.ticket_settings.next_action_owners.map((item) => (
                      <div key={item.value} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-slate-950">{item.label}</p>
                          <code className="text-xs text-slate-400">{item.value}</code>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{item.internal_statuses.join(", ") || "Нет статусов"}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Детальные настройки</CardTitle>
                    <CardDescription>Редактируемые части тикетной системы уже вынесены в соседние вкладки.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3">
                    <Button onClick={() => setActiveTab("queues")} variant="outline">Очереди и внутренние сроки</Button>
                    <Button onClick={() => setActiveTab("routing")} variant="outline">Маршрутизация</Button>
                    <Button onClick={() => setActiveTab("sla")} variant="outline">Сроки и матрица приоритетов</Button>
                    <Button onClick={() => setActiveTab("resolution")} variant="outline">Коды решения</Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : null}

          {activeTab === "notifications" ? (
            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Каналы уведомлений</CardTitle>
                    <CardDescription>Что уже может попадать в in-app уведомления и технические alerts.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {NOTIFICATION_CATALOG.map((item) => {
                      const enabled = !mutedNotificationTypes.includes(item.eventType);
                      return (
                        <label
                          key={item.eventType}
                          className="flex items-start gap-3 rounded-[1.1rem] border border-border bg-white px-4 py-4"
                        >
                          <input
                            checked={enabled}
                            className="mt-1 h-4 w-4"
                            disabled={!canWrite || notificationMutation.isPending || notificationSettingsQuery.isLoading}
                            onChange={(event) => toggleMutedNotification(item.eventType, event.target.checked)}
                            type="checkbox"
                          />
                          <span>
                            <span className="block font-semibold text-slate-950">{item.title}</span>
                            <span className="mt-1 block text-sm text-slate-500">{item.description}</span>
                            <span className="mt-2 block text-xs uppercase tracking-[0.18em] text-slate-400">{item.eventType}</span>
                          </span>
                        </label>
                      );
                    })}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Последние уведомления</CardTitle>
                    <CardDescription>Живой список для текущего пользователя админки.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {notificationsQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем уведомления…</p> : null}
                    {(notificationsQuery.data?.notifications ?? []).length ? (
                      notificationsQuery.data?.notifications.map((item) => (
                        <div key={item.id} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold text-slate-950">{item.event_type}</p>
                            <Badge tone={item.is_read ? "neutral" : "info"}>{item.is_read ? "Прочитано" : "Новое"}</Badge>
                          </div>
                          <p className="mt-2 text-sm text-slate-500">
                            Тикет {item.ticket_id} • {formatDateTime(item.created_at)}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                        Последних уведомлений пока нет.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Правила тишины</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <label className="flex items-start gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <input
                        checked={Boolean(notificationPreferences?.suppress_self ?? true)}
                        className="mt-1 h-4 w-4"
                        disabled={!canWrite || notificationMutation.isPending}
                        onChange={(event) => notificationMutation.mutate({ suppress_self: event.target.checked })}
                        type="checkbox"
                      />
                      <span>
                        <span className="block font-medium text-slate-950">Не уведомлять о своих действиях</span>
                        <span className="mt-1 block text-sm text-slate-500">Снижает шум от собственных комментариев и смен статуса.</span>
                      </span>
                    </label>
                    <label className="flex items-start gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <input
                        checked={Boolean(notificationPreferences?.mute_internal ?? false)}
                        className="mt-1 h-4 w-4"
                        disabled={!canWrite || notificationMutation.isPending}
                        onChange={(event) => notificationMutation.mutate({ mute_internal: event.target.checked })}
                        type="checkbox"
                      />
                      <span>
                        <span className="block font-medium text-slate-950">Глушить internal-note</span>
                        <span className="mt-1 block text-sm text-slate-500">Оставляет публичные события и сроки ответа, но убирает внутренние заметки.</span>
                      </span>
                    </label>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Ошибки и alerts</CardTitle>
                    <CardDescription>Операционные события, которые должны быть видны администратору.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {techAlertsQuery.isLoading ? <p className="text-sm text-slate-500">Проверяем alerts…</p> : null}
                    {(techAlertsQuery.data?.alerts ?? []).length ? (
                      techAlertsQuery.data?.alerts.map((alert) => (
                        <div key={`${alert.kind}:${alert.title}`} className="rounded-[1.1rem] border border-amber-200 bg-amber-50 px-4 py-4">
                          <div className="flex items-start gap-3">
                            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
                            <div>
                              <p className="font-semibold text-amber-950">{alert.title}</p>
                              <p className="mt-1 text-sm text-amber-800">{alert.description}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                        Активных технических alerts нет.
                      </div>
                    )}
                    <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                      <div className="flex items-center gap-2 font-semibold text-slate-950">
                        <Bell className="h-4 w-4 text-brand-700" />
                        Контролируемые события
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {TECH_ALERT_CATALOG.map((item) => (
                          <Badge key={item} tone="neutral">{item}</Badge>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : null}

          {activeTab === "queues" ? (
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Очереди</CardTitle>
                  <CardDescription>Выбор очереди, участники и внутренние сроки принятия и обработки.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    disabled={!canManageQueues}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => {
                      setSelectedQueueId(null);
                      setQueueDraft(buildQueueDraft(null));
                      setOlaDraft(buildOlaDraft(null));
                    }}
                    variant="secondary"
                  >
                    Новая очередь
                  </Button>
                  {payload.queues.map((queue) => (
                    <button
                      key={queue.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedQueue?.id === queue.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => setSelectedQueueId(queue.id)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{queue.name}</p>
                        <Badge tone={queue.is_active ? "success" : "neutral"}>{queue.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">
                        Открыто: {queue.open_tickets_count} • участников: {queue.members.length}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <PermissionNotice text={queueDeniedReason} />
                <Card>
                  <CardHeader>
                    <CardTitle>{selectedQueue ? "Настройки очереди" : "Новая очередь"}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <SettingsField label="Code">
                        <Input
                          onChange={(event) => setQueueDraft((current) => ({ ...current, code: event.target.value }))}
                          value={queueDraft.code}
                        />
                      </SettingsField>
                      <SettingsField label="Name">
                        <Input
                          onChange={(event) => setQueueDraft((current) => ({ ...current, name: event.target.value }))}
                          value={queueDraft.name}
                        />
                      </SettingsField>
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input
                          checked={queueDraft.is_triage}
                          onChange={(event) => setQueueDraft((current) => ({ ...current, is_triage: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Triage queue</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input
                          checked={queueDraft.is_active}
                          onChange={(event) => setQueueDraft((current) => ({ ...current, is_active: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Активна</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input
                          checked={queueDraft.auto_assign_enabled}
                          onChange={(event) =>
                            setQueueDraft((current) => ({ ...current, auto_assign_enabled: event.target.checked }))
                          }
                          type="checkbox"
                        />
                        <span>Auto-assign</span>
                      </label>
                    </div>
                    <Button disabled={!canManageQueues || queueMutation.isPending} onClick={() => queueMutation.mutate()} className="w-full">
                      {queueMutation.isPending ? "Сохраняем…" : "Сохранить очередь"}
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-6 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Участники очереди</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {selectedQueue?.members.length ? (
                        selectedQueue.members.map((member) => (
                          <div key={member.actor_id} className="flex items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                            <div>
                              <p className="font-medium text-slate-900">{member.actor_id}</p>
                              <p className="text-slate-500">{member.role_in_queue ?? "role_in_queue не задан"}</p>
                            </div>
                            <Button
                              disabled={!canManageQueues || removeMemberMutation.isPending}
                              onClick={() => removeMemberMutation.mutate(member.actor_id)}
                              size="sm"
                              variant="ghost"
                            >
                              Удалить
                            </Button>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-slate-500">У выбранной очереди участников пока нет.</p>
                      )}

                      <div className="grid gap-3">
                        <Input
                          onChange={(event) => setNewMemberActorId(event.target.value)}
                          placeholder="actor_id"
                          value={newMemberActorId}
                        />
                        <Input
                          onChange={(event) => setNewMemberRole(event.target.value)}
                          placeholder="role_in_queue"
                          value={newMemberRole}
                        />
                        <Button disabled={!canManageQueues || memberMutation.isPending} onClick={() => memberMutation.mutate()}>
                          Добавить / обновить участника
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Внутренние сроки очереди</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {olaDraft.map((row) => (
                        <div key={row.priority} className="grid gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 md:grid-cols-3">
                          <div className="font-semibold text-slate-950">{row.priority}</div>
                          <Input
                            min={0}
                            onChange={(event) =>
                              setOlaDraft((current) =>
                                current.map((item) =>
                                  item.priority === row.priority ? { ...item, ack_min: Number(event.target.value) } : item
                                )
                              )
                            }
                            type="number"
                            value={String(row.ack_min)}
                          />
                          <Input
                            min={0}
                            onChange={(event) =>
                              setOlaDraft((current) =>
                                current.map((item) =>
                                  item.priority === row.priority ? { ...item, processing_min: Number(event.target.value) } : item
                                )
                              )
                            }
                            type="number"
                            value={String(row.processing_min)}
                          />
                        </div>
                      ))}
                      <Button disabled={!canManageQueues || olaMutation.isPending || !selectedQueue} onClick={() => olaMutation.mutate()} className="w-full">
                        Сохранить внутренние сроки
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === "routing" ? (
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Правила маршрутизации</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Button
                      disabled={!canManageRouting}
                      leadingIcon={<Plus className="h-4 w-4" />}
                      onClick={() => {
                        setSelectedRuleId(-1);
                        setRoutingDraft(buildRoutingDraft(null, payload.queues[0]?.id ?? null));
                        setRoutingConditionBuilder(
                          buildRoutingConditionBuilder(
                            { field: payload.routing_builder.fields[0]?.field ?? "request_kind", op: "eq", value: "" },
                            payload.routing_builder.fields[0]?.field ?? "request_kind"
                          )
                        );
                      }}
                      variant="secondary"
                    >
                    Новое правило
                  </Button>
                  {payload.routing_rules.map((rule) => (
                    <button
                      key={rule.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedRule?.id === rule.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => setSelectedRuleId(rule.id)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">Rule #{rule.id}</p>
                        <Badge tone={rule.enabled ? "success" : "neutral"}>{rule.target_queue_name ?? rule.target_queue_id}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Priority: {rule.priority_order}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedRule ? `Rule #${selectedRule.id}` : "Новое правило"}</CardTitle>
                  <CardDescription>
                    Роутинг теперь понимает `ticket_type`, `request_kind`, `custom_fields.request_kind` и поля вида
                    `request_form_data.*`. Ниже можно собрать leaf-условие из текущего каталога форм без ручного JSON.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-3">
                    <SettingsField label="Priority order">
                      <Input
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, priority_order: Number(event.target.value) }))}
                        type="number"
                        value={String(routingDraft.priority_order)}
                      />
                    </SettingsField>
                    <SettingsField label="Target queue">
                      <Select
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, target_queue_id: Number(event.target.value) }))}
                        value={String(routingDraft.target_queue_id)}
                      >
                        {payload.queues.map((queue) => (
                          <option key={queue.id} value={queue.id}>
                            {queue.name}
                          </option>
                        ))}
                      </Select>
                    </SettingsField>
                    <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                      <input
                        checked={routingDraft.enabled}
                        onChange={(event) => setRoutingDraft((current) => ({ ...current, enabled: event.target.checked }))}
                        type="checkbox"
                      />
                      <span>Правило активно</span>
                    </label>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Form-aware builder</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Поля из текущих intake-форм уже подгружены в настройки. Условие собирается автоматически при сохранении.
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      <SettingsField label="Поле">
                        <Select
                          onChange={(event) =>
                            setRoutingConditionBuilder((current) => ({ ...current, field: event.target.value }))
                          }
                          value={routingConditionBuilder.field}
                        >
                          {payload.routing_builder.fields.map((item) => (
                            <option key={`${item.field}-${item.form_key ?? "base"}`} value={item.field}>
                              {item.label}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      <SettingsField label="Оператор">
                        <Select
                          onChange={(event) =>
                            setRoutingConditionBuilder((current) => ({
                              ...current,
                              op: event.target.value,
                            }))
                          }
                          value={routingConditionBuilder.op}
                        >
                          {payload.routing_builder.operators.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      {routingConditionBuilder.op === "is_null" ? (
                        <SettingsField label="Значение">
                          <Select
                            onChange={(event) =>
                              setRoutingConditionBuilder((current) => ({
                                ...current,
                                null_state: event.target.value as "true" | "false",
                              }))
                            }
                            value={routingConditionBuilder.null_state}
                          >
                            <option value="true">Пусто</option>
                            <option value="false">Не пусто</option>
                          </Select>
                        </SettingsField>
                      ) : (
                        <SettingsField
                          label={routingConditionBuilder.op === "in" || routingConditionBuilder.op === "nin" ? "Значение (через запятую)" : "Значение"}
                        >
                          <Input
                            onChange={(event) =>
                              setRoutingConditionBuilder((current) => ({
                                ...current,
                                value_text: event.target.value,
                              }))
                            }
                            placeholder={
                              routingConditionBuilder.op === "in" || routingConditionBuilder.op === "nin"
                                ? "214, 215"
                                : "access"
                            }
                            value={routingConditionBuilder.value_text}
                          />
                        </SettingsField>
                      )}
                    </div>

                    <div className="mt-4 space-y-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Текущие формы каталога</p>
                      {payload.routing_builder.forms.length === 0 ? (
                        <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-4 text-sm text-slate-500">
                          Формы пока не опубликованы.
                        </div>
                      ) : (
                        payload.routing_builder.forms.map((form) => (
                          <div key={form.key} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <p className="font-medium text-slate-900">{form.title}</p>
                                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{form.request_kind}</p>
                              </div>
                              <Badge tone="neutral">{form.fields.length} полей</Badge>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                              {form.fields.map((field) => (
                                <code key={field.field} className="rounded-pill bg-surface-subtle px-3 py-1 text-[11px]">
                                  {field.field}
                                </code>
                              ))}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Собранное условие</p>
                    <code className="mt-3 block whitespace-pre-wrap rounded-[0.8rem] bg-surface-subtle px-4 py-3 text-xs text-slate-700">
                      {prettyJson(buildRoutingConditionJson(routingConditionBuilder))}
                    </code>
                  </div>

                  <Button disabled={!canManageRouting || routingMutation.isPending} onClick={() => routingMutation.mutate()} className="w-full">
                    {routingMutation.isPending ? "Сохраняем…" : "Сохранить правило"}
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {activeTab === "sla" ? (
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Политики сроков</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PermissionNotice text={routingDeniedReason} />
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => {
                      setSelectedPolicyId(null);
                      setPolicyDraft(buildPolicyDraft(null));
                      setSlaTargetsDraft(buildSlaTargetsDraft(null));
                      setPriorityMatrixDraft(buildPriorityMatrixDraft(null));
                    }}
                    variant="secondary"
                  >
                    Новая политика
                  </Button>
                  {payload.sla_policies.map((policy) => (
                    <button
                      key={policy.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedPolicy?.id === policy.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => setSelectedPolicyId(policy.id)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{policy.name}</p>
                        {policy.is_default ? <Badge tone="success">Default</Badge> : null}
                      </div>
                      <p className="mt-2 text-xs text-current/70">
                        {policy.timezone} • открытых тикетов: {policy.open_tickets_count}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <PermissionNotice text={routingDeniedReason} />
                <Card>
                  <CardHeader>
                    <CardTitle>{selectedPolicy ? selectedPolicy.name : "Новая политика сроков"}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <SettingsField label="Название">
                        <Input
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, name: event.target.value }))}
                          value={policyDraft.name}
                        />
                      </SettingsField>
                      <SettingsField label="Часовой пояс">
                        <Input
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, timezone: event.target.value }))}
                          value={policyDraft.timezone}
                        />
                      </SettingsField>
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                      <SettingsField label="Календарь">
                        <Select
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, calendar_id: event.target.value }))}
                          value={policyDraft.calendar_id}
                        >
                          <option value="">Без календаря</option>
                          {payload.calendars.map((calendar) => (
                            <option key={calendar.id} value={calendar.id}>
                              {calendar.name}
                            </option>
                          ))}
                        </Select>
                      </SettingsField>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input
                          checked={policyDraft.is_default}
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, is_default: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Политика по умолчанию</span>
                      </label>
                      <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                        <input
                          checked={policyDraft.is_active}
                          onChange={(event) => setPolicyDraft((current) => ({ ...current, is_active: event.target.checked }))}
                          type="checkbox"
                        />
                        <span>Политика активна</span>
                      </label>
                    </div>
                    <SettingsField label="Режим рабочих часов">
                      <Select
                        onChange={(event) =>
                          setPolicyDraft((current) => ({
                            ...current,
                            business_hours_mode: event.target.value as PolicyDraft["business_hours_mode"],
                          }))
                        }
                        value={policyDraft.business_hours_mode}
                      >
                        <option value="calendar">По выбранному календарю</option>
                        <option value="always_on">24×7 без календаря</option>
                      </Select>
                    </SettingsField>
                    <Button disabled={!canManageRouting || policyMutation.isPending} onClick={() => policyMutation.mutate()} className="w-full">
                      Сохранить политику сроков
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-6 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Сроки ответа и решения</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {slaTargetsDraft.map((row) => (
                        <div key={row.priority} className="grid gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 md:grid-cols-3">
                          <div className="font-semibold text-slate-950">{row.priority}</div>
                          <Input
                            min={0}
                            onChange={(event) =>
                              setSlaTargetsDraft((current) =>
                                current.map((item) =>
                                  item.priority === row.priority
                                    ? { ...item, first_response_min: Number(event.target.value) }
                                    : item
                                )
                              )
                            }
                            type="number"
                            value={String(row.first_response_min)}
                          />
                          <Input
                            min={0}
                            onChange={(event) =>
                              setSlaTargetsDraft((current) =>
                                current.map((item) =>
                                  item.priority === row.priority
                                    ? { ...item, resolution_min: Number(event.target.value) }
                                    : item
                                )
                              )
                            }
                            type="number"
                            value={String(row.resolution_min)}
                          />
                        </div>
                      ))}
                      <Button disabled={!canManageRouting || slaTargetsMutation.isPending || !selectedPolicy} onClick={() => slaTargetsMutation.mutate()} className="w-full">
                        Сохранить сроки
                      </Button>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Матрица влияния и срочности</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {priorityMatrixDraft.map((row) => (
                        <div key={`${row.impact}:${row.urgency}`} className="grid gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 md:grid-cols-[1fr_1fr_1fr]">
                          <div className="text-sm font-medium text-slate-900">
                            Влияние {row.impact} / срочность {row.urgency}
                          </div>
                          <Select
                            onChange={(event) =>
                              setPriorityMatrixDraft((current) =>
                                current.map((item) =>
                                  item.impact === row.impact && item.urgency === row.urgency
                                    ? { ...item, priority: event.target.value }
                                    : item
                                )
                              )
                            }
                            value={row.priority}
                          >
                            {PRIORITY_OPTIONS.map((priority) => (
                              <option key={priority} value={priority}>
                                {priority}
                              </option>
                            ))}
                          </Select>
                          <span className="text-sm text-slate-500">Приоритет для этого сочетания</span>
                        </div>
                      ))}
                      <Button disabled={!canManageRouting || priorityMatrixMutation.isPending || !selectedPolicy} onClick={() => priorityMatrixMutation.mutate()} className="w-full">
                        Сохранить матрицу
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === "calendars" ? (
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Календари</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => {
                      setSelectedCalendarId(null);
                      setCalendarDraft(buildCalendarDraft(null));
                    }}
                    variant="secondary"
                  >
                    Новый календарь
                  </Button>
                  {payload.calendars.map((calendar) => (
                    <button
                      key={calendar.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedCalendar?.id === calendar.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => setSelectedCalendarId(calendar.id)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{calendar.name}</p>
                        <Badge tone={calendar.is_active ? "success" : "neutral"}>{calendar.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Обновлён: {formatDateTime(calendar.updated_at)}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedCalendar ? selectedCalendar.name : "Новый календарь"}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Code">
                      <Input
                        onChange={(event) => setCalendarDraft((current) => ({ ...current, code: event.target.value }))}
                        value={calendarDraft.code}
                      />
                    </SettingsField>
                    <SettingsField label="Name">
                      <Input
                        onChange={(event) => setCalendarDraft((current) => ({ ...current, name: event.target.value }))}
                        value={calendarDraft.name}
                      />
                    </SettingsField>
                  </div>
                  <SettingsField label="Timezone">
                    <Input
                      onChange={(event) => setCalendarDraft((current) => ({ ...current, timezone: event.target.value }))}
                      value={calendarDraft.timezone}
                    />
                  </SettingsField>
                  <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                    <input
                      checked={calendarDraft.is_active}
                      onChange={(event) => setCalendarDraft((current) => ({ ...current, is_active: event.target.checked }))}
                      type="checkbox"
                    />
                    <span>Календарь активен</span>
                  </label>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Рабочая неделя</p>
                        <p className="mt-1 text-sm text-slate-500">Один интервал на день; структура календаря собирается автоматически.</p>
                      </div>
                      <Button
                        onClick={() => setCalendarDraft((current) => ({ ...current, weekly_hours: defaultCalendarHours() }))}
                        size="sm"
                        variant="outline"
                      >
                        Будни 09:00–18:00
                      </Button>
                    </div>
                    <div className="mt-4 grid gap-3">
                      {calendarDraft.weekly_hours.map((row) => {
                        const dayLabel = CALENDAR_DAYS.find((item) => item.day === row.day)?.label ?? String(row.day);
                        return (
                          <div key={row.day} className="grid gap-3 rounded-[0.9rem] bg-white px-3 py-3 md:grid-cols-[7rem_1fr_1fr]">
                            <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
                              <input
                                checked={row.enabled}
                                onChange={(event) =>
                                  setCalendarDraft((current) => ({
                                    ...current,
                                    weekly_hours: current.weekly_hours.map((item) =>
                                      item.day === row.day ? { ...item, enabled: event.target.checked } : item,
                                    ),
                                  }))
                                }
                                type="checkbox"
                              />
                              <span>{dayLabel}</span>
                            </label>
                            <Input
                              disabled={!row.enabled}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  weekly_hours: current.weekly_hours.map((item) =>
                                    item.day === row.day ? { ...item, start: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="time"
                              value={row.start}
                            />
                            <Input
                              disabled={!row.enabled}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  weekly_hours: current.weekly_hours.map((item) =>
                                    item.day === row.day ? { ...item, end: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="time"
                              value={row.end}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Праздники и исключения</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Даты выбираются списком; JSON для API собирается автоматически.
                        </p>
                      </div>
                      <Button
                        disabled={!canManageRouting}
                        leadingIcon={<Plus className="h-4 w-4" />}
                        onClick={() =>
                          setCalendarDraft((current) => ({
                            ...current,
                            holidays: [...current.holidays, createHolidayDraft("", current.holidays.length)],
                          }))
                        }
                        size="sm"
                        variant="outline"
                      >
                        Добавить дату
                      </Button>
                    </div>

                    <div className="mt-4 grid gap-3">
                      {calendarDraft.holidays.length ? (
                        calendarDraft.holidays.map((holiday, index) => (
                          <div key={holiday.id} className="grid gap-3 rounded-[0.9rem] bg-white px-3 py-3 md:grid-cols-[minmax(0,1fr)_auto]">
                            <Input
                              aria-label="Дата праздника или исключения"
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  holidays: current.holidays.map((item) =>
                                    item.id === holiday.id ? { ...item, date: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="date"
                              value={holiday.date}
                            />
                            <Button
                              aria-label={`Удалить дату ${holiday.date || index + 1}`}
                              disabled={!canManageRouting}
                              leadingIcon={<Trash2 className="h-4 w-4" />}
                              onClick={() =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  holidays: current.holidays.filter((item) => item.id !== holiday.id),
                                }))
                              }
                              size="sm"
                              variant="outline"
                            >
                              Удалить
                            </Button>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-[0.9rem] border border-dashed border-border bg-white px-4 py-5 text-sm text-slate-500">
                          Исключений нет. Добавьте дату, если сроки ответа не должны считать этот день рабочим.
                        </div>
                      )}
                    </div>

                    <div className="mt-4 rounded-[0.9rem] bg-white px-3 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Собирается для API</p>
                      <pre className="mt-2 overflow-x-auto text-xs text-slate-600">{prettyJson(buildHolidaysJson(calendarDraft.holidays))}</pre>
                    </div>
                  </div>
                  <Button disabled={!canManageRouting || calendarMutation.isPending} onClick={() => calendarMutation.mutate()} className="w-full">
                    Сохранить календарь
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {activeTab === "resolution" ? (
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Коды решения</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PermissionNotice text={routingDeniedReason} />
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => {
                      setSelectedResolutionCode(null);
                      setResolutionDraft(buildResolutionDraft(null));
                    }}
                    variant="secondary"
                  >
                    Новый код
                  </Button>
                  {payload.resolution_codes.map((item) => (
                    <button
                      key={item.code}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedResolution?.code === item.code ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => setSelectedResolutionCode(item.code)}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{item.name}</p>
                        <Badge tone={item.is_active ? "success" : "neutral"}>{item.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Использований: {item.usage_count}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedResolution ? selectedResolution.name : "Новый код решения"}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Code">
                      <Input
                        disabled={Boolean(selectedResolution)}
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, code: event.target.value }))}
                        value={resolutionDraft.code}
                      />
                    </SettingsField>
                    <SettingsField label="Name">
                      <Input
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, name: event.target.value }))}
                        value={resolutionDraft.name}
                      />
                    </SettingsField>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Sort order">
                      <Input
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, sort_order: Number(event.target.value) }))}
                        type="number"
                        value={String(resolutionDraft.sort_order)}
                      />
                    </SettingsField>
                    <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                      <input
                        checked={resolutionDraft.is_active}
                        onChange={(event) => setResolutionDraft((current) => ({ ...current, is_active: event.target.checked }))}
                        type="checkbox"
                      />
                      <span>Код активен</span>
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button disabled={!canManageRouting || resolutionMutation.isPending} onClick={() => resolutionMutation.mutate()}>
                      Сохранить код
                    </Button>
                    <Button
                      disabled={!canManageRouting || deleteResolutionMutation.isPending || !selectedResolution || selectedResolution.usage_count > 0}
                      leadingIcon={<Trash2 className="h-4 w-4" />}
                      onClick={() => deleteResolutionMutation.mutate()}
                      variant="outline"
                    >
                      Удалить код
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {activeTab === "audit" ? (
            <Card>
              <CardHeader>
                <CardTitle>Журнал аудита</CardTitle>
                <CardDescription>Последние real-data изменения admin-config в новом интерфейсе.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {payload.audit.length ? (
                  payload.audit.map((item) => (
                    <div key={item.id} className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">
                            {item.entity_type} / {item.entity_id}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {item.action} • {item.actor_id} ({item.actor_role})
                          </p>
                        </div>
                        <Badge tone="info">{formatDateTime(item.created_at)}</Badge>
                      </div>
                      <p className="mt-3 text-xs text-slate-400">{item.trace_id ?? "trace_id не передан"}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Записей аудита пока нет.</p>
                )}
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
