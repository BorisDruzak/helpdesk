import { fireEvent,render,screen } from "@testing-library/react";
import { expect,it,vi } from "vitest";
import { ScenarioMapLinkCard } from "./scenario-map-link-card";
vi.mock("@xyflow/react",()=>({Position:{Left:"left",Right:"right"},Handle:({id,isConnectable}:{id:string;isConnectable?:boolean})=><span data-testid={`port-${id}`} data-connectable={String(isConnectable??true)}/>}));
it("edits an action label directly and exposes ordinary selectable card actions",()=>{
 const rename=vi.fn(),select=vi.fn();render(<ScenarioMapLinkCard link={{edgeId:"q:0",positionKey:"a",title:"Вариант 1",context:"Вопрос → Ответ",targetTitle:"Ответ",disabled:false,rename,select}} preferenceKey="test"/>);
 const field=screen.getByRole("textbox",{name:"Текст кнопки «Вариант 1»"});fireEvent.change(field,{target:{value:"Проверить приложение"}});fireEvent.blur(field);expect(rename).toHaveBeenCalledWith("Проверить приложение");
 fireEvent.click(screen.getByRole("button",{name:"Редактировать переход"}));expect(select).toHaveBeenCalledOnce();
 expect(screen.getByTestId("port-in")).toHaveAttribute("data-connectable","false");expect(screen.getByTestId("port-out")).toHaveAttribute("data-connectable","true");
});
it("uses the shared editor inside the card and preserves keyboard resizing",()=>{
 render(<ScenarioMapLinkCard link={{edgeId:"q:0",positionKey:"a",title:"Продолжить",context:"Вопрос → Ответ",targetTitle:"Ответ",disabled:false,select:vi.fn()}} editor={<input aria-label="Условие"/>} preferenceKey="card-editor"/>);
 const input=screen.getByRole("textbox",{name:"Условие"}),root=input.closest(".studio-resizable-editor") as HTMLElement;
 expect(input.closest("[data-scenario-edge]")).toHaveAttribute("data-scenario-edge","q:0");const before=parseFloat(root.style.width);fireEvent.keyDown(screen.getByRole("button",{name:"Размер редактора перехода"}),{key:"ArrowRight"});expect(parseFloat(root.style.width)).toBe(before+20);
});
