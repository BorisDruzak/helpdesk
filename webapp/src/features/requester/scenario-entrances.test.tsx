import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioEntrances } from "./scenario-entrances";
vi.mock("./scenario-session", () => ({ ScenarioSession: ({ entryPointKey }: { entryPointKey?: string }) => <div>Entrance:{entryPointKey ?? "legacy"}</div> }));
it("searches published entrance synonyms and starts the chosen entrance", () => {
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", description: "Извлеките бумагу", synonyms: ["замятие"], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper_block" }] }} owner="user" deviceId="" />);
  fireEvent.change(screen.getByLabelText("Найти проблему"), { target: { value: "замятие" } });
  fireEvent.click(screen.getByRole("button", { name: /Бумага застряла/ }));
  expect(screen.getByText("Entrance:paper")).toBeVisible();
});
it("preserves the legacy single entrance", () => {
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing" }} owner="user" deviceId="" />);
  expect(screen.getByText("Entrance:legacy")).toBeVisible();
});
