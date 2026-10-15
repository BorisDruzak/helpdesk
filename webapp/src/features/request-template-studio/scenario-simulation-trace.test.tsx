import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScenarioSimulationComparison, ScenarioSimulationTrace } from "./scenario-simulation-trace";
import type { ScenarioSimulation } from "./scenario-api";

const result: ScenarioSimulation = { revision: 1, current_block: { id: "end", title: "Обращение", kind: "submit_ticket" }, state: { current_block_id: "end", revision: 2, state: "ready_to_submit", answers: { scale: "department" }, history: ["logic"], results: {} }, processing: { priority: { priority_class: "P1" }, routing: { queue_title: "Поддержка" }, sla: { first_response_min: 30, resolution_min: 120 }, approval: { required: true }, would_create_ticket: false, map_processing: { assignment_mode: "last_matching_branch", route: { key: "support", title: "Поддержка", queue_code: "support", source: { kind: "transition", block_id: "logic", transition_index: 0 } }, sla_profile: { key: "urgent", title: "Срочный", first_response_minutes: 30, resolution_minutes: 120, time_basis: "calendar", source: { kind: "default" } }, trace: [{ block_id: "logic", transition_index: 0, to: "end", matched: true, assignments: { route: "support", sla_profile: "urgent" } }], condition_trace: [{ block_id: "logic", transition_index: 0, to: "end", selected: true, condition_evaluation: { op: "and", matched: true, children: [{ op: "eq", matched: true, field: "scale", actual: "department", value: "department", present: true }, { op: "exists", matched: false, field: "missing", present: false }] } }] } } };
it("renders authoritative server source and nested matched/missing condition results", () => {
 render(<ScenarioSimulationTrace result={result} />);
 expect(screen.getByText(/настройка карты по умолчанию/)).toBeVisible();
 expect(screen.getByText(/ветвь 1.*выбрана/)).toBeVisible();
 expect(screen.getByText("Ответ отсутствует")).toBeInTheDocument();
 expect(screen.getByText(/Не выполнено/)).toBeInTheDocument();
});
it("compares two server computations without recomputing priority or SLA", () => {
 const second = structuredClone(result); second.processing!.sla.resolution_min = 300; second.processing!.priority.priority_class = "P3";
 render(<ScenarioSimulationComparison first={result} second={second} />);
 expect(screen.getByText(/решение: 120 мин/)).toBeVisible(); expect(screen.getByText(/решение: 300 мин/)).toBeVisible();
 expect(screen.getByText("Приоритет: P1")).toBeVisible(); expect(screen.getByText("Приоритет: P3")).toBeVisible();
});
it("shows final self-service conditions using top-level server trace without ticket deadlines", () => {
 const final = structuredClone(result);
 final.current_block.kind = "finish";
 final.map_processing = final.processing!.map_processing;
 final.processing = null;
 render(<ScenarioSimulationTrace result={final} />);
 expect(screen.getByText(/ветвь 1.*выбрана/)).toBeVisible();
 expect(screen.getByText("Ответ отсутствует")).toBeInTheDocument();
 expect(screen.queryByText(/Срок выполнения/)).not.toBeInTheDocument();
});
