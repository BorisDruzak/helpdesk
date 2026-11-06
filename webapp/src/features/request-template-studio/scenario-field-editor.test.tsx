import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioFieldEditor } from "./scenario-field-editor";
import type { ScenarioDraftDefinition, ScenarioField } from "./scenario-contract";

const field: ScenarioField = { key: "q", label: "Описание", type: "text" };
const definition = { schema_version: 4, scenario_key: "test", blocks: [{ id: "page", kind: "form_page", fields: [field] }] } as ScenarioDraftDefinition;
it("clearly identifies the answer placeholder as an employee control rather than author data",()=>{
 const change=vi.fn();render(<ScenarioFieldEditor field={field} definition={definition} disabled={false} onChange={change}/>);
 expect(screen.getByText("Так выглядит поле ответа сотрудника")).toBeVisible();
 expect(screen.getByRole("textbox",{name:"Описание"})).toBeDisabled();
 expect(change).not.toHaveBeenCalled();
});
it("explains employee-facing help and shows an empty placeholder without changing the document", () => {
  const change = vi.fn();
  render(<ScenarioFieldEditor field={field} definition={definition} disabled={false} onChange={change} />);
  expect(screen.getByText("Подсказка сотруднику (необязательно)")).toBeVisible();
  expect(screen.getByText("Сотрудник увидит этот текст под вопросом. Добавьте пояснение, пример или инструкцию.")).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Подсказка к вопросу" })).toHaveAttribute("data-placeholder", "Например: где найти имя компьютера или как описать проблему…");
  expect(screen.getByRole("textbox", { name: "Подсказка к вопросу" })).toHaveAttribute("aria-placeholder", "Например: где найти имя компьютера или как описать проблему…");
  expect(change).not.toHaveBeenCalled();
});
it("keeps legacy plain help serialization unchanged", () => {
  const change = vi.fn();
  render(<ScenarioFieldEditor field={{ ...field, help_text: "Было" }} definition={{ ...definition, schema_version: 3 }} disabled={false} onChange={change} />);
  fireEvent.change(screen.getByDisplayValue("Было"), { target: { value: "Новое пояснение" } });
  expect(change).toHaveBeenCalledWith({ ...field, help_text: "Новое пояснение" });
  expect(change.mock.lastCall?.[0]).not.toHaveProperty("help_document");
});
it("serializes edited rich help and the plain fallback without placeholder attributes", async () => {
  const change = vi.fn();
  render(<ScenarioFieldEditor field={field} definition={definition} disabled={false} onChange={change} />);
  const editor = screen.getByRole("textbox", { name: "Подсказка к вопросу" });
  editor.innerHTML = "<p>Пояснение сотруднику</p>";
  fireEvent.input(editor, { inputType: "insertText", data: "Пояснение сотруднику" });
  await waitFor(() => expect(change).toHaveBeenCalled());
  expect(change.mock.lastCall?.[0]).toEqual({ ...field, help_text: "Пояснение сотруднику", help_document: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Пояснение сотруднику" }] }] } });
  expect(editor).toHaveAttribute("data-empty", "false");
});
