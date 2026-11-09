import type { WebSettingsPayload } from "../settings/api";

export type ScenarioProcessingRegistry = Pick<WebSettingsPayload, "queues" | "calendars"> & Partial<Pick<WebSettingsPayload, "ticket_settings">>;

/** Operational choices do not rewrite historical queue references. */
export function scenarioQueueSettings(registry: ScenarioProcessingRegistry | null) {
 const flags = registry?.ticket_settings?.operational_flags;
 const unified = flags?.queue_mode === "unified";
 const commonCode = flags?.take_queue_common_code?.trim() ?? "";
 const queues = registry?.queues.filter(queue => queue.is_active && (!unified || queue.code === commonCode)) ?? [];
 return { unified, queues, defaultCode: unified && queues.some(queue => queue.code === commonCode) ? commonCode : "" };
}
