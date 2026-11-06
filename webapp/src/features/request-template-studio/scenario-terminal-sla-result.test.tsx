import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ScenarioProcessingResult } from "./scenario-processing-result";
import type { ScenarioSimulation } from "./scenario-api";

afterEach(cleanup);
it("shows actual SLA durations, time basis and terminal override source", () => {
 const result = {state:{history:["question"],current_block_id:"submit",answers:{},results:{}},processing:{priority:{priority_class:"P2"},routing:{queue_code:"support"},sla:{first_response_min:17,resolution_min:83,time_basis:"business",source:{kind:"terminal",block_id:"submit"},selection:{kind:"policy",key:"published",source:{kind:"terminal",block_id:"submit"}}},approval:{required:false},would_create_ticket:false}} as unknown as ScenarioSimulation;
 render(<ScenarioProcessingResult result={result} definition={{scenario_key:"map",service_code:"it",offering_full_code:"it.print",title:"Print",process_binding:{request_template_key:"printer"},blocks:[{id:"submit",title:"Отправка",kind:"submit_ticket"}]}} />);
 expect(screen.getByText("Первый ответ: 17 мин.")).toBeInTheDocument();
 expect(screen.getByText("Срок выполнения: 83 мин.")).toBeInTheDocument();
 expect(screen.getByText("Рабочее время")).toBeInTheDocument();
 expect(screen.getByText(/итоговый выбор в блоке «Отправка»/)).toBeInTheDocument();
});
