

import {type WebSettingsPayload} from "../../features/settings/api";

export type SettingsTab =
  | "overview"
  | "tickets"
  | "notifications"
  | "queues"
  | "routing"
  | "sla"
  | "calendars"
  | "resolution"
  | "audit";

export type QueueItem = WebSettingsPayload["queues"][number];

export type RoutingRuleItem = WebSettingsPayload["routing_rules"][number];

export type SlaPolicyItem = WebSettingsPayload["sla_policies"][number];

export type CalendarItem = WebSettingsPayload["calendars"][number];

export type ResolutionCodeItem = WebSettingsPayload["resolution_codes"][number];

export type ActionFeedback =
  | {
      tone: "error" | "success";
      text: string;
    }
  | null;

export type QueueDraft = {
  code: string;
  name: string;
  is_triage: boolean;
  is_active: boolean;
  auto_assign_enabled: boolean;
};

export type RoutingDraft = {
  enabled: boolean;
  priority_order: number;
  target_queue_id: number;
};

export type RoutingConditionBuilder = {
  field: string;
  op: string;
  value_text: string;
  null_state: "true" | "false";
};

export type PolicyDraft = {
  name: string;
  timezone: string;
  calendar_id: string;
  is_default: boolean;
  is_active: boolean;
  business_hours_mode: "calendar" | "always_on";
};

export type CalendarDayDraft = {
  day: number;
  enabled: boolean;
  start: string;
  end: string;
};

export type CalendarHolidayDraft = {
  id: string;
  date: string;
};

export type CalendarDraft = {
  code: string;
  name: string;
  timezone: string;
  is_active: boolean;
  weekly_hours: CalendarDayDraft[];
  holidays: CalendarHolidayDraft[];
};

export type ResolutionDraft = {
  code: string;
  name: string;
  is_active: boolean;
  sort_order: number;
};

export type OlaDraftRow = {
  priority: string;
  ack_min: number | null;
  processing_min: number | null;
};

export type SlaTargetDraftRow = {
  priority: string;
  first_response_min: number | null;
  resolution_min: number | null;
};

export type PriorityMatrixDraftRow = {
  impact: number;
  urgency: number;
  priority: string;
};

export type WorkflowProfileItem = WebSettingsPayload["ticket_settings"]["workflow_profiles"][number];

export type WorkflowProfileDraft = Omit<
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
  transition_builder_from: string;
  transition_builder_to: string;
  transition_builder_allowed_roles_text: string;
  transition_builder_required_fields_text: string;
  transition_builder_required_comment: string;
  transition_builder_require_approval: boolean;
  transition_builder_require_evidence: boolean;
  transition_builder_notify_text: string;
  transition_builder_sla_action: string;
  transition_builder_approval_action: string;
  transition_builder_log_fields_text: string;
  transition_builder_trigger: string;
  transition_builder_auto: boolean;
};

export const TAB_ITEMS = [
  { value: "overview", label: "Обзор" },
  { value: "tickets", label: "Тикеты" },
  { value: "notifications", label: "Состояние системы" },
  { value: "queues", label: "Очереди" },
  { value: "routing", label: "Маршрутизация" },
  { value: "sla", label: "Сроки" },
  { value: "calendars", label: "Календари" },
  { value: "resolution", label: "Коды решения" },
  { value: "audit", label: "Аудит" },
] as const;

export const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;

export const PRIORITY_OPTIONS = ["P0", "P1", "P2", "P3"] as const;

export const IMPACT_VALUES = [0, 1, 2, 3] as const;

export const CALENDAR_DAYS = [
  { day: 0, key: "mon", label: "Пн" },
  { day: 1, key: "tue", label: "Вт" },
  { day: 2, key: "wed", label: "Ср" },
  { day: 3, key: "thu", label: "Чт" },
  { day: 4, key: "fri", label: "Пт" },
  { day: 5, key: "sat", label: "Сб" },
  { day: 6, key: "sun", label: "Вс" },
] as const;

export const NOTIFICATION_CATALOG = [
  {eventType:"sla_reminder_sent",title:"Напоминания о сроках",description:"Напоминания о приближении или нарушении срока обработки обращения."},
  {
    eventType: "ticket_message",
    title: "Новые сообщения в обращениях",
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
    description: "Обращение перешло в работу, ожидание, решение или закрытие.",
  },
  {
    eventType: "assignment_changed",
    title: "Назначение исполнителя",
    description: "Тикет назначен на пользователя или очередь.",
  },
  {
    eventType: "sla_breached",
    title: "Срок ответа или решения нарушен",
    description: "Напоминание о нарушенном сроке ответа или решения.",
  },
  {
    eventType: "mention",
    title: "Упоминания",
    description: "Адресные события, которые лучше оставлять включёнными.",
  },
] as const;

export const TECH_ALERT_CATALOG = [
  "connection_request_stuck_pending",
  "connection_request_token_limit",
  "agent_update_failed",
  "observer_degradation",
  "inventory_duplicate_env_uuid",
] as const;

export type WorkflowTransitionEntry = string | Record<string, unknown>;

export type WorkflowTransitionsJson = Record<string, WorkflowTransitionEntry[]>;
