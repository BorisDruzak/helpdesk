import { fireEvent,render,screen } from "@testing-library/react";
import { expect,it,vi } from "vitest";
import { ScenarioRequesterPreview } from "./scenario-requester-preview";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const definition:ScenarioDraftDefinition={scenario_key:"s",title:"Карта",service_code:"it",offering_full_code:"it.p",process_binding:{request_template_key:"p"},blocks:[]};
it("uses requester controls with local answers and discloses conditional field projection",()=>{
 const fetcher=vi.spyOn(globalThis,"fetch");const block={id:"q",kind:"form_page" as const,title:"Запрос доступа",layout:"section" as const,fields:[{key:"name",type:"text" as const,label:"Куда нужен доступ?",group:"general",group_title:"Основное",visible_when:{op:"exists" as const,source:"answer" as const,field:"other"}}]};
 render(<ScenarioRequesterPreview definition={definition} block={block}/>);fireEvent.change(screen.getByLabelText("Куда нужен доступ?"),{target:{value:"Папка"}});expect(screen.getByLabelText("Куда нужен доступ?")).toHaveValue("Папка");expect(screen.getByText("Основное")).toBeVisible();expect(screen.getByText(/показаны все вопросы/)).toBeVisible();expect(screen.getByRole("button",{name:"Продолжить"})).toBeDisabled();expect(fetcher).not.toHaveBeenCalled();fetcher.mockRestore();
});
it("renders instruction text safely and does not run diagnostics",()=>{const {rerender}=render(<ScenarioRequesterPreview definition={definition} block={{id:"i",kind:"instruction",title:"Инструкция",content:{body:"<script>unsafe()</script>"}}}/>);expect(screen.getByText("<script>unsafe()</script>")).toBeVisible();expect(document.querySelector("script")).toBeNull();rerender(<ScenarioRequesterPreview definition={definition} block={{id:"d",kind:"diagnostic",title:"Проверка"}}/>);expect(screen.getByText(/диагностика не запускается/)).toBeVisible();});
