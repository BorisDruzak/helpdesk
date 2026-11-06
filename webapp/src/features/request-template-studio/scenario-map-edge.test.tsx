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
