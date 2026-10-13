import { useRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { useWorkbenchGeometry } from "./scenario-workbench-geometry";
afterEach(()=>localStorage.clear());
function Frame(){const ref=useRef<HTMLDivElement>(null);const layout=useWorkbenchGeometry(ref);return <div ref={ref} style={layout.style}>{layout.handle("left")}{layout.handle("right")}{layout.handle("height")}<button onClick={layout.reset}>Сбросить размеры</button></div>;}
it("resizes with the keyboard, restores browser preferences and resets without touching a draft",()=>{
 const first=render(<Frame/>);
 fireEvent.keyDown(screen.getByRole("separator",{name:"Ширина каталога и блоков"}),{key:"ArrowRight"});
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","260");
 first.unmount();render(<Frame/>);
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","260");
 fireEvent.keyDown(screen.getByRole("separator",{name:"Ширина инспектора"}),{key:"Home"});
 expect(screen.getByRole("separator",{name:"Ширина инспектора"})).toHaveAttribute("aria-valuenow","280");
 fireEvent.click(screen.getByRole("button",{name:"Сбросить размеры"}));
 expect(screen.getByRole("separator",{name:"Ширина каталога и блоков"})).toHaveAttribute("aria-valuenow","240");
});
