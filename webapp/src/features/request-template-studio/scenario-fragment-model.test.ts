import { expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { insertBuiltinFragment } from "./scenario-fragment-model";
it("inserts a reusable SLA question fragment atomically with independent keys and separate effects", () => {
  const definition: ScenarioDraftDefinition = { schema_version: 4, execution_semantics: 3, scenario_key: "s", title: "S", service_code: "it", offering_full_code: "it.s", process_binding: { request_template_key: "s" }, blocks: [] };
  const one = insertBuiltinFragment(definition, "impact", { x: 5000, y: -4000 });
  const two = insertBuiltinFragment(one, "impact", { x: 6000, y: -4000 });
  expect(new Set(two.blocks!.map(block => block.id)).size).toBe(two.blocks!.length);
  expect(two.blocks!.filter(block => block.kind === "sla")).toHaveLength(6);
  const question = one.blocks!.find(block => block.kind === "form_page")!;
  expect(question.kind === "form_page" && question.fields[0].process_mapping).toBeUndefined();
  expect(one.editor_layout!.positions![one.blocks![0].id].x).toBeGreaterThan(4000);
  expect(definition.blocks).toEqual([]);
});
