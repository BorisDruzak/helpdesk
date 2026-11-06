import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ScenarioResizableEditor } from "./scenario-editor-size";
beforeEach(() => localStorage.clear());
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
