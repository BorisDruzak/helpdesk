import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioMapEdge } from "./scenario-map-edge";
vi.mock("@xyflow/react", () => ({ BaseEdge: () => null, EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) => children, getSmoothStepPath: () => ["", 10, 20] }));
it("separates editing a transition button from adding another block", () => {
  const select = vi.fn(), add = vi.fn();
  render(<ScenarioMapEdge {...({ id: "q:0", label: "Нужна помощь", data: { select, add, addLabel: "Добавить шаг" } } as unknown as Parameters<typeof ScenarioMapEdge>[0])} />);
  fireEvent.click(screen.getByRole("button", { name: "Нужна помощь" })); expect(select).toHaveBeenCalledOnce(); expect(add).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Добавить шаг" })); expect(add).toHaveBeenCalledOnce(); expect(select).toHaveBeenCalledOnce();
});
it("renames one employee button from its connection without selecting or adding", () => {
  const rename = vi.fn(), select = vi.fn();
  render(<ScenarioMapEdge {...({ id: "q:1", label: "Решено", data: { rename, button: true, select } } as unknown as Parameters<typeof ScenarioMapEdge>[0])} />);
  const input = screen.getByRole("textbox", { name: "Текст кнопки «Решено»" });
  fireEvent.change(input, { target: { value: "Всё работает" } });
  fireEvent.keyDown(input, { key: "Enter" });
  fireEvent.blur(input);
  expect(rename).toHaveBeenCalledWith("Всё работает"); expect(select).not.toHaveBeenCalled();
});
it("opens transition settings explicitly and on label double click while preserving inline rename", () => {
  const select = vi.fn();
  const view = render(<ScenarioMapEdge {...({ id: "q:2", label: "Дальше", data: { rename: vi.fn(), button: true, select } } as unknown as Parameters<typeof ScenarioMapEdge>[0])} />);
  fireEvent.click(screen.getByRole("button", { name: "Редактировать переход" }));
  expect(select).toHaveBeenCalledOnce();
  fireEvent.doubleClick(view.container.querySelector("[data-scenario-edge]")!);
  expect(select).toHaveBeenCalledTimes(2);
  fireEvent.doubleClick(screen.getByRole("textbox"));
  expect(select).toHaveBeenCalledTimes(2);
});
it("renders selected transition settings at the same map label and keeps movement in local preferences", () => {
  localStorage.clear();
  const move = vi.fn();
  render(<ScenarioMapEdge {...({ id: "q:3", label: "Помощь", data: { labelOffset: 5, editor: <p>Настройки перехода</p>, preferenceKey: "scenario:edge:q:3", getZoom: () => 0.5, onEditorOffsetChange: move } } as unknown as Parameters<typeof ScenarioMapEdge>[0])} />);
  const blank = screen.getByText("Настройки перехода");
  const label = blank.closest("[data-scenario-edge]") as HTMLElement;
  expect(label.style.transform).toContain("translate(10px, 25px)");
  expect(blank.closest(".studio-resizable-editor")).not.toBeNull();
  fireEvent.pointerDown(blank, { button: 0, pointerId: 4, clientX: 10, clientY: 20 });
  fireEvent.pointerMove(blank, { pointerId: 4, clientX: 30, clientY: 30 });
  fireEvent.pointerUp(blank, { pointerId: 4 });
  expect(move).toHaveBeenLastCalledWith({ x: 40, y: 20 });
  expect(JSON.parse(localStorage.getItem("studio-editor-offset:v1:scenario:edge:q:3")!)).toEqual({ x: 40, y: 20 });
});
