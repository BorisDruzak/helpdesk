import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { summarizeTerminalSla, terminalActualSla, terminalSlaSummary } from "./scenario-terminal-sla-model";
import type { ScenarioSimulation } from "./scenario-api";

function slaDefinition(): ScenarioDraftDefinition {
 return { schema_version: 4, scenario_key: "test", service_code: "test", offering_full_code: "test.test", title: "Test", process_binding: { request_template_key: "test" }, entry_block_id: "start",
  processing: { defaults: { route: "desk", sla_profile: "normal" }, routes: { desk: { title: "Desk", queue_code: "desk" } }, sla_profiles: {
   normal: { title: "Обычный", first_response_minutes: 30, resolution_minutes: 480, time_basis: "calendar" }, fast: { title: "Срочный", first_response_minutes: 5, resolution_minutes: 60, time_basis: "business", calendar_id: 3 },
  } }, blocks: [{ id: "start", kind: "navigation", title: "Начало", transitions: [{ to: "end" }] }, { id: "end", kind: "submit_ticket", title: "Обращение" }] };
}
describe("terminal SLA path summary", () => {
 it.each(["profile", "policy"] as const)("applies attached %s before the visited legacy SLA block, matching server replay", mode => {
  const definition = slaDefinition();
  if (mode === "policy") definition.processing = null;
  definition.blocks![0] = { id: "start", kind: "sla", title: "Обычный последовательный SLA", sla_profile: mode === "profile" ? "normal" : undefined, policy_ref: mode === "policy" ? "standard" : undefined, transitions: [{ to: "end" }] };
  definition.blocks!.push({ id: "urgent", kind: "sla_attachment", title: "Срочная настройка", attached_to: "start", sla_profile: mode === "profile" ? "fast" : undefined, policy_ref: mode === "policy" ? "urgent" : undefined });
  const before = structuredClone(definition);
  expect(summarizeTerminalSla(definition, "end").alternatives[0].selection).toEqual({ kind: mode, key: mode === "profile" ? "normal" : "standard", source: "блок сроков «Обычный последовательный SLA»" });
  expect(definition).toEqual(before);
 });
 it("replays attachments before selected transitions and explicit terminal selections last", () => {
  const d = slaDefinition(); d.processing!.routes.special = { title: "Специалисты", queue_code: "special" };
  d.blocks!.push({ id: "sa", kind: "sla_attachment", title: "Привязанный SLA", attached_to: "start", sla_profile: "fast" }, { id: "ra", kind: "routing_attachment", title: "Привязанный маршрут", attached_to: "start", route: "special" });
  expect(summarizeTerminalSla(d, "end").alternatives[0]).toMatchObject({ selection: { key: "fast", source: expect.stringContaining("Привязанный SLA") }, routing: { key: "special", source: expect.stringContaining("Привязанный маршрут") } });
  expect(summarizeTerminalSla(d, "end").alternatives[0].route).not.toContain("Привязанный SLA");
  d.blocks![0].transitions![0].processing = { sla_profile: "normal", route: "desk" };
  expect(summarizeTerminalSla(d, "end").alternatives[0]).toMatchObject({ selection: { key: "normal" }, routing: { key: "desk" } });
  d.blocks!.push({ id: "final-sla", kind: "sla_attachment", title: "SLA результата", attached_to: "end", sla_profile: "fast" }, { id: "final-route", kind: "routing_attachment", title: "Маршрут результата", attached_to: "end", route: "special" });
  expect(summarizeTerminalSla(d, "end").alternatives[0]).toMatchObject({ selection: { key: "fast" }, routing: { key: "special" } });
  d.blocks![1] = { id: "end", kind: "submit_ticket", title: "Обращение", sla_profile: "normal", route: "desk" };
  expect(summarizeTerminalSla(d, "end").alternatives[0]).toMatchObject({ selection: { key: "normal", source: expect.stringContaining("завершение") }, routing: { key: "desk", source: expect.stringContaining("завершение") } });
  expect(summarizeTerminalSla(d, "end", { inheritOnly: true }).alternatives[0]).toMatchObject({ selection: { key: "fast" }, routing: { key: "special" } });
 });
 it("inherits only visited routing policies and overrides them explicitly at the terminal", () => {
  const d = slaDefinition(); d.processing = null; d.process_binding.policy_refs = { routing: "base" };
  d.blocks!.push({ id: "ra", kind: "routing_attachment", title: "Маршрут", attached_to: "start", policy_ref: "visited" }, { id: "off", kind: "routing_attachment", title: "Не посещён", attached_to: "other", policy_ref: "unvisited" });
  expect(summarizeTerminalSla(d, "end").alternatives[0].routingSelection).toMatchObject({ kind: "policy", key: "visited" });
  d.blocks![1] = { id: "end", kind: "submit_ticket", title: "Обращение", routing_policy_ref: "final" };
  expect(summarizeTerminalSla(d, "end").alternatives[0].routingSelection).toMatchObject({ kind: "policy", key: "final" });
 });
 it("labels actual SLA and routing attachments by modifier and visited target", () => {
  const definition = slaDefinition(); definition.blocks!.push({ id: "sa", kind: "sla_attachment", title: "Срочный SLA", attached_to: "start" }, { id: "ra", kind: "routing_attachment", title: "Маршрут специалистов", attached_to: "end" });
  const block = definition.blocks![1];
  const result = { current_block: block, state: { current_block_id: "end", history: ["start", "end"] }, processing: { sla: { first_response_min: 5, resolution_min: 60, source: { kind: "attachment", block_id: "sa", attached_to: "start" } }, routing: { queue_title: "Специалисты", source: { kind: "attachment", block_id: "ra", attached_to: "end" } } } } as unknown as ScenarioSimulation;
  const actual = terminalActualSla(definition, block, result);
  expect(actual?.source).toBe("настройка «Срочный SLA» у блока «Начало»"); expect(actual?.routingSource).toBe("настройка «Маршрут специалистов» у блока «Обращение»");
  expect(actual?.route).toEqual(["Начало", "Обращение"]); expect(actual?.queue).toBe("Специалисты");
 });
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
  expect(terminalSlaSummary(definition, definition.blocks![1])).toContain("зависят от пути");
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
 it("shows service policy inheritance for empty v4 fallbacks without inventing durations", () => {
  const definition = slaDefinition();
  definition.processing!.defaults = { route: "", sla_profile: "" };
  definition.blocks![0].transitions = [{ to: "end" }];
  definition.process_binding.policy_refs = { sla: "priority-sla", routing: "service-route" };
  const alternative = summarizeTerminalSla(definition, "end").alternatives[0];
  expect(alternative.selection).toMatchObject({ kind: "policy", key: "priority-sla" });
  expect(alternative.routingSelection).toMatchObject({ kind: "policy", key: "service-route" });
  expect(alternative.profile).toBeUndefined();
  expect(terminalSlaSummary(definition, definition.blocks![1])).toContain("сроки в проверке пути");
 });
});
