import { expect, it } from "vitest";
import { scenarioQueueSettings, type ScenarioProcessingRegistry } from "./scenario-policy-settings";

// The helper consumes only queue identity/activity and these two flags.
const settings = (queue_mode: string, take_queue_common_code: string, active = true) => ({ queues: [{ code: "configured", name: "Общая", is_active: active }, { code: "legacy", name: "Старая", is_active: true }], calendars: [], ticket_settings: { operational_flags: { queue_mode, take_queue_common_code } } }) as unknown as ScenarioProcessingRegistry;
it("uses only the configured active common queue in unified mode", () => {
 const result = scenarioQueueSettings(settings("unified", "configured"));
 expect(result.queues.map(queue => queue.code)).toEqual(["configured"]);
 expect(result.defaultCode).toBe("configured");
});
it.each([["missing", true], ["configured", false]])("does not invent a common queue when configuration cannot be selected", (code, active) => {
 expect(scenarioQueueSettings(settings("unified", code, active))).toMatchObject({ queues: [], defaultCode: "" });
});
it("keeps active queues available in partitioned mode without inventing a default", () => {
 expect(scenarioQueueSettings(settings("partitioned", "configured"))).toMatchObject({ defaultCode: "", queues: [{ code: "configured" }, { code: "legacy" }] });
});
