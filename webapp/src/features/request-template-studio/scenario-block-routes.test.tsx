import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioBlockRoutes } from "./scenario-block-routes";
import type { ScenarioDraftDefinition } from "./scenario-contract";
afterEach(cleanup);
it("collapses branches independently with human summaries and no scenario writes", () => {
  const definition: ScenarioDraftDefinition = { schema_version: 2, scenario_key: "s", title: "Test", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
    { id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "private_key", type: "select", label: "Что не работает?", options: [{ value: "mail_raw", label: "Почта" }, { value: "vpn_raw", label: "VPN" }] }], transitions: [{ to: "d" }] },
    { id: "d", kind: "decision", title: "Маршрут", transitions: [{ to: "d2", when: { op: "eq", source: "answer", field: "private_key", value: "mail_raw" } }, { to: "end", when: { op: "eq", source: "answer", field: "private_key", value: "vpn_raw" } }, { to: "end" }] },
    { id: "d2", kind: "decision", title: "Дополнительная проверка", transitions: [{ to: "end" }] }, { id: "end", kind: "submit_ticket", title: "В поддержку" },
  ] };
  const change = vi.fn();
  function Harness() { const [draft, setDraft] = useState(definition); return <ScenarioBlockRoutes definition={draft} block={draft.blocks![1]} disabled={false} onChange={next => { change(next); setDraft(next); }} />; }
  render(<Harness />);
  const first = screen.getByRole("button", { name: /Ветвь 1/ });
  expect(first).toHaveTextContent("Почта"); expect(first).toHaveTextContent("Дополнительная проверка");
  expect(first).not.toHaveTextContent(/private_key|mail_raw/);
  expect(first).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByLabelText("Значение условия")).not.toBeInTheDocument();
  fireEvent.click(first);
  expect(first).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("Почта");
  expect(change).not.toHaveBeenCalled();
  fireEvent.click(first);
  fireEvent.click(screen.getByRole("button", { name: /Ветвь 2/ }));
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("VPN");
  fireEvent.change(screen.getByLabelText("Следующий блок"), { target: { value: "d2" } });
  expect(change.mock.calls[0][0].blocks[1].transitions[1].to).toBe("d2");
  expect(screen.getByRole("button", { name: /Ветвь 2/ })).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(screen.getByRole("button", { name: "Развернуть все ветви" }));
  expect(screen.getAllByLabelText("Значение условия")).toHaveLength(2);
  expect(screen.getByLabelText("Если ни одно условие не выполнено")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Удалить ветвь 1" }));
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("VPN");
  fireEvent.click(screen.getByRole("button", { name: "Свернуть все ветви" }));
  expect(screen.queryByLabelText("Значение условия")).not.toBeInTheDocument();
});
it("creates a branch for a selected answer and preserves the fallback last", () => {
  const definition: ScenarioDraftDefinition = { schema_version: 2, scenario_key: "test", title: "Test", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
    { id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "issue", type: "select", label: "Что не работает?", options: [{ value: "mail", label: "Почта" }, { value: "vpn", label: "VPN" }] }], transitions: [{ to: "d" }] },
    { id: "d", kind: "decision", title: "Условие", transitions: [{ to: "other" }] },
    { id: "mail", kind: "instruction", title: "Проверка почты", content: { body: "Проверьте адрес" }, transitions: [{ to: "other" }] },
    { id: "other", kind: "submit_ticket", title: "В поддержку" },
  ] };
  const change = vi.fn();
  const view = render(<ScenarioBlockRoutes definition={definition} block={definition.blocks![1]} disabled={false} onChange={change} />);
  fireEvent.change(screen.getByLabelText("Добавить условную ветвь"), { target: { value: "mail" } });
  const next = change.mock.calls[0][0];
  expect(next.blocks[1].transitions).toEqual([{ to: "mail", when: { op: "eq", source: "answer", field: "issue", value: "mail" } }, { to: "other" }]);
  view.rerender(<ScenarioBlockRoutes definition={next} block={next.blocks[1]} disabled={false} onChange={change} />);
  expect(screen.getByRole("option", { name: "Что не работает?" })).toBeInTheDocument();
  expect(screen.getByLabelText("Значение условия")).toHaveDisplayValue("Почта");
  fireEvent.change(screen.getByLabelText("Значение условия"), { target: { value: "vpn" } });
  expect(change.mock.calls[1][0].blocks[1].transitions[0].when.value).toBe("vpn");
});
it("creates a multi-select membership branch with immediate choices and preserves its fallback", () => {
  const definition: ScenarioDraftDefinition = { schema_version: 2, scenario_key: "test", title: "Test", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, entry_block_id: "q", blocks: [
    { id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "issues", type: "multi_select", label: "Что не работает?", options: [{ value: "printer", label: "Принтер" }, { value: "network", label: "Сеть" }] }], transitions: [{ to: "d" }] },
    { id: "d", kind: "decision", title: "Условие", transitions: [{ to: "other" }] },
    { id: "other", kind: "submit_ticket", title: "В поддержку" },
  ] };
  const unchanged = structuredClone(definition), change = vi.fn();
  function Harness() { const [draft, setDraft] = useState(definition); return <ScenarioBlockRoutes definition={draft} block={draft.blocks![1]} disabled={false} onChange={next => { change(next); setDraft(next); }} />; }
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Добавить условную ветвь"), { target: { value: "other" } });
  expect(change.mock.calls[0][0].blocks[1].transitions).toEqual([{ to: "other", when: { op: "in", source: "answer", field: "issues", value: ["printer"] } }, { to: "other" }]);
  expect(screen.getByLabelText("Правило")).toHaveValue("in");
  expect(screen.getByRole("checkbox", { name: "Принтер" })).toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "Сеть" }));
  expect(change.mock.calls.at(-1)![0].blocks[1].transitions).toEqual([{ to: "other", when: { op: "in", source: "answer", field: "issues", value: ["printer", "network"] } }, { to: "other" }]);
  expect(definition).toEqual(unchanged);
});
