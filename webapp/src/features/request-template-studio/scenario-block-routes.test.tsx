import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioBlockRoutes } from "./scenario-block-routes";
import type { ScenarioDraftDefinition } from "./scenario-contract";
afterEach(cleanup);
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
