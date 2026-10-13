import { fireEvent, render, screen } from "@testing-library/react";
import { expect,it,vi } from "vitest";
import { ScenarioPurpose } from "./scenario-purpose";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const catalog={services:[{code:"it",public_title:"ИТ",lifecycle_status:"published",visibility:"public"}],categories:[{id:"a",service_code:"it",title:"Первая"},{id:"b",service_code:"it",title:"Вторая"}],offerings:[],scenarios:[]} as unknown as ScenarioCatalog;
const definition:ScenarioDraftDefinition={schema_version:2,scenario_key:"s",title:"Услуга",service_code:"it",offering_full_code:"it.service",category_id:"a",process_binding:{request_template_key:"internal"},entry_points:[{key:"main",title:"Вход",target_block_id:"q",category_id:"a"},{key:"override",title:"Старый вход",target_block_id:"q",category_id:"old"}]};
it("inherits category changes without silently moving a historical entrance override",()=>{
 const change=vi.fn();render(<ScenarioPurpose definition={definition} catalog={catalog} disabled={false} existing onChange={change}/>);
 fireEvent.change(screen.getByLabelText("Категория (необязательно)"),{target:{value:"b"}});
 expect(change.mock.calls[0][0].entry_points.map((entry:{category_id:string})=>entry.category_id)).toEqual(["b","old"]);
 expect(change.mock.calls[0][0].title).toBe("Услуга");
});
it("shows service placement without internal template and initial-block selectors",()=>{
 render(<ScenarioPurpose definition={definition} catalog={catalog} disabled={false} existing onChange={vi.fn()}/>);
 expect(screen.getByLabelText("Раздел каталога")).toBeDisabled();
 expect(screen.queryByLabelText("Тип обращения")).not.toBeInTheDocument();
 expect(screen.queryByLabelText("Начальный блок")).not.toBeInTheDocument();
 expect(screen.queryByText(/internal/)).not.toBeInTheDocument();
});
