import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioDocumentPanel } from "./scenario-document-panel";
import type { ScenarioDetail } from "./scenario-api";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("shows safe structural error paths without replacing the draft", async () => {
 const definition = {schema_version:3 as const,scenario_key:"test",service_code:"it",offering_full_code:"it.test",title:"Test",process_binding:{request_template_key:"test"}};
 const detail = {scenario:{id:"test"},draft:{revision:1,definition}} as ScenarioDetail;
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({status:"error",error_code:"SCENARIO_INVALID",issues:[{code:"literal_error",path:"blocks.0.fields.0.type",message:"Unsupported"}]}),{status:400,headers:{"content-type":"application/json"}})));
 const onChange=vi.fn();
 render(<ScenarioDocumentPanel definition={definition} detail={detail} dirty={false} disabled={false} onChange={onChange}/>);
 fireEvent.click(screen.getByText("Импорт и экспорт JSON / YAML"));
 fireEvent.change(screen.getByLabelText("Документ карты"),{target:{value:'{"schema_version":3}'}});
 fireEvent.click(screen.getByRole("button",{name:"Проверить импорт"}));
 expect(await screen.findByText(/blocks\.0\.fields\.0\.type/)).toBeVisible();
 expect(onChange).not.toHaveBeenCalled();
});
