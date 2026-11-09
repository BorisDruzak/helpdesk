import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { connectPolicyAttachment, detachPolicyAttachment, policyAttachmentsFor, reassignPolicyAttachments } from "./scenario-policy-attachments-model";
import { addMapBlock, appendMapStep, connectBlocks, connectStart, deleteMapBlock, insertOnTransition, mapPalette } from "./scenario-map-model";

const draft = (): ScenarioDraftDefinition => ({ schema_version: 4, scenario_key: "test", title: "Карта", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
 { id: "q", kind: "instruction", title: "Начало", content: { body: "Помощь" }, transitions: [{ to: "end" }] },
 { id: "end", kind: "submit_ticket", title: "Обращение" },
 { id: "sla", kind: "sla_attachment", title: "SLA", sla_profile: "fast" },
 { id: "route", kind: "routing_attachment", title: "Маршрут", route: "desk" },
] });
describe("map policy attachments", () => {
 it("connects, replaces and detaches settings without flow transitions or input mutations", () => {
  const d = draft(), before = structuredClone(d), connected = connectPolicyAttachment(d, "sla", "q");
  expect(policyAttachmentsFor(connected, "q").map(item => item.id)).toEqual(["sla"]);
  expect(connected.blocks![0].transitions).toEqual([{ to: "end" }]);
  expect(policyAttachmentsFor(connectPolicyAttachment(connected, "sla", "end"), "end")).toHaveLength(1);
  expect(policyAttachmentsFor(detachPolicyAttachment(connected, "sla"), "q")).toEqual([]);
  expect(d).toEqual(before);
 });
 it("rejects missing targets, settings targets, and same-kind conflicts atomically", () => {
  const d = connectPolicyAttachment(draft(), "sla", "q");
  d.blocks!.push({ id: "sla2", kind: "sla_attachment", title: "Второй SLA" });
  expect(() => connectPolicyAttachment(d, "sla2", "q")).toThrow(/уже/);
  expect(() => connectPolicyAttachment(d, "sla", "route")).toThrow(/настройк/);
  expect(() => connectPolicyAttachment(d, "sla", "missing")).toThrow(/существующ/);
  expect(policyAttachmentsFor(connectPolicyAttachment(d, "route", "q"), "q")).toHaveLength(2);
 });
 it("redirects attachments explicitly on deletion or leaves unattached editable drafts", () => {
  const d = connectPolicyAttachment(draft(), "sla", "q");
  expect(reassignPolicyAttachments(d, "q", "end").blocks!.find(item => item.id === "sla")).toMatchObject({ attached_to: "end" });
  expect(deleteMapBlock(d, "q", "end").blocks!.find(item => item.id === "sla")).toMatchObject({ attached_to: "end" });
  expect(deleteMapBlock(d, "q", null, "remove", "detach").blocks!.find(item => item.id === "sla")).not.toHaveProperty("attached_to");
  const conflict = connectPolicyAttachment({ ...d, blocks: [...d.blocks!, { id: "sla2", kind: "sla_attachment", title: "Другой SLA" }] }, "sla2", "end");
  expect(() => deleteMapBlock(conflict, "q", "end")).toThrow(/уже/);
 });
 it("adds modifiers only as settings and never makes them an entrance or ordinary step", () => {
  const d = draft();
  expect(mapPalette.find(item => item.label === "Сроки обработки")?.kind).toBe("sla_attachment");
  expect(mapPalette.find(item => item.label === "Маршрут")?.kind).toBe("routing_attachment");
  expect(() => connectBlocks(d, "q", "sla")).toThrow(/прикреп/);
  expect(() => connectBlocks(d, "sla", "q")).toThrow(/прикреп/);
  expect(() => connectStart(d, "sla")).toThrow(/настройк/i);
  expect(() => appendMapStep(d, "q", "sla_attachment")).toThrow(/прикреп/);
  expect(() => insertOnTransition(d, "q", 0, "routing_attachment")).toThrow(/прикреп/);
  const empty = { ...d, blocks: [], entry_block_id: null };
  const next = addMapBlock(empty, "sla_attachment", { x: 1, y: 2 });
  expect(next.entry_block_id).toBeNull(); expect(next.blocks![0]).not.toHaveProperty("transitions");
 });
});
