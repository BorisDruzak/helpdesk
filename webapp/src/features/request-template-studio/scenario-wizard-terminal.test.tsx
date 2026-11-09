import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as renderView, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioWizard } from "./scenario-wizard";
function render(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderView(ui, { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
}
vi.mock("./scenario-map-workbench",()=>({ScenarioMapWorkbench:({simulationResult,onTest,inspectorPanel}:any)=><div><button onClick={onTest}>Открыть тест</button><output data-testid="result">{simulationResult?.revision??"нет"}</output>{inspectorPanel}</div>}));
vi.mock("./scenario-simulation",()=>({ScenarioSimulationPanel:({revision,onState}:any)=><button onClick={()=>onState("end",["q"],{revision,state:{current_block_id:"end"}})}>Получить результат</button>}));
vi.mock("./scenario-author-attachments",()=>({ScenarioAuthorAttachmentProvider:({children}:any)=>children}));
vi.mock("./scenario-requester-preview",()=>({ScenarioPagePreview:()=> <section aria-label="Страница сотрудника">Визуальное оформление черновика</section>}));
it("opens employee visual preview from the top actions even for an unsaved draft",()=>{
 render(<ScenarioWizard definition={{scenario_key:"test",blocks:[],process_binding:{request_template_key:"t"}} as never} detail={null} catalog={{offerings:[],services:[],categories:[]} as never} disabled={false} dirty onChange={vi.fn()}/>);
 fireEvent.click(screen.getByRole("button",{name:"Вернуться к карте"}));
 fireEvent.click(screen.getByRole("button",{name:"Как у сотрудника"}));
 expect(screen.getByRole("region",{name:"Страница сотрудника"})).toBeVisible();
});
it("discards an actual terminal result on draft edits, revision and disabled changes",()=>{
 const props:any={definition:{scenario_key:"test",blocks:[],process_binding:{request_template_key:"t"}},detail:{scenario:{id:"s"},draft:{revision:1}},catalog:{offerings:[]},disabled:false,dirty:false,onChange:vi.fn()};
 const view=render(<ScenarioWizard {...props}/>);
 fireEvent.click(screen.getByRole("button",{name:"Открыть тест"}));
 fireEvent.click(screen.getByRole("button",{name:"Получить результат"}));
 expect(screen.getByTestId("result")).toHaveTextContent("1");
 view.rerender(<ScenarioWizard {...props} dirty/>);
 expect(screen.getByTestId("result")).toHaveTextContent("нет");
 view.rerender(<ScenarioWizard {...props}/>);
 expect(screen.getByTestId("result")).toHaveTextContent("нет");
 fireEvent.click(screen.getByRole("button",{name:"Получить результат"}));
 view.rerender(<ScenarioWizard {...props} detail={{...props.detail,draft:{revision:2}}}/>);
 expect(screen.getByTestId("result")).toHaveTextContent("нет");
 fireEvent.click(screen.getByRole("button",{name:"Получить результат"}));
 expect(screen.getByTestId("result")).toHaveTextContent("2");
 view.rerender(<ScenarioWizard {...props} disabled/>);
 expect(screen.getByTestId("result")).toHaveTextContent("нет");
});
