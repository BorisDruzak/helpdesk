import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioFragments } from "./scenario-fragments";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-fragment-api", async importOriginal => ({ ...await importOriginal<typeof import("./scenario-fragment-api")>(), fetchScenarioFragments: vi.fn().mockResolvedValue({items:[],total:0}) }));
const definition: ScenarioDraftDefinition = { schema_version:4, execution_semantics:3, scenario_key:"s", title:"S",service_code:"it",offering_full_code:"it.s",process_binding:{request_template_key:"s"},blocks:[] };
it("inserts a built-in fragment into an unsaved local draft", async () => {
 const inserted = vi.fn();
 render(<ScenarioFragments definition={definition} detail={null} dirty disabled={false} position={{x:5,y:6}} onLocalInsert={inserted} onInserted={vi.fn()} />);
 fireEvent.click(screen.getByRole("button", {name:"Описание проблемы со скриншотом"}));
 fireEvent.click(screen.getByRole("button", {name:"Добавить шаблон"}));
 expect(inserted).toHaveBeenCalledOnce();
 expect(inserted.mock.calls[0][0].blocks.length).toBeGreaterThan(0);
 await waitFor(() => expect(screen.getByText(/Сначала сохраните/)).toBeInTheDocument());
});
it("blocks built-in edits for read-only users", () => {
 render(<ScenarioFragments definition={definition} detail={null} dirty={false} disabled position={{x:0,y:0}} onLocalInsert={vi.fn()} onInserted={vi.fn()} />);
 expect(screen.getByRole("button", {name:"Описание проблемы со скриншотом"})).toBeDisabled();
});
it("requires explicit fact mapping and a saved v4 draft before insertion", async () => {
 const api = await import("./scenario-fragment-api");
 const destination = {...definition, blocks:[{id:"b",kind:"finish" as const,title:"Конец",transitions:[]}]};
 const detail = {scenario:{id:"s1",scenario_key:"s",service_code:"it",offering_full_code:"it.s",category_id:null,title:"S",description:"",archived:false,enabled:true,published_version_id:null},draft:{revision:2,definition:destination}};
 const fragment = {fragment:{id:"f1",title:"Готовый",revision:1,block_count:1,source_title:"Источник",archived:false},definition:destination,external_dependencies:[{kind:"fact",key:"source_fact",label:"Вопрос"}]};
 vi.mocked(api.fetchScenarioFragments).mockResolvedValueOnce({items:[fragment.fragment],total:1});
 vi.spyOn(api,"fetchScenarioFragment").mockResolvedValueOnce(fragment);
 render(<ScenarioFragments definition={destination} detail={detail} dirty={false} disabled={false} position={{x:0,y:0}} onLocalInsert={vi.fn()} onInserted={vi.fn()} />);
 fireEvent.click(await screen.findByRole("button", {name:/Готовый/}));
 const insert = await screen.findByRole("button",{name:"Вставить фрагмент"});
 expect(insert).toBeDisabled();
 fireEvent.change(screen.getByLabelText(/Назначение ответа: Вопрос/),{target:{value:"new"}});
 expect(insert).toBeEnabled();
});
