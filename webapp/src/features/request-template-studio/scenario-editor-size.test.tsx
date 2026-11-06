import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ScenarioResizableEditor } from "./scenario-editor-size";
beforeEach(() => localStorage.clear());
it("keeps edge and corner hit areas usable in screen pixels at map zoom",()=>{
 render(<ScenarioResizableEditor preferenceKey="hit-zones" label="Размер" getZoom={()=>.25}><span>Редактор</span></ScenarioResizableEditor>);
 const editor=screen.getByText("Редактор").closest(".studio-resizable-editor") as HTMLElement;
 expect(parseFloat(editor.style.getPropertyValue("--studio-resize-hit"))*.25).toBe(20);
 expect(parseFloat(editor.style.getPropertyValue("--studio-resize-corner"))*.25).toBe(28);
 expect(screen.getAllByRole("button").filter(button=>button.hasAttribute("data-resize-direction"))).toHaveLength(8);
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mockWindowEditorGeometry(context: "full" | "popover") {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const element = this;
    if (element.classList.contains("studio-map-main")) return { left: 100, top: 50, right: window.innerWidth - 20, bottom: window.innerHeight - 20, width: window.innerWidth - 120, height: window.innerHeight - 70 } as DOMRect;
    const width = parseFloat(element.style.width) || 0, height = parseFloat(element.style.height) || 0;
    const translate = element.style.transform.match(/translate\((-?[\d.]+)px, (-?[\d.]+)px\)/);
    const x = Number(translate?.[1] ?? 0), y = Number(translate?.[2] ?? 0);
    const left = (context === "full" ? (window.innerWidth - width) / 2 : window.innerWidth - 32 - width) + x;
    const top = (context === "full" ? (window.innerHeight - height) / 2 : 62) + y;
    return { left, top, right: left + width, bottom: top + height, width, height } as DOMRect;
  });
}
it("persists keyboard sizing per scenario/node/context without business callbacks", () => {
  const props = { preferenceKey: "s:q:inline", label: "Размер редактора", children: <input aria-label="Вопрос" /> };
  const view = render(<ScenarioResizableEditor {...props} />);
  const panel = screen.getByLabelText("Вопрос").closest(".studio-resizable-editor")! as HTMLElement;
  const width = parseFloat(panel.style.width);
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер редактора" }), { key: "ArrowRight" });
  expect(parseFloat(panel.style.width)).toBe(width + 20);
  view.unmount(); render(<ScenarioResizableEditor {...props} />);
  expect((screen.getByLabelText("Вопрос").closest(".studio-resizable-editor") as HTMLElement).style.width).toBe(`${width + 20}px`);
});
it("accounts for canvas zoom during pointer resize and stops canvas gestures", () => {
  render(<ScenarioResizableEditor preferenceKey="zoom" label="Размер редактора" getZoom={() => 0.5}><span>Содержимое</span></ScenarioResizableEditor>);
  const handle = screen.getByRole("button", { name: "Размер редактора" });
  const panel = handle.closest(".studio-resizable-editor") as HTMLElement;
  const width = parseFloat(panel.style.width);
  fireEvent.pointerDown(handle, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 120, clientY: 110 });
  fireEvent.pointerUp(handle, { pointerId: 1 });
  expect(parseFloat(panel.style.width)).toBe(width + 40);
});
it("clamps oversized saved preferences to the viewport and keeps contexts separate", () => {
  localStorage.setItem("studio-editor-size:v1:s:q:inline", JSON.stringify({ width: 9000, height: 9000 }));
  const view = render(<ScenarioResizableEditor preferenceKey="s:q:inline" label="Размер" context="inline"><input aria-label="Содержимое" /></ScenarioResizableEditor>);
  const panel = screen.getByLabelText("Содержимое").closest(".studio-resizable-editor") as HTMLElement;
  expect(parseFloat(panel.style.width)).toBeLessThan(window.innerWidth);
  expect(parseFloat(panel.style.height)).toBeLessThan(window.innerHeight);
  view.unmount();
  render(<ScenarioResizableEditor preferenceKey="s:q:popover" label="Размер" context="popover"><span>Связь</span></ScenarioResizableEditor>);
  expect((screen.getByText("Связь").closest(".studio-resizable-editor") as HTMLElement).style.width).toBe("460px");
});
it("reclamps when canvas zoom changes after opening", () => {
  const view = render(<ScenarioResizableEditor preferenceKey="zoom-change" label="Размер" getZoom={() => 0.5}><span>Вопрос</span></ScenarioResizableEditor>);
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер" }), { key: "ArrowRight", shiftKey: true });
  view.rerender(<ScenarioResizableEditor preferenceKey="zoom-change" label="Размер" getZoom={() => 2}><span>Вопрос</span></ScenarioResizableEditor>);
  const panel = screen.getByText("Вопрос").closest(".studio-resizable-editor") as HTMLElement;
  expect(parseFloat(panel.style.width) * 2).toBeLessThan(window.innerWidth);
});
it("keeps a usable inline minimum and restores preferred size after a small canvas zooms back", () => {
  const fit = vi.fn();
  const surface = (zoom: number, height = 500) => <div className="studio-map-canvas" ref={element => { if (element) element.getBoundingClientRect = () => ({ width: 900, height } as DOMRect); }}><ScenarioResizableEditor preferenceKey="small" label="Размер" getZoom={() => zoom} onMinimumFit={fit}><span>Вопросы</span></ScenarioResizableEditor></div>;
  const view = render(surface(1));
  const panel = screen.getByText("Вопросы").closest(".studio-resizable-editor") as HTMLElement;
  expect(panel.style.height).toBe("340px");
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер" }), { key: "ArrowDown" });
  expect(panel.style.height).toBe("360px");
  view.rerender(surface(2, 280));
  expect(parseFloat(panel.style.height)).toBeGreaterThanOrEqual(160);
  expect(fit).toHaveBeenCalled();
  expect(JSON.parse(localStorage.getItem("studio-editor-size:v1:small")!).height).toBe(360);
  view.rerender(surface(1));
  expect(panel.style.height).toBe("360px");
});
it("offers all eight border handles without a visible dimensions bar", () => {
  const view = render(<ScenarioResizableEditor preferenceKey="borders" label="Размер"><span>Содержимое</span></ScenarioResizableEditor>);
  expect(view.container.querySelectorAll("[data-resize-direction]")).toHaveLength(8);
  expect(view.container).not.toHaveTextContent("460 × 340");
  expect(screen.getByRole("button", { name: "Размер: левая граница" })).toBeInTheDocument();
});
it("moves an edge card by blank space with zoom-correct local preferences and ignores controls", () => {
  const move = vi.fn();
  const view = render(<ScenarioResizableEditor preferenceKey="move" label="Размер" dragMode="offset" getZoom={() => 0.5} onOffsetChange={move}><p>Пустое место</p><label>Подпись<input /></label><button>Обычная кнопка</button><div contentEditable suppressContentEditableWarning>Текст</div></ScenarioResizableEditor>);
  const blank = screen.getByText("Пустое место");
  fireEvent.pointerDown(blank, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(blank, { pointerId: 1, clientX: 125, clientY: 110 });
  fireEvent.pointerUp(blank, { pointerId: 1 });
  expect(move).toHaveBeenLastCalledWith({ x: 50, y: 20 });
  const panel = blank.closest(".studio-resizable-editor") as HTMLElement;
  expect(panel.style.transform).toBe("translate(50px, 20px)");
  for (const control of [screen.getByRole("textbox"), screen.getByText("Подпись"), screen.getByRole("button", { name: "Обычная кнопка" }), screen.getByText("Текст")]) {
    fireEvent.pointerDown(control, { button: 0, pointerId: 2, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(control, { pointerId: 2, clientX: 200, clientY: 200 });
    fireEvent.pointerUp(control, { pointerId: 2 });
  }
  expect(move).toHaveBeenCalledTimes(1);
  view.unmount();
  render(<ScenarioResizableEditor preferenceKey="move" label="Размер" dragMode="offset"><p>Снова</p></ScenarioResizableEditor>);
  expect((screen.getByText("Снова").closest(".studio-resizable-editor") as HTMLElement).style.transform).toBe("translate(50px, 20px)");
});
it("leaves inline blank-space dragging to the native node and protects controls", () => {
  const nodeDrag = vi.fn();
  render(<div onMouseDown={nodeDrag}><ScenarioResizableEditor preferenceKey="node" label="Размер"><p>Фон</p><label>Вопрос<input /></label></ScenarioResizableEditor></div>);
  const blank = screen.getByText("Фон");
  expect(blank.closest(".nodrag")).toBeNull();
  fireEvent.mouseDown(blank, { button: 0 });
  expect(nodeDrag).toHaveBeenCalledOnce();
  fireEvent.mouseDown(screen.getByRole("textbox"), { button: 0 });
  fireEvent.mouseDown(screen.getByText("Вопрос"), { button: 0 });
  expect(nodeDrag).toHaveBeenCalledOnce();
});
it("resizes from the north-west while keeping the opposite corner in place", () => {
  render(<ScenarioResizableEditor preferenceKey="northwest" label="Размер" dragMode="offset" getZoom={() => 0.5}><span>Карточка</span></ScenarioResizableEditor>);
  const handle = screen.getByRole("button", { name: "Размер: верхний левый угол" });
  const panel = handle.closest(".studio-resizable-editor") as HTMLElement;
  fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 90, clientY: 95 });
  fireEvent.pointerUp(handle, { pointerId: 1 });
  expect(panel.style.width).toBe("480px"); expect(panel.style.height).toBe("350px");
  expect(panel.style.transform).toBe("translate(-20px, -10px)");
});
it.each([
  ["верхняя граница", 460, 320], ["верхний правый угол", 480, 320], ["правая граница", 480, 340],
  ["нижняя граница", 460, 360], ["нижний левый угол", 440, 360], ["левая граница", 440, 340], ["верхний левый угол", 440, 320],
] as const)("resizes from %s using the matching edge axes", (name, width, height) => {
  render(<ScenarioResizableEditor preferenceKey="axes" label="Размер"><span>Карточка</span></ScenarioResizableEditor>);
  const handle = screen.getByRole("button", { name: `Размер: ${name}` });
  const panel = handle.closest(".studio-resizable-editor") as HTMLElement;
  fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 120, clientY: 120 });
  fireEvent.pointerUp(handle, { pointerId: 1 });
  expect(panel.style.width).toBe(`${width}px`); expect(panel.style.height).toBe(`${height}px`);
});
it("reloads size and position preferences when switching editors without a remount", () => {
  const view = render(<ScenarioResizableEditor preferenceKey="first" label="Размер" dragMode="offset"><span>Карточка</span></ScenarioResizableEditor>);
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер" }), { key: "ArrowRight" });
  const blank = screen.getByText("Карточка");
  fireEvent.pointerDown(blank, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(blank, { pointerId: 1, clientX: 120, clientY: 110 }); fireEvent.pointerUp(blank, { pointerId: 1 });
  view.rerender(<ScenarioResizableEditor preferenceKey="second" label="Размер" dragMode="offset"><span>Карточка</span></ScenarioResizableEditor>);
  const panel = blank.closest(".studio-resizable-editor") as HTMLElement;
  expect(panel.style.width).toBe("460px"); expect(panel.style.transform).toBe("translate(0px, 0px)");
  view.rerender(<ScenarioResizableEditor preferenceKey="first" label="Размер" dragMode="offset"><span>Карточка</span></ScenarioResizableEditor>);
  expect(panel.style.width).toBe("480px"); expect(panel.style.transform).toBe("translate(20px, 10px)");
});
it("reports total clamped origin deltas while resizing a node and commits once at release", () => {
  const origin = vi.fn();
  render(<ScenarioResizableEditor preferenceKey="origin" label="Размер" onOriginChange={origin} getZoom={() => 0.5}><span>Узел</span></ScenarioResizableEditor>);
  const handle = screen.getByRole("button", { name: "Размер: верхний левый угол" });
  fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 90, clientY: 95 });
  expect(origin).toHaveBeenLastCalledWith({ x: -20, y: -10 }, false);
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 85, clientY: 90 });
  expect(origin).toHaveBeenLastCalledWith({ x: -30, y: -20 }, false);
  fireEvent.pointerUp(handle, { pointerId: 1 });
  expect(origin).toHaveBeenLastCalledWith({ x: -30, y: -20 }, true);
  expect(origin.mock.calls.filter(call => call[1])).toHaveLength(1);
  // Dragging well past the minimum reports actual shrinkage, not raw pointer movement.
  fireEvent.pointerDown(handle, { button: 0, pointerId: 2, clientX: 0, clientY: 0 });
  fireEvent.pointerMove(handle, { pointerId: 2, clientX: 1000, clientY: 1000 });
  expect(origin).toHaveBeenLastCalledWith({ x: 210, y: 200 }, false);
  fireEvent.pointerUp(handle, { pointerId: 2 });
});
it("commits keyboard north-west node origin changes immediately", () => {
  const origin = vi.fn();
  render(<ScenarioResizableEditor preferenceKey="keyboard-origin" label="Размер" onOriginChange={origin}><span>Узел</span></ScenarioResizableEditor>);
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер: верхний левый угол" }), { key: "ArrowLeft" });
  expect(origin).toHaveBeenCalledExactlyOnceWith({ x: -20, y: 0 }, true);
});
it.each(["full", "popover"] as const)("bounds restored %s offsets at mount and after viewport resize", context => {
  mockWindowEditorGeometry(context);
  localStorage.setItem("studio-editor-offset:v1:restore", JSON.stringify({ x: 5000, y: 5000 }));
  const view = render(<div className="studio-map-main"><ScenarioResizableEditor preferenceKey="restore" label="Размер" context={context}><span>Окно</span></ScenarioResizableEditor></div>);
  const editor = screen.getByText("Окно").closest(".studio-resizable-editor") as HTMLElement;
  const check = () => {
    const rect = editor.getBoundingClientRect();
    expect(rect.right).toBeLessThanOrEqual(window.innerWidth - (context === "full" ? 8 : 28));
    expect(rect.bottom).toBeLessThanOrEqual(window.innerHeight - (context === "full" ? 8 : 28));
    expect(rect.left).toBeGreaterThanOrEqual(context === "full" ? 8 : 108);
    expect(rect.top).toBeGreaterThanOrEqual(context === "full" ? 8 : 58);
  };
  check();
  vi.stubGlobal("innerWidth", 600); vi.stubGlobal("innerHeight", 460); fireEvent(window, new Event("resize"));
  check();
  view.unmount();
});
it.each(["full", "popover"] as const)("keeps a right-aligned %s card in bounds when its east/south borders grow", context => {
  mockWindowEditorGeometry(context);
  localStorage.setItem("studio-editor-size:v1:grow", JSON.stringify({ width: 300, height: 180 }));
  localStorage.setItem("studio-editor-offset:v1:grow", JSON.stringify({ x: 5000, y: 5000 }));
  render(<div className="studio-map-main"><ScenarioResizableEditor preferenceKey="grow" label="Размер" context={context}><span>Окно</span></ScenarioResizableEditor></div>);
  const editor = screen.getByText("Окно").closest(".studio-resizable-editor") as HTMLElement;
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер" }), { key: "ArrowRight", shiftKey: true });
  fireEvent.keyDown(screen.getByRole("button", { name: "Размер" }), { key: "ArrowDown", shiftKey: true });
  expect(editor.style.width).toBe("360px"); expect(editor.style.height).toBe("240px");
  const rect = editor.getBoundingClientRect();
  expect(rect.right).toBeLessThanOrEqual(window.innerWidth - (context === "full" ? 8 : 28));
  expect(rect.bottom).toBeLessThanOrEqual(window.innerHeight - (context === "full" ? 8 : 28));
});
it("keeps a saved inline edge offset inside its zoomed map surface without moving a native node", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this.classList.contains("studio-map-canvas")) return { left: 100, top: 50, right: 900, bottom: 550, width: 800, height: 500 } as DOMRect;
    const translate = this.style.transform.match(/translate\((-?[\d.]+)px, (-?[\d.]+)px\)/);
    const width = parseFloat(this.style.width) * 0.5, height = parseFloat(this.style.height) * 0.5;
    const left = 750 + Number(translate?.[1] ?? 0) * 0.5, top = 20 + Number(translate?.[2] ?? 0) * 0.5;
    return { left, top, right: left + width, bottom: top + height, width, height } as DOMRect;
  });
  localStorage.setItem("studio-editor-offset:v1:edge-bounds", JSON.stringify({ x: 5000, y: -5000 }));
  const view = render(<div className="studio-map-canvas"><ScenarioResizableEditor preferenceKey="edge-bounds" label="Размер" dragMode="offset" getZoom={() => 0.5}><span>Переход</span></ScenarioResizableEditor></div>);
  const editor = screen.getByText("Переход").closest(".studio-resizable-editor") as HTMLElement;
  const rect = editor.getBoundingClientRect();
  expect(rect.left).toBeGreaterThanOrEqual(108); expect(rect.top).toBeGreaterThanOrEqual(58);
  expect(rect.right).toBeLessThanOrEqual(892); expect(rect.bottom).toBeLessThanOrEqual(542);
  expect(JSON.parse(localStorage.getItem("studio-editor-offset:v1:edge-bounds")!)).toEqual({ x: 5000, y: -5000 });
  view.rerender(<div className="studio-map-canvas"><ScenarioResizableEditor preferenceKey="edge-bounds" label="Размер" dragMode="node" getZoom={() => 0.5}><span>Узел</span></ScenarioResizableEditor></div>);
  expect((screen.getByText("Узел").closest(".studio-resizable-editor") as HTMLElement).style.transform).toBe("");
});
