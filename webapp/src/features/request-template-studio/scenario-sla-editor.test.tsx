import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { vi } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioSlaEditor } from "./scenario-sla-editor";
const draft = (): ScenarioDraftDefinition => ({ schema_version: 4, title: "Карта", scenario_key: "s", service_code: "it", offering_full_code: "it.s", process_binding: { request_template_key: "s" }, entry_block_id: "end", blocks: [{ id: "end", kind: "submit_ticket", title: "Обращение" }, { id: "sla", kind: "sla", title: "Мой SLA", sla_profile: "fast", processing_facts: { urgency: "blocked" }, transitions: [] }], processing: { defaults: { route: "desk", sla_profile: "fast" }, routes: {}, sla_profiles: {} } });
it("converts only an isolated legacy SLA after an explicit author action", () => {
 const definition = draft(), block = definition.blocks![1]; if (block.kind !== "sla") throw new Error(); const change = vi.fn();
 render(<ScenarioSlaEditor block={block} definition={definition} disabled={false} onChange={change} />);
 expect(change).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole("button", { name: "Использовать как настройку блока" }));
 expect(change.mock.lastCall![0].blocks[1]).toEqual({ id: "sla", title: "Мой SLA", kind: "sla_attachment", sla_profile: "fast", processing_facts: { urgency: "blocked" }, attached_to: null });
});
it("never offers conversion for connected, entered or old-version legacy SLA", () => {
 for (const variant of ["outgoing", "incoming", "start", "entry", "schema"] as const) {
  const definition = draft(), block = definition.blocks![1]; if (block.kind !== "sla") throw new Error();
  if (variant === "outgoing") block.transitions = [{ to: "end" }];
  if (variant === "incoming") definition.blocks![0].transitions = [{ to: "sla" }];
  if (variant === "start") definition.entry_block_id = "sla";
  if (variant === "entry") definition.entry_points = [{ key: "e", title: "Вход", target_block_id: "sla" }];
  if (variant === "schema") definition.schema_version = 3;
  const { unmount } = render(<ScenarioSlaEditor block={block} definition={definition} disabled={false} onChange={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Использовать как настройку блока" })).not.toBeInTheDocument(); unmount();
 }
});
