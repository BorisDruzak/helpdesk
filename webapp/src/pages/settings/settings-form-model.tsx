

import {type QueueItem, type RoutingRuleItem, type SlaPolicyItem, type CalendarItem, type ResolutionCodeItem, type QueueDraft, type RoutingDraft, type RoutingConditionBuilder, type PolicyDraft, type CalendarDayDraft, type CalendarHolidayDraft, type CalendarDraft, type ResolutionDraft, type OlaDraftRow, type SlaTargetDraftRow, type PriorityMatrixDraftRow, PRIORITIES, IMPACT_VALUES, CALENDAR_DAYS} from './settings-types';

export function formatDateTime(value: string | null | undefined): string {
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

export function prettyJson(value: unknown): string {
  if (!value) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

export function readBusinessHoursMode(value: Record<string, unknown> | null | undefined): PolicyDraft["business_hours_mode"] {
  return value?.mode === "calendar" ? "calendar" : "always_on";
}

export function buildBusinessHoursJson(mode: PolicyDraft["business_hours_mode"]): Record<string, unknown> | null {
  return mode === "calendar" ? { mode: "calendar" } : null;
}

export function defaultCalendarHours(): CalendarDayDraft[] {
  return CALENDAR_DAYS.map((item) => ({
    day: item.day,
    enabled: item.day < 5,
    start: "09:00",
    end: "18:00",
  }));
}

export function dayIndexFromKey(value: string): number | null {
  const normalized = value.toLowerCase().slice(0, 3);
  const found = CALENDAR_DAYS.find((item) => item.key === normalized);
  return found?.day ?? null;
}

export function readCalendarHours(value: unknown): CalendarDayDraft[] {
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

export function buildCalendarHoursJson(rows: CalendarDayDraft[]): Record<string, unknown> {
  return Object.fromEntries(
    rows
      .filter((row) => row.enabled)
      .map((row) => {
        const dayKey = CALENDAR_DAYS.find((item) => item.day === row.day)?.key ?? String(row.day);
        return [dayKey, [[row.start || "09:00", row.end || "18:00"]]];
      }),
  );
}

export function createHolidayDraft(date = "", index = 0): CalendarHolidayDraft {
  return {
    id: `${date || "new"}:${index}:${Math.random().toString(16).slice(2)}`,
    date,
  };
}

export function readHolidayRows(value: unknown): CalendarHolidayDraft[] {
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

export function buildHolidaysJson(rows: CalendarHolidayDraft[]): Record<string, unknown> {
  return {
    dates: rows
      .map((item) => item.date.trim())
      .filter(Boolean),
  };
}

export function buildQueueDraft(queue: QueueItem | null): QueueDraft {
  return {
    code: queue?.code ?? "",
    name: queue?.name ?? "",
    is_triage: queue?.is_triage ?? false,
    is_active: queue?.is_active ?? true,
    auto_assign_enabled: queue?.auto_assign_enabled ?? true,
  };
}

export function buildRoutingDraft(rule: RoutingRuleItem | null, fallbackQueueId: number | null): RoutingDraft {
  return {
    enabled: rule?.enabled ?? true,
    priority_order: rule?.priority_order ?? 100,
    target_queue_id: rule?.target_queue_id ?? fallbackQueueId ?? 0,
  };
}

export function isLeafRoutingCondition(value: Record<string, unknown> | null | undefined): value is {
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

export function buildRoutingConditionBuilder(
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

export function buildRoutingConditionJson(builder: RoutingConditionBuilder): Record<string, unknown> {
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

export function buildPolicyDraft(policy: SlaPolicyItem | null): PolicyDraft {
  return {
    name: policy?.name ?? "",
    timezone: policy?.timezone ?? "UTC",
    calendar_id: policy?.calendar_id ? String(policy.calendar_id) : "",
    is_default: policy?.is_default ?? false,
    is_active: policy?.is_active ?? true,
    business_hours_mode: readBusinessHoursMode(policy?.business_hours_json),
  };
}

export function buildCalendarDraft(calendar: CalendarItem | null): CalendarDraft {
  return {
    code: calendar?.code ?? "",
    name: calendar?.name ?? "",
    timezone: calendar?.timezone ?? "UTC",
    is_active: calendar?.is_active ?? true,
    weekly_hours: readCalendarHours(calendar?.weekly_hours_json),
    holidays: readHolidayRows(calendar?.holidays_json),
  };
}

export function buildResolutionDraft(code: ResolutionCodeItem | null): ResolutionDraft {
  return {
    code: code?.code ?? "",
    name: code?.name ?? "",
    is_active: code?.is_active ?? true,
    sort_order: code?.sort_order ?? 0,
  };
}

export function buildOlaDraft(queue: QueueItem | null): OlaDraftRow[] {
  return PRIORITIES.map((priority) => {
    const existing = queue?.ola_targets.find((item) => item.priority === priority);
    return {
      priority,
      ack_min: existing?.ack_min ?? null,
      processing_min: existing?.processing_min ?? null,
    };
  });
}

export function buildSlaTargetsDraft(policy: SlaPolicyItem | null): SlaTargetDraftRow[] {
  return PRIORITIES.map((priority) => {
    const existing = policy?.targets.find((item) => item.priority === priority);
    return {
      priority,
      first_response_min: existing?.first_response_min ?? null,
      resolution_min: existing?.resolution_min ?? null,
    };
  });
}

export function buildPriorityMatrixDraft(policy: SlaPolicyItem | null): PriorityMatrixDraftRow[] {
  return IMPACT_VALUES.flatMap((impact) =>
    IMPACT_VALUES.map((urgency) => {
      const existing = policy?.priority_matrix.find((item) => item.impact === impact && item.urgency === urgency);
      return {
        impact,
        urgency,
        priority: existing?.priority ?? "",
      };
    })
  );
}

export function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
