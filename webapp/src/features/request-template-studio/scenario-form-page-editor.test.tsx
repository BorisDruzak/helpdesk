import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioFormPageEditor } from "./scenario-form-page-editor";

type Page = Extract<ScenarioBlock, { kind: "form_page" }>;
const page: Page = { id: "q", kind: "form_page", title: "Вопросы", layout: "group", fields: [
  { key: "a", type: "text", label: "Компьютер", help_text: "Имя устройства" },
  { key: "b", type: "select", label: "Отдел", options: [{ value: "it", label: "ИТ" }] },
] };
function Harness({ initial = page, schema = 3, onChange = () => {} }: { initial?: Page; schema?: number; onChange?: (next: Page) => void }) {
  const [block, setBlock] = useState(initial);
  const definition = { schema_version: schema, scenario_key: "s", title: "S", blocks: [block] } as ScenarioDraftDefinition;
  return <ScenarioFormPageEditor block={block} definition={definition} disabled={false} onChange={next => { setBlock(next); onChange(next); }} />;
}
it("edits every question and option immediately without selecting a question", () => {
  const change = vi.fn(); render(<Harness onChange={change} />);
  expect(screen.getAllByLabelText("Что спросить?").map(input => (input as HTMLInputElement).value)).toEqual(["Компьютер", "Отдел"]);
  expect(screen.getByDisplayValue("Имя устройства")).toBeVisible();
  fireEvent.change(screen.getByDisplayValue("ИТ"), { target: { value: "Поддержка" } });
  expect(change.mock.lastCall?.[0].fields[1].options).toEqual([{ value: "it", label: "Поддержка" }]);
});
it("shows clearly labelled employee answer examples without accepting author answers", () => {
  const change = vi.fn();
  render(<Harness initial={{ ...page, fields: [...page.fields, { key: "c", type: "textarea", label: "Описание" }] }} onChange={change} />);
  expect(screen.getAllByText("Так выглядит поле ответа сотрудника")).toHaveLength(3);
  expect(screen.getByRole("textbox", { name: "Описание" }).tagName).toBe("TEXTAREA");
  expect(screen.getByRole("combobox", { name: "Отдел" })).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Компьютер" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Описание" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "Отдел" })).toBeDisabled();
  expect(change).not.toHaveBeenCalled();
});
it("reorders with keyboard and preserves IDs and referenced-field guards on count reduction", () => {
  const change = vi.fn();
  const initial = { ...page, fields: [page.fields[0], { ...page.fields[1], visible_when: { source: "answer" as const, field: "a", op: "exists" as const } }] };
  render(<Harness initial={initial} onChange={change} />);
  fireEvent.click(screen.getByRole("button", { name: "Вопрос 1 вниз" }));
  expect(change.mock.lastCall?.[0].fields.map((field: { key: string }) => field.key)).toEqual(["b", "a"]);
  fireEvent.change(screen.getByLabelText("Количество вопросов"), { target: { value: "1" } });
  expect(screen.getByRole("alert")).toHaveTextContent("зависимости");
  expect(screen.getAllByLabelText("Что спросить?")).toHaveLength(2);
});
it("renders section order exactly as the employee and moves a question into the adjacent section", () => {
  const change = vi.fn();
  const initial: Page = { ...page, layout: "section", fields: [
    { ...page.fields[0], group: "one", group_title: "Первый" },
    { ...page.fields[1], group: "two", group_title: "Второй" },
    { key: "c", type: "text", label: "Адрес", group: "one", group_title: "Первый" },
  ] };
  render(<Harness initial={initial} onChange={change} />);
  expect(screen.getAllByLabelText("Что спросить?").map(input => (input as HTMLInputElement).value)).toEqual(["Компьютер", "Адрес", "Отдел"]);
  fireEvent.click(screen.getByRole("button", { name: "Вопрос 2 вниз" }));
  expect(change.mock.lastCall?.[0].fields.map((field: { key: string }) => field.key)).toEqual(["a", "b", "c"]);
  expect(change.mock.lastCall?.[0].fields[2].group).toBe("two");
  expect(within(screen.getByRole("group", { name: "Второй" })).getByDisplayValue("Адрес")).toBeVisible();
});
it("opening a v4 question provides rich help directly and never dirties plain legacy content", () => {
  const change = vi.fn(); render(<Harness schema={4} onChange={change} />);
  expect(screen.queryByRole("button", { name: "Оформить подсказку визуально" })).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});
it.each([1, 2, 3])("opening a v%i question keeps legacy help plain without emitting changes", schema => {
  const change = vi.fn(); render(<Harness schema={schema} onChange={change} />);
  expect(screen.getByDisplayValue("Имя устройства")).toBeVisible();
  expect(screen.queryByRole("textbox", { name: "Подсказка к вопросу" })).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
});
it("copies a question with a fresh key while keeping other questions and conditions intact", () => {
  const change = vi.fn(); render(<Harness onChange={change} />);
  fireEvent.click(within(screen.getByRole("article", { name: "Вопрос 2" })).getByRole("button", { name: "Копировать вопрос" }));
  const next = change.mock.lastCall?.[0];
  expect(next.fields.slice(0, 2)).toEqual(page.fields);
  expect(next.fields[2].key).not.toBe("b");
  expect(next.fields[2].options).toEqual([{ value: "it", label: "ИТ" }]);
});
it("reorders when dropping on a nested rich editor that consumes bubble-phase drops", () => {
  const change = vi.fn(); render(<Harness schema={4} onChange={change} />);
  const target = screen.getAllByRole("textbox", { name: "Подсказка к вопросу" })[0].querySelector("p")!;
  // ProseMirror owns native text drops; the page must intercept its own question drag first.
  target.addEventListener("drop", event => event.stopPropagation());
  target.addEventListener("dragover", event => event.stopPropagation());
  const dataTransfer = { types: ["application/x-studio-question"], files: [], items: [], effectAllowed: "move", dropEffect: "move", getData: () => "b", setData: vi.fn() };
  fireEvent.dragStart(screen.getByRole("button", { name: "Переместить вопрос 2" }), { dataTransfer });
  fireEvent.dragOver(target, { dataTransfer });
  fireEvent.drop(target, { dataTransfer });
  expect(change.mock.lastCall?.[0].fields.map((field: { key: string }) => field.key)).toEqual(["b", "a"]);
});
it("leaves file drops to the nested attachment surface even during an unfinished question drag", () => {
  const change = vi.fn(); render(<Harness onChange={change} />);
  const target = screen.getByDisplayValue("Имя устройства"), dropped = vi.fn();
  target.addEventListener("drop", dropped);
  const question = { types: ["application/x-studio-question"], files: [], setData: vi.fn() };
  fireEvent.dragStart(screen.getByRole("button", { name: "Переместить вопрос 2" }), { dataTransfer: question });
  fireEvent.drop(target, { dataTransfer: { types: ["Files"], files: [new File(["image"], "screen.png", { type: "image/png" })], items: [] } });
  expect(dropped).toHaveBeenCalledOnce(); expect(change).not.toHaveBeenCalled();
});
