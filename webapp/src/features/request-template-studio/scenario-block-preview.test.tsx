import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScenarioBlockPreview } from "./scenario-block-preview";

it("previews requester controls and section headings without executing a branch", () => {
  render(<ScenarioBlockPreview block={{ id: "questions", kind: "form_page", title: "Принтер", layout: "section", fields: [
    { key: "printer", type: "text", label: "Модель принтера", group: "details", group_title: "Устройство" },
    { key: "power", type: "radio", label: "Питание", options: [{ value: "on", label: "Включён" }], group: "details", group_title: "Устройство" },
  ] }} />);
  expect(screen.getByRole("group", { name: "Устройство" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Модель принтера" })).toBeDisabled();
  expect(screen.getByRole("radio", { name: "Включён" })).toBeDisabled();
});
