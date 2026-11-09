import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ScenarioProcessingResult } from "./scenario-processing-result";
import type { ScenarioSimulation } from "./scenario-api";

afterEach(cleanup);
it("renders canonical service policy results when map overrides are null", () => {
 const result = { state: { history: [], current_block_id: "submit", answers: {}, results: {} }, map_processing: { assignment_mode: "last_matching_branch", route: null, sla_profile: null, trace: [] }, processing: { priority: { priority_class: "P2" }, routing: { queue_title: "Общая поддержка", source: { kind: "server" } }, sla: { first_response_min: 23, resolution_min: 95, source: { kind: "server" } }, approval: { required: false }, would_create_ticket: false } } as unknown as ScenarioSimulation;
 render(<ScenarioProcessingResult result={result} />);
 expect(screen.getByText("Первый ответ: 23 мин.")).toBeVisible();
 expect(screen.getByText("Срок выполнения: 95 мин.")).toBeVisible();
 expect(screen.getByText("Источник сроков для сотрудника: серверная политика услуги.")).toBeVisible();
 expect(screen.getByText(/Приоритет рассчитан сервером по проверенным ответам и действующей политике/)).toBeVisible();
});
it("shows actual SLA durations, time basis and terminal override source", () => {
 const result = {state:{history:["question"],current_block_id:"submit",answers:{},results:{}},processing:{priority:{priority_class:"P2"},routing:{queue_code:"support"},sla:{first_response_min:17,resolution_min:83,time_basis:"business",source:{kind:"terminal",block_id:"submit"},selection:{kind:"policy",key:"published",source:{kind:"terminal",block_id:"submit"}}},approval:{required:false},would_create_ticket:false}} as unknown as ScenarioSimulation;
 render(<ScenarioProcessingResult result={result} definition={{scenario_key:"map",service_code:"it",offering_full_code:"it.print",title:"Print",process_binding:{request_template_key:"printer"},blocks:[{id:"submit",title:"Отправка",kind:"submit_ticket"}]}} />);
 expect(screen.getByText("Первый ответ: 17 мин.")).toBeInTheDocument();
 expect(screen.getByText("Срок выполнения: 83 мин.")).toBeInTheDocument();
 expect(screen.getByText("Рабочее время")).toBeInTheDocument();
 expect(screen.getByText(/итоговый выбор в блоке «Отправка»/)).toBeInTheDocument();
});
it("shows actual queue, visited path and both attachment sources with target context", () => {
 const result = { state: { history: ["question", "submit"], current_block_id: "submit", answers: {}, results: {} }, processing: { priority: { priority_class: "P2" }, routing: { queue_title: "Инженеры", selection: { kind: "policy", key: "published-routing", source: { kind: "attachment", block_id: "ra", attached_to: "submit" } } }, sla: { first_response_min: 7, resolution_min: 42, time_basis: "calendar", source: { kind: "attachment", block_id: "sa", attached_to: "question" } }, approval: { required: false }, would_create_ticket: false } } as unknown as ScenarioSimulation;
 render(<ScenarioProcessingResult result={result} definition={{ scenario_key: "map", service_code: "it", offering_full_code: "it.print", title: "Print", process_binding: { request_template_key: "printer" }, blocks: [{ id: "question", title: "Проблема", kind: "form_page", fields: [] }, { id: "submit", title: "Отправка", kind: "submit_ticket" }, { id: "sa", title: "Срочный SLA", kind: "sla_attachment", attached_to: "question" }, { id: "ra", title: "Маршрут инженеров", kind: "routing_attachment", attached_to: "submit" }] }} />);
 expect(screen.getByText("Проблема → Отправка")).toBeInTheDocument(); expect(screen.getByText("Очередь: Инженеры")).toBeInTheDocument();
 expect(screen.getByText("Источник сроков для сотрудника: настройка «Срочный SLA» у блока «Проблема».")).toBeInTheDocument();
 expect(screen.getByText("Источник очереди: настройка «Маршрут инженеров» у блока «Отправка».")).toBeInTheDocument();
});
