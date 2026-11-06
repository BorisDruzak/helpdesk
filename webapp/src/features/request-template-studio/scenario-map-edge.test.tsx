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
