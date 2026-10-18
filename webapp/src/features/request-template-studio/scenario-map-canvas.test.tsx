import { createElement, useState, type ComponentType } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioMapCanvas, type MapNode } from "./scenario-map-canvas";
import type { ScenarioDraftDefinition } from "./scenario-contract";

vi.mock("@xyflow/react", () => ({
  Background: () => null, Controls: () => null, MarkerType: { ArrowClosed: "arrow" }, Position: { Left: "left", Right: "right", Bottom: "bottom" },
  useUpdateNodeInternals: () => vi.fn(),
  useNodesState: (initial: MapNode[]) => { const [nodes, setNodes] = useState(initial); return [nodes, setNodes, vi.fn()]; },
  Handle: ({ id, "aria-label": label }: { id?: string; "aria-label"?: string }) => <span data-testid={`handle-${id ?? "target"}`} aria-label={label} />,
  ReactFlow: ({ nodes, edges, nodeTypes }: { nodes: MapNode[]; edges: { id: string; label: string }[]; nodeTypes: { scenario: ComponentType<{ id: string; data: MapNode["data"]; selected?: boolean }> } }) => <>{nodes.map(node => <div key={node.id} data-testid={`node-${node.id}`}>{createElement(nodeTypes.scenario, { id: node.id, data: node.data, selected: node.selected })}</div>)}{edges.map(edge => <span key={edge.id}>{edge.label}</span>)}</>,
}));
const definition: ScenarioDraftDefinition = { schema_version: 3, scenario_key: "test", service_code: "it", offering_full_code: "it.test", title: "Test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
  { id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "answer", type: "checkbox", label: "123" }], transitions: [{ to: "d" }] },
  { id: "d", kind: "decision", title: "Условие", transitions: [] },
  { id: "end", kind: "submit_ticket", title: "Обращение" },
] };
const props = { selected: "d", selectedEdge: null, disabled: false, onSelect: vi.fn(), onEdge: vi.fn(), onMove: vi.fn(), onConnect: vi.fn(), onReconnect: vi.fn(), onDropBlock: vi.fn(), onEntrance: vi.fn(), onEntranceReconnect: vi.fn(), onReady: vi.fn() };
it("offers explicit Yes and No actions on an empty decision without changing the definition", () => {
  const onAnswerAdd = vi.fn(), before = structuredClone(definition);
  render(<ScenarioMapCanvas {...props} definition={definition} onAnswerAdd={onAnswerAdd} />);
  expect(screen.getByText("По ответу: 123")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" }));
  expect(onAnswerAdd).toHaveBeenCalledWith("d", { source: "answer", field: "answer", op: "eq", value: false });
  expect(screen.getByRole("button", { name: "Добавить шаг для «Да» после «Условие»" })).toBeEnabled();
  expect(screen.getByTestId("handle-answer-0")).toBeInTheDocument(); expect(screen.getByTestId("handle-answer-1")).toBeInTheDocument();
  expect(definition).toEqual(before);
});
it("shows an existing typed answer branch with one reconnect handle and keeps the other answer available", () => {
  const next = structuredClone(definition); next.blocks![1].transitions = [{ to: "end", when: { source: "answer", field: "answer", op: "eq", value: true } }, { to: "end" }];
  render(<ScenarioMapCanvas {...props} definition={next} onAnswerAdd={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Добавить шаг для «Да» после «Условие»" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" })).toBeEnabled();
  expect(screen.getAllByTestId("handle-route-0")).toHaveLength(2); // One ordinary question route and one decision route.
  expect(screen.queryByTestId("handle-answer-0")).not.toBeInTheDocument();
  expect(screen.getByText(/123 равно «Да»/)).toBeVisible(); expect(screen.getByText("Иначе")).toBeVisible();
});
it("keeps answer choices visible but prevents answer actions for a read-only canvas", () => {
  const onAnswerAdd = vi.fn(); render(<ScenarioMapCanvas {...props} disabled definition={definition} onAnswerAdd={onAnswerAdd} />);
  const no = screen.getByRole("button", { name: "Добавить шаг для «Нет» после «Условие»" });
  expect(no).toBeDisabled(); fireEvent.click(no); expect(onAnswerAdd).not.toHaveBeenCalled();
});
