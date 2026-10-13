import { useRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useWorkbenchGeometry } from "./scenario-workbench-geometry";
afterEach(()=>{localStorage.clear();vi.unstubAllGlobals();});
function Frame(){const ref=useRef<HTMLDivElement>(null);const layout=useWorkbenchGeometry(ref);return <div ref={ref} style={layout.style}>{layout.handle("left")}{layout.handle("right")}{layout.handle("height")}<button onClick={layout.reset}>Сбросить размеры</button></div>;}
it("resizes with the keyboard, restores browser preferences and resets without touching a draft",()=>{
 vi.stubGlobal("innerWidth",1366);
 const first=render(<Frame/>);
 fireEvent.keyDown(screen.getByRole("separator",{name:"Ширина каталога и блоков"}),{key:"ArrowRight"});
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","220");
 first.unmount();render(<Frame/>);
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","220");
 fireEvent.keyDown(screen.getByRole("separator",{name:"Ширина инспектора"}),{key:"Home"});
 expect(screen.getByRole("separator",{name:"Ширина инспектора"})).toHaveAttribute("aria-valuenow","280");
 fireEvent.click(screen.getByRole("button",{name:"Сбросить размеры"}));
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","200");
});
it("keeps room for manual connections when saved panels were wider on another screen",()=>{
 vi.stubGlobal("innerWidth",1280);
 localStorage.setItem("pc_client.studio.workbench.geometry.v1",JSON.stringify({left:480,right:640,height:null}));render(<Frame/>);
 const left=Number(screen.getByRole("separator",{name:"Ширина каталога и блоков"}).getAttribute("aria-valuenow")),right=Number(screen.getByRole("separator",{name:"Ширина инспектора"}).getAttribute("aria-valuenow"));
 expect(1280-left-right-16).toBeGreaterThanOrEqual(480);
});
