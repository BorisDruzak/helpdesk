import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClosurePolicyControls, VisibilityPolicyControls } from "../forms-builder/forms-builder-panel";
afterEach(cleanup);
it("uses effective nested resolution codes and preserves unknown codes and policy extras", () => {
  const config = { custom: { preserved: true }, allowed_resolution_codes: ["duplicate"], before_resolved: { allowed_resolution_codes: ["fixed_remote", "custom_existing"], preserved: 42 } };
  const change = vi.fn();
  render(<ClosurePolicyControls config={config} onChange={change} runtimeDefaults friendly />);
  expect(screen.getByLabelText("Допустимые результаты решения: Исправлено удалённо")).toBeChecked();
  expect(screen.getByLabelText("Допустимые результаты решения: Повторное обращение")).not.toBeChecked();
  expect(screen.queryByText(/custom_existing/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Допустимые результаты решения: Повторное обращение"));
  expect(change).toHaveBeenCalledWith({ ...config, before_resolved: { ...config.before_resolved, allowed_resolution_codes: ["fixed_remote", "custom_existing", "duplicate"] } });
});
it("preserves visibility paths, structured status mappings and unknown settings", () => {
  const config = { extra: 1, show_to_requester: ["public_messages", "custom.legacy"], hide_from_requester: ["internal_notes"], public_status_mapping: { new: { status: "accepted", title: "Принято", extra: true } } };
  const change = vi.fn();
  render(<VisibilityPolicyControls config={config} onChange={change} friendly />);
  fireEvent.click(screen.getByLabelText("Показывать сотруднику: Плановый срок решения"));
  expect(change).toHaveBeenLastCalledWith({ ...config, show_to_requester: ["public_messages", "custom.legacy", "expected_due_at"] });
  expect(screen.getByLabelText("Статус «Обращение принято»")).toHaveValue("Принято");
  fireEvent.change(screen.getByLabelText("Статус «Обращение принято»"), { target: { value: "Мы получили заявку" } });
  expect(change).toHaveBeenLastCalledWith({ ...config, public_status_mapping: { new: { ...config.public_status_mapping.new, label: "Мы получили заявку" } } });
});
