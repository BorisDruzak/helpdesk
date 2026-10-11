import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { ScenarioCondition, ScenarioField } from "./scenario-contract";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import { ScenarioSeparatedInput } from "./scenario-separated-input";

it("keeps newline/comma while ordinary incremental typing adds a second value", () => {
  function InputHarness() {
    const [values, setValues] = useState<string[]>([]);
    return <><ScenarioSeparatedInput label="Values" values={values} separator={"\n"} disabled={false} limit={100} onChange={setValues} /><output>{values.join("|")}</output></>;
  }
  render(<InputHarness />);
  const input = screen.getByLabelText("Values") as HTMLTextAreaElement;
  fireEvent.focus(input);
  for (const char of "yes\nno") fireEvent.change(input, { target: { value: input.value + char } });
  expect(input).toHaveValue("yes\nno"); expect(screen.getByText("yes|no")).toBeInTheDocument();
});
it("keeps alias separators instead of concatenating aliases", () => {
  function AliasHarness() {
    const [values, setValues] = useState<string[]>([]);
    return <><ScenarioSeparatedInput label="Aliases" values={values} separator="," disabled={false} limit={8} onChange={setValues} /><output>{values.join("|")}</output></>;
  }
  render(<AliasHarness />);
  const input = screen.getByLabelText("Aliases") as HTMLTextAreaElement;
  fireEvent.focus(input);
  for (const char of "old,new") fireEvent.change(input, { target: { value: input.value + char } });
  expect(input).toHaveValue("old,new"); expect(screen.getByText("old|new")).toBeInTheDocument();
});
function ConditionHarness({ fields, results = [] }: { fields: ScenarioField[]; results?: string[] }) {
  const [value, setValue] = useState<ScenarioCondition | null>(null);
  return <ScenarioConditionEditor label="Test condition" fields={fields} resultValues={results} disabled={false} value={value} onChange={setValue} />;
}
it("offers numeric ordering only for numbers and no result source on a form", () => {
  render(<ConditionHarness fields={[{ key: "a", type: "text", label: "A" }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  expect(screen.getByRole("option", { name: "Больше" })).toBeDisabled();
  expect(screen.queryByRole("option", { name: "Результат текущего блока" })).not.toBeInTheDocument();
});
it("allows membership rather than scalar comparisons for a multiple choice", () => {
  render(<ConditionHarness fields={[{ key: "a", type: "multi_select", label: "A", options: [{ value: "a", label: "A" }] }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  expect(screen.getByRole("option", { name: "Равно" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "Один из" })).toBeEnabled();
});
it("offers only the exact block result domain", () => {
  render(<ConditionHarness fields={[]} results={["unavailable"]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  expect(screen.getByLabelText("Значение условия")).toHaveValue("unavailable");
  expect(screen.queryByRole("option", { name: "Да" })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Недоступно" })).toBeEnabled();
});
it("keeps boolean option values typed even after a saved field has empty options", () => {
  render(<ConditionHarness fields={[{ key: "a", type: "checkbox", label: "A", options: [] }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  fireEvent.change(screen.getByLabelText("Правило"), { target: { value: "eq" } });
  expect(screen.getByLabelText("Значение условия")).toHaveValue("true");
  expect(screen.getByRole("option", { name: "Да" })).toBeEnabled();
  expect(screen.getByRole("option", { name: "Нет" })).toBeEnabled();
});
it("keeps invalid numeric membership explicit instead of serializing infinity as null", () => {
  render(<ConditionHarness fields={[{ key: "a", type: "number", label: "A" }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  fireEvent.change(screen.getByLabelText("Правило"), { target: { value: "in" } });
  const input = screen.getByLabelText("Список значений");
  fireEvent.focus(input); fireEvent.change(input, { target: { value: "1e999" } }); fireEvent.blur(input);
  expect(input).toHaveValue("1e999");
  expect(screen.getByRole("alert")).toHaveTextContent("Введите конечные числа");
});
