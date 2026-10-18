import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioAnswerBranches } from "./scenario-answer-branches-editor";

const draft = (): ScenarioDraftDefinition => ({
  schema_version: 3, scenario_key: "branches", title: "Развилка", service_code: "it", offering_full_code: "it.branches", process_binding: { request_template_key: "branches" },
  blocks: [
    { id: "q", kind: "form_page", title: "123", fields: [{ key: "working", label: "Работает?", type: "checkbox" }], transitions: [{ to: "d" }] },
    { id: "d", kind: "decision", title: "Условие", transitions: [] },
  ],
});
describe("answer branch construction from an empty decision", () => {
  it("shows the incoming question and creates either answer without pre-existing target blocks", () => {
    const definition = draft(), change = vi.fn(), add = vi.fn();
    render(<ScenarioAnswerBranches definition={definition} block={definition.blocks![1]} disabled={false} onChange={change} onAdd={add} />);
    expect(screen.getByLabelText("Вопрос для ветвления")).toHaveDisplayValue("Работает?");
    expect(screen.getByRole("group", { name: "Ответ «Да»" })).toBeVisible();
    expect(screen.getByRole("group", { name: "Ответ «Нет»" })).toBeVisible();
    expect(within(screen.getByRole("group", { name: "Ответ «Нет»" })).queryByRole("option", { name: "123" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Добавить шаг для «Нет»" }));
    expect(add).toHaveBeenCalledWith({ source: "answer", field: "working", op: "eq", value: false });
    expect(change).not.toHaveBeenCalled();
  });
  it("switches the source explicitly without altering saved transitions", () => {
    const definition = draft(), change = vi.fn(), add = vi.fn();
    const q = definition.blocks![0];
    if (q.kind === "form_page") q.fields.push({ key: "issue", type: "radio", label: "Что сломалось?", options: [{ value: "printer", label: "Принтер" }, { value: "network", label: "Сеть" }] });
    render(<ScenarioAnswerBranches definition={definition} block={definition.blocks![1]} disabled={false} onChange={change} onAdd={add} />);
    fireEvent.change(screen.getByLabelText("Вопрос для ветвления"), { target: { value: "issue" } });
    expect(screen.queryByRole("group", { name: "Ответ «Да»" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Добавить шаг для «Сеть»" }));
    expect(add).toHaveBeenCalledWith({ source: "answer", field: "issue", op: "eq", value: "network" });
    expect(change).not.toHaveBeenCalled();
    expect(definition.blocks![1].transitions).toEqual([]);
  });
  it("connects the negative answer to an existing valid target with a typed false value", () => {
    const definition = draft(), change = vi.fn();
    definition.blocks!.push({ id: "help", kind: "submit_ticket", title: "В поддержку" });
    render(<ScenarioAnswerBranches definition={definition} block={definition.blocks![1]} disabled={false} onChange={change} />);
    fireEvent.change(within(screen.getByRole("group", { name: "Ответ «Нет»" })).getByLabelText("Следующий шаг"), { target: { value: "help" } });
    expect(change.mock.calls[0][0].blocks[1].transitions).toEqual([{ to: "help", when: { source: "answer", field: "working", op: "eq", value: false } }]);
  });
  it("keeps read-only branches visible and prevents mutations", () => {
    const definition = draft(), change = vi.fn(), add = vi.fn();
    render(<ScenarioAnswerBranches definition={definition} block={definition.blocks![1]} disabled onChange={change} onAdd={add} />);
    expect(screen.getByLabelText("Вопрос для ветвления")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Добавить шаг для «Да»" })).toBeDisabled();
    expect(change).not.toHaveBeenCalled();
  });
});
