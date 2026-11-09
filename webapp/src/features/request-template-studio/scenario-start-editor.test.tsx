import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioStartEditor } from "./scenario-start-editor";
import type { ScenarioDraftDefinition } from "./scenario-contract";

it("groups start settings and opens an existing entry without changing the draft", () => {
  const change = vi.fn(), entry = vi.fn(), processing = vi.fn();
  const definition = { scenario_key: "s", title: "Чат", service_code: "s", process_binding: { request_template_key: "t" }, blocks: [{ id: "q", title: "Вопрос", kind: "review" }], entry_points: [{ key: "entry", title: "Не работает чат", target_block_id: "q" }] } as ScenarioDraftDefinition;
  render(<ScenarioStartEditor definition={definition} catalog={{ services: [], categories: [], offerings: [] } as never} disabled={false} existing section="entries" onSection={vi.fn()} onChange={change} onEntry={entry} onConnect={vi.fn()} onProcessing={processing} />);
  expect(screen.getByText("Услуга и описание", { selector: "summary" })).toBeVisible();
  expect(screen.getByText("Раздел и категория", { selector: "summary" })).toBeVisible();
  expect(screen.getByText("Входы в каталог", { selector: "summary" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Настроить вход Не работает чат" }));
  expect(entry).toHaveBeenCalledWith("entry", "q");
  fireEvent.click(screen.getByRole("button", { name: "Правила обработки" }));
  expect(processing).toHaveBeenCalled();
  expect(change).not.toHaveBeenCalled();
});
it("separates catalog availability from ticket visibility and opens focused rules",()=>{
 const processing=vi.fn();
 const definition={scenario_key:"s",title:"Карта",service_code:"s",process_binding:{request_template_key:"t"}} as ScenarioDraftDefinition;
 render(<ScenarioStartEditor definition={definition} catalog={{services:[],categories:[],offerings:[]} as never} disabled={false} existing section="service" onSection={vi.fn()} onChange={vi.fn()} onEntry={vi.fn()} onConnect={vi.fn()} onProcessing={processing} catalogVisibility={<button>Скрыть услугу</button>}/>);
 expect(screen.getByRole("region",{name:"Видимость услуги в каталоге"})).toHaveTextContent("Скрыть услугу");
 fireEvent.click(screen.getByRole("button",{name:"Видимость обращения"}));
 expect(processing).toHaveBeenLastCalledWith(["visibility"]);
 fireEvent.click(screen.getByRole("button",{name:"Правила обработки"}));
 expect(processing).toHaveBeenLastCalledWith(["priority","ola","approval","notification","closure"]);
});
