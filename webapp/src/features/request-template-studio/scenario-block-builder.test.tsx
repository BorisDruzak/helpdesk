import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { ScenarioBlockBuilder } from "./scenario-block-builder";
import type { ScenarioDraftDefinition } from "./scenario-contract";

function Harness() {
  const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "test", title: "Тест", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, blocks: [] });
  return <ScenarioBlockBuilder definition={definition} disabled={false} onChange={setDefinition} />;
}
it("makes next-step controls available without opening advanced settings", () => {
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Тип нового блока"), { target: { value: "instruction" } });
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  fireEvent.change(screen.getByLabelText("Тип нового блока"), { target: { value: "finish" } });
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  fireEvent.click(screen.getByRole("button", { name: "Инструкция" }));
  expect(screen.getByRole("button", { name: "Добавить переход" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Добавить переход" })).toBeEnabled();
});
it("shows diagnostic consent, execution boundary and missing mandatory fallback", () => {
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Тип нового блока"), { target: { value: "diagnostic" } });
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  expect(screen.getByText("Запасной шаг не выбран. Публикация будет заблокирована.")).toBeInTheDocument();
  expect(screen.getByText("Согласие хранится как настройка. В симуляции реального разрешения нет.")).toBeInTheDocument();
  expect(screen.getByLabelText("Запрашивать согласие")).toBeChecked();
});
it("adds blocks, focuses the selected editor, adds a field and supports undo/redo", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  expect(screen.getByLabelText("Название блока")).toHaveFocus();
  expect(screen.getAllByLabelText("Название вопроса")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Добавить вопрос" }));
  expect(screen.getAllByLabelText("Название вопроса")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Название вопроса"), { target: { value: "Уточнение" } });
  fireEvent.click(screen.getByRole("button", { name: "Отменить изменение" }));
  expect(screen.getByLabelText("Название вопроса")).toHaveValue("Новый вопрос");
  fireEvent.click(screen.getByRole("button", { name: "Повторить изменение" }));
  expect(screen.getByLabelText("Название вопроса")).toHaveValue("Уточнение");
});
it("keeps settings local, permits multiple roles and disables incompatible roles and files", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  const editor = screen.getByRole("group", { name: "Редактор вопроса" });
  fireEvent.click(within(editor).getByText("Расширенные настройки"));
  expect(within(editor).getByLabelText("Влияние на приоритет")).toBeDisabled();
  fireEvent.click(within(editor).getByLabelText("Отчётность"));
  fireEvent.click(within(editor).getByLabelText("Факт паспорта"));
  expect(within(editor).getByLabelText("Отчётность")).toBeChecked();
  expect(within(editor).getByLabelText("Факт паспорта")).toBeChecked();
  expect(within(editor).getByRole("option", { name: /Вложение/ })).toBeDisabled();
});
it("changes the selected block with keyboard controls and shows only its editor", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  fireEvent.change(screen.getByLabelText("Тип нового блока"), { target: { value: "instruction" } });
  fireEvent.click(screen.getByRole("button", { name: "Добавить блок" }));
  expect(screen.queryByLabelText("Название вопроса")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Текст инструкции")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Переместить блок вверх" }));
  expect(within(screen.getByRole("list", { name: "Блоки сценария" })).getAllByRole("button")[0]).toHaveTextContent("Инструкция");
  fireEvent.click(screen.getByRole("button", { name: "Страница вопросов" }));
  expect(screen.queryByLabelText("Текст инструкции")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Название вопроса")).toBeInTheDocument();
});
it("keeps every mutation disabled for an auditor while selection remains readable", () => {
  const definition: ScenarioDraftDefinition = { scenario_key: "test", title: "Test", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, blocks: [{ id: "first", title: "Вопросы", kind: "form_page", fields: [{ key: "question", type: "text", label: "Вопрос" }] }] };
  render(<ScenarioBlockBuilder definition={definition} disabled onChange={() => { throw Error("readonly mutation"); }} />);
  expect(screen.getByRole("button", { name: "Добавить блок" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Удалить блок" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Добавить вопрос" })).toBeDisabled();
  expect(screen.getByLabelText("Название блока")).toBeDisabled();
  expect(screen.getByLabelText("Название вопроса")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Вопросы" })).toBeEnabled();
});
