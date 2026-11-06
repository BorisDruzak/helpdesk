import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioNavigationEditor } from "./scenario-navigation-editor";
import type { ScenarioDraftDefinition } from "./scenario-contract";
it("edits only the navigation button while preserving the legacy guard and processing", () => {
  const block = { id: "n", kind: "navigation" as const, title: "Выбор", transition_mode: "buttons" as const, transitions: [{ to: "end", button: { key: "a", label: "Дальше" }, processing_facts: { urgency: "blocked" as const } }] };
  const definition = { schema_version: 4, scenario_key: "s", title: "S", blocks: [block, { id: "end", kind: "submit_ticket", title: "Обращение" }] } as ScenarioDraftDefinition;
  const change = vi.fn(); render(<ScenarioNavigationEditor block={block} definition={definition} disabled={false} onChange={change} />);
  fireEvent.change(screen.getByLabelText("Текст кнопки 1"), { target: { value: "Нужна помощь" } });
  expect(change.mock.calls[0][0].transitions[0]).toEqual({ ...block.transitions[0], button: { key: "a", label: "Нужна помощь" } });
  expect(screen.queryByText("Масштаб воздействия")).not.toBeInTheDocument();
});
it("offers explicit visual mode controls and names converted actions independently", () => {
  const block = { id: "q", kind: "review" as const, title: "Проверка", transitions: [{ to: "end" }, { to: "done" }] };
  const definition = { schema_version: 4, scenario_key: "s", title: "S", blocks: [block, { id: "end", kind: "submit_ticket", title: "Обращение" }, { id: "done", kind: "finish", title: "Решено" }] } as ScenarioDraftDefinition;
  const change = vi.fn(); render(<ScenarioNavigationEditor block={block} definition={definition} disabled={false} onChange={change} />);
  expect(screen.queryByRole("combobox", { name: "Способ перехода" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Сотрудник выбирает кнопку" }));
  expect(change.mock.lastCall?.[0].transitions.map((edge: { button: { label: string } }) => edge.button.label)).toEqual(["Обращение", "Решено"]);
});
it("never converts a legacy source even if the component is opened directly", () => {
  const block = { id: "q", kind: "review" as const, title: "Проверка", transitions: [{ to: "end" }] };
  const definition = { schema_version: 3, scenario_key: "s", title: "S", blocks: [block] } as ScenarioDraftDefinition;
  const change = vi.fn(); render(<ScenarioNavigationEditor block={block} definition={definition} disabled={false} onChange={change} />);
  expect(screen.queryByRole("button", { name: "Сотрудник выбирает кнопку" })).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});
