import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { summarizeTerminalSla, terminalSlaSummary } from "./scenario-terminal-sla-model";
import type { ScenarioSimulation } from "./scenario-api";

function slaDefinition(): ScenarioDraftDefinition {
 return { schema_version: 4, scenario_key: "test", service_code: "test", offering_full_code: "test.test", title: "Test", process_binding: { request_template_key: "test" }, entry_block_id: "start",
  processing: { defaults: { route: "desk", sla_profile: "normal" }, routes: { desk: { title: "Desk", queue_code: "desk" } }, sla_profiles: {
   normal: { title: "Обычный", first_response_minutes: 30, resolution_minutes: 480, time_basis: "calendar" }, fast: { title: "Срочный", first_response_minutes: 5, resolution_minutes: 60, time_basis: "business", calendar_id: 3 },
  } }, blocks: [{ id: "start", kind: "navigation", title: "Начало", transitions: [{ to: "end" }] }, { id: "end", kind: "submit_ticket", title: "Обращение" }] };
}
describe("terminal SLA path summary", () => {
 it("keeps exact inherited values and never mutates the draft", () => {
  const definition = slaDefinition(), before = JSON.stringify(definition);
  const result = summarizeTerminalSla(definition, "end");
  expect(result.alternatives).toHaveLength(1);
  expect(result.alternatives[0].selection).toMatchObject({ kind: "profile", key: "normal" });
  expect(result.alternatives[0].profile?.resolution_minutes).toBe(480);
  expect(JSON.stringify(definition)).toBe(before);
 });
 it("applies an explicit edge after its SLA block and terminal last", () => {
  const definition = slaDefinition();
  definition.blocks![0] = { id: "start", kind: "sla", title: "Настройка", sla_profile: "fast", transitions: [{ to: "end", processing: { sla_profile: "normal" } }] };
  expect(summarizeTerminalSla(definition, "end").alternatives[0].selection.key).toBe("normal");
  definition.blocks![1] = { ...definition.blocks![1], kind: "submit_ticket", sla_profile: "fast" };
  const result = summarizeTerminalSla(definition, "end").alternatives[0];
  expect(result.selection).toMatchObject({ key: "fast", source: expect.stringContaining("завершение") });
  expect(result.profile?.time_basis).toBe("business");
 });
 it("retains entrance and conditional route provenance as alternatives", () => {
  const definition = slaDefinition();
  definition.entry_points = [{ key: "direct", title: "Прямой вход", target_block_id: "end" }, { key: "off", title: "Выключен", target_block_id: "end", enabled: false }];
  definition.blocks![0].transitions = [{ to: "end", when: { source: "answer", field: "answer", op: "eq", value: true }, processing: { sla_profile: "fast" } }, { to: "end" }];
  const result = summarizeTerminalSla(definition, "end");
  expect(result.alternatives).toHaveLength(3);
  expect(result.alternatives.filter(item => item.conditional)).toHaveLength(2);
  expect(result.alternatives.some(item => item.route.includes("Прямой вход"))).toBe(true);
  expect(result.alternatives.some(item => item.route.includes("Выключен"))).toBe(false);
  expect(terminalSlaSummary(definition, definition.blocks![1])).toContain("зависит от пути");
 });
 it("keeps registry policy values unknown and applies terminal policy last", () => {
  const definition = slaDefinition(); definition.processing = null;
  definition.process_binding.policy_refs = { sla: "base" };
  definition.blocks![0] = { id: "start", kind: "sla", title: "Правило", policy_ref: "middle", transitions: [{ to: "end" }] };
  definition.blocks![1] = { ...definition.blocks![1], kind: "submit_ticket", policy_ref: "final" };
  const result = summarizeTerminalSla(definition, "end").alternatives[0];
  expect(result.selection).toMatchObject({ kind: "policy", key: "final" });
  expect(result.profile).toBeUndefined();
 });
 it("reports cycles and truncation, and ignores unrelated terminals", () => {
  const definition = slaDefinition();
  definition.blocks![0].transitions = [{ to: "start" }, { to: "end" }];
  expect(summarizeTerminalSla(definition, "end").cyclic).toBe(true);
  definition.blocks = [...Array.from({ length: 130 }, (_, index) => ({ id: `n${index}`, kind: "navigation" as const, title: `N${index}`, transitions: [{ to: index === 129 ? "end" : `n${index + 1}` }, { to: "end" }] })), definition.blocks![1]];
  definition.entry_block_id = "n0";
  const result = summarizeTerminalSla(definition, "end");
  expect(result.truncated).toBe(true); expect(result.explored).toBeLessThanOrEqual(256); expect(result.alternatives.length).toBeLessThanOrEqual(64);
 });
 it("finish has no ticket SLA even when a previous block assigned one", () => {
  const definition = slaDefinition(); definition.blocks![1] = { id: "end", kind: "finish", title: "Готово" };
  expect(summarizeTerminalSla(definition, "end").alternatives).toEqual([]);
  expect(terminalSlaSummary(definition, definition.blocks![1])).toContain("без обращения");
 });
 it("shows the actual server values only for the current terminal", () => {
  const definition = slaDefinition(), block = definition.blocks![1];
  const result = { current_block: block, state: { current_block_id: "end" }, processing: { sla: { first_response_min: 12, resolution_min: 144, time_basis: "business", source: { kind: "terminal", block_id: "end" } }, routing: { queue_title: "Инженеры" } } } as unknown as ScenarioSimulation;
  expect(terminalSlaSummary(definition, block, result)).toContain("144 мин.");
  expect(terminalSlaSummary(definition, block, { ...result, current_block: definition.blocks![0] })).not.toContain("144 мин.");
 });
 it("tracks the last explicit route separately from SLA", () => {
  const definition = slaDefinition();
  definition.processing!.routes.special = { title: "Специалисты", queue_code: "special" };
  definition.blocks![0].transitions![0].processing = { route: "special" };
  expect(summarizeTerminalSla(definition, "end").alternatives[0].routing).toMatchObject({ key: "special", queue_code: "special" });
 });
});
