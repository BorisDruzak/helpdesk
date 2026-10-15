import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
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
  return <><ScenarioConditionEditor label="Test condition" fields={fields} resultValues={results} disabled={false} value={value} onChange={setValue} /><output data-testid="condition">{JSON.stringify(value)}</output></>;
}
const issueChoices = [{ value: "printer", label: "Принтер" }, { value: "network", label: "Сеть" }];
it.each(["radio", "select"] as const)("immediately exposes actual %s choices when adding a new condition", type => {
  render(<ConditionHarness fields={[{ key: "issue", type, label: "Что не работает?", options: issueChoices }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  expect(screen.getByLabelText("Правило")).toHaveValue("eq");
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("Принтер");
  fireEvent.change(screen.getByLabelText("Значение условия"), { target: { value: "network" } });
  expect(JSON.parse(screen.getByTestId("condition").textContent!)).toEqual({ source: "answer", field: "issue", op: "eq", value: "network" });
});
it("resets an explicitly changed question source to its own categorical choices", () => {
  render(<ConditionHarness fields={[{ key: "issue", type: "radio", label: "Проблема", options: issueChoices }, { key: "scope", type: "select", label: "Масштаб", options: [{ value: "department", label: "Весь отдел" }, { value: "single", label: "Один сотрудник" }] }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "scope" } });
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("Весь отдел");
  expect(screen.queryByRole("option", { name: "Принтер" })).not.toBeInTheDocument();
  expect(JSON.parse(screen.getByTestId("condition").textContent!)).toEqual({ source: "answer", field: "scope", op: "eq", value: "department" });
});
it("offers typed boolean values immediately when switching to a checkbox question", () => {
  render(<ConditionHarness fields={[{ key: "issue", type: "radio", label: "Проблема", options: issueChoices }, { key: "blocked", type: "checkbox", label: "Работа остановлена?" }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "blocked" } });
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("Да");
  fireEvent.change(screen.getByLabelText("Значение условия"), { target: { value: "false" } });
  expect(JSON.parse(screen.getByTestId("condition").textContent!)).toEqual({ source: "answer", field: "blocked", op: "eq", value: false });
});
it.each([false, true])("immediately offers membership for a multi-select source (switch=%s)", switchSource => {
  const field: ScenarioField = { key: "issues", type: "multi_select", label: "Проблемы", options: issueChoices };
  render(<ConditionHarness fields={switchSource ? [{ key: "details", type: "text", label: "Подробности" }, field] : [field]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  if (switchSource) fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "issues" } });
  expect(screen.getByLabelText("Правило")).toHaveValue("in");
  expect(screen.getByRole("checkbox", { name: "Принтер" })).toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "Сеть" }));
  expect(JSON.parse(screen.getByTestId("condition").textContent!)).toEqual({ source: "answer", field: "issues", op: "in", value: ["printer", "network"] });
});
it.each([false, true])("preserves saved explicit presence checks without changes on render (nested=%s)", nested => {
  const exists: ScenarioCondition = { source: "answer", field: "issue", op: "exists" };
  const value: ScenarioCondition = nested ? { op: "not", condition: exists } : exists;
  const onChange = vi.fn();
  render(<ScenarioConditionEditor label="Saved" value={value} fields={[{ key: "issue", type: "radio", label: "Проблема", options: issueChoices }]} disabled={false} onChange={onChange} />);
  expect(screen.getAllByLabelText("Правило").some(input => (input as HTMLSelectElement).value === "exists")).toBe(true);
  expect(screen.queryByLabelText("Значение условия")).not.toBeInTheDocument();
  expect(onChange).not.toHaveBeenCalled();
  expect(value).toEqual(nested ? { op: "not", condition: exists } : exists);
});
it("labels all diagnostic failures in equality and membership branches", () => {
  render(<ConditionHarness fields={[]} results={["unavailable", "denied", "timeout", "capability_absent"]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  const labels = ["Недоступно", "Согласие не получено", "Истёк срок ожидания", "Возможность проверки отсутствует"];
  for (const label of labels) expect(screen.getByRole("option", { name: label })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Правило"), { target: { value: "in" } });
  for (const label of labels) expect(screen.getByRole("checkbox", { name: label })).toBeInTheDocument();
});
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
it("builds nested ALL/ANY/NOT rules over three previous questions using visible labels", () => {
  render(<ConditionHarness fields={[{ key: "issue", type: "text", label: "Что не работает?" }, { key: "scale", type: "text", label: "Сколько сотрудников?" }, { key: "work", type: "text", label: "Можно продолжать работу?" }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
  fireEvent.click(screen.getByRole("button", { name: "Добавить группу И" }));
  fireEvent.click(screen.getByRole("button", { name: "Ещё условие" }));
  const sources = screen.getAllByLabelText("Источник");
  expect(sources).toHaveLength(3);
  fireEvent.change(sources[1], { target: { value: "scale" } });
  fireEvent.change(sources[2], { target: { value: "work" } });
  expect(sources.map(source => (source as HTMLSelectElement).value)).toEqual(["issue", "scale", "work"]);
  fireEvent.click(screen.getAllByRole("button", { name: "Добавить группу ИЛИ" })[1]);
  expect(screen.getAllByLabelText("Правило").some(select => (select as HTMLSelectElement).value === "or")).toBe(true);
  fireEvent.click(screen.getAllByRole("button", { name: "Добавить отрицание" })[1]);
  expect(screen.getAllByLabelText("Правило").some(select => (select as HTMLSelectElement).value === "not")).toBe(true);
});
