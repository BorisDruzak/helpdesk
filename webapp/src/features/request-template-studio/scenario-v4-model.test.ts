import { expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { upgradeScenarioDraft, setNavigationMode } from "./scenario-v4-model";
it.each([1, 2, 3] as const)("keeps source semantics and question data when enabling v4 for v%i", version => {
  const definition: ScenarioDraftDefinition = { schema_version: version, scenario_key: "s", title: "S", service_code: "it", offering_full_code: "it.s", process_binding: { request_template_key: "s" }, blocks: [{ id: "q", kind: "form_page", title: "Q", fields: [{ key: "a", type: "checkbox", label: "A", required: true }] }] };
  const before = structuredClone(definition), next = upgradeScenarioDraft(definition);
  expect(next).toMatchObject({ schema_version: 4, execution_semantics: version, blocks: before.blocks, process_binding: before.process_binding });
  expect(definition).toEqual(before);
});
it("requires explicit labels for old routes and never truncates more than ten", () => {
  const block = { id: "n", kind: "instruction" as const, title: "N", content: { body: "T" }, transitions: Array.from({ length: 11 }, () => ({ to: "end" })) };
  expect(() => setNavigationMode(block, "buttons")).toThrow(/10/);
  const next = setNavigationMode({ ...block, transitions: [{ to: "end" }] }, "buttons");
  expect(next.transitions?.[0].button).toMatchObject({ label: "Продолжить" });
  expect(setNavigationMode(next, "automatic").transitions?.[0].button).toBeUndefined();
});
