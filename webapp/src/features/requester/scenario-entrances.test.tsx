import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioEntrances } from "./scenario-entrances";
vi.mock("./scenario-session", () => ({ ScenarioSession: ({ entryPointKey }: { entryPointKey?: string }) => <div>Entrance:{entryPointKey ?? "legacy"}</div> }));
it("starts an explicit published entrance without adding another search input", () => {
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", description: "Извлеките бумагу", synonyms: ["замятие"], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper_block" }] }} owner="user" deviceId="" />);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Бумага застряла/ }));
  expect(screen.getByText("Entrance:paper")).toBeVisible();
});
it("preserves the legacy single entrance", () => {
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing" }} owner="user" deviceId="" />);
  expect(screen.getByText("Entrance:legacy")).toBeVisible();
});
it("shows published problems for a direct service link instead of an empty panel", () => {
  cleanup();
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", synonyms: [], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper" }] }} owner="direct-user" deviceId="" onBrowse={() => {}} />);
  expect(screen.getByRole("button", { name: "Бумага застряла" })).toBeVisible();
  expect(screen.queryByText("Entrance:legacy")).not.toBeInTheDocument();
});
it("offers catalog navigation for a scenario without named entrances", () => {
  cleanup();
  const browse = vi.fn();
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing" }} owner="user" deviceId="" onBrowse={browse} />);
  fireEvent.click(screen.getByRole("button", { name: "Другой пункт каталога" }));
  expect(browse).toHaveBeenCalledOnce();
});
it("does not restore a cached problem while browsing service categories", () => {
  sessionStorage.setItem("pc_client.scenario.selection:browsing-user:it.printer", "paper");
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", synonyms: [], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper" }] }} owner="browsing-user" deviceId="" onBrowse={() => {}} />);
  expect(screen.queryByText("Entrance:paper")).not.toBeInTheDocument();
});
it("remembers the explicit whole-catalog entrance across a page reload", () => {
  sessionStorage.clear();
  const offering = { offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", synonyms: [], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper_block" }] };
  render(<ScenarioEntrances offering={offering} owner="search-user" deviceId="" initialEntryPointKey="paper" />);
  expect(screen.getByText("Entrance:paper")).toBeVisible();
  cleanup();
  render(<ScenarioEntrances offering={offering} owner="search-user" deviceId="" />);
  expect(screen.getByText("Entrance:paper")).toBeVisible();
});
