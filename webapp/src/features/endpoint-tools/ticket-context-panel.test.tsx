import {fireEvent,render,screen} from "@testing-library/react";
import {expect,it} from "vitest";
import {TicketContextPanel} from "./ticket-context-panel";
it("orders requester device agent before observer and keeps critical summary visible",()=>{
  const view=render(<TicketContextPanel requester={<p>Заявитель</p>} device={<p>Компьютер</p>} agent={<p>Агент</p>} observer={<button>Трасса</button>} criticalSummary={<p>Ошибок: 2</p>}/>);
  expect(Array.from(view.container.querySelectorAll("[data-context-layer]")).map(n=>n.getAttribute("data-context-layer"))).toEqual(["requester","device","agent","observer"]);
  expect(screen.getByText("Ошибок: 2")).toBeVisible();
  expect(screen.queryByRole("button",{name:"Трасса"})).not.toBeInTheDocument();
  const details=view.container.querySelector("details")!;details.open=true;fireEvent(details,new Event("toggle"));
  expect(screen.getByRole("button",{name:"Трасса"})).toBeVisible();
});
