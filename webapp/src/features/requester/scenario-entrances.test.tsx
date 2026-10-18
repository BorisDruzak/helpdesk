import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioEntrances } from "./scenario-entrances";
import { ScenarioSession } from "./scenario-session";
vi.mock("./scenario-session", () => ({ ScenarioSession: vi.fn(({ entryPointKey }: { entryPointKey?: string }) => <div>Entrance:{entryPointKey ?? "legacy"}</div>) }));
it("leaves entrance selection to the unified search without a second local filter", () => {
  sessionStorage.clear();
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", description: "Извлеките бумагу", synonyms: ["замятие"], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper_block" }] }} owner="user" deviceId="" />);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByText(/^Entrance:/)).not.toBeInTheDocument();
  expect(screen.getByText("Выберите проблему в поиске выше, чтобы начать пошаговую помощь.")).toBeVisible();
});
it("preserves the legacy single entrance", () => {
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing" }} owner="user" deviceId="" />);
  expect(screen.getByText("Entrance:legacy")).toBeVisible();
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
it("does not start a session for a removed stored entrance", () => {
  sessionStorage.setItem("pc_client.scenario.selection:stale-user:it.printer", "removed");
  render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: [{ key: "paper", title: "Бумага застряла", synonyms: [], entry_point_key: "paper", scenario_key: "print", version_id: "v1", target_block_id: "paper_block" }] }} owner="stale-user" deviceId="" />);
  expect(screen.queryByText(/^Entrance:/)).not.toBeInTheDocument();
  expect(screen.getByText(/Выберите проблему в поиске выше/)).toBeVisible();
});
it("follows an explicit entrance change while preserving the selected offering", () => {
  sessionStorage.clear();
  const offering = { offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: ["paper", "network"].map(key => ({ key, title: key, synonyms: [], entry_point_key: key, scenario_key: "print", version_id: "v1", target_block_id: key })) };
  const view = render(<ScenarioEntrances offering={offering} owner="switch-user" deviceId="" initialEntryPointKey="paper" />);
  expect(screen.getByText("Entrance:paper")).toBeVisible();
  view.rerender(<ScenarioEntrances offering={offering} owner="switch-user" deviceId="" initialEntryPointKey="network" />);
  expect(screen.getByText("Entrance:network")).toBeVisible();
});
it.each([true, false])("resumes a pinned removed entrance without creating a session (other published entrances: %s)", async hasPublishedEntrances => {
  sessionStorage.clear();
  const retiredEntry = "paper/retired";
  sessionStorage.setItem("pc_client.scenario.selection:pinned-user:it.printer", retiredEntry);
  sessionStorage.setItem("pc_client.scenario.session:pinned-user:it.printer:entry:paper%2Fretired", "opaque-pinned-session");
  const actual = await vi.importActual<typeof import("./scenario-session")>("./scenario-session");
  vi.mocked(ScenarioSession).mockImplementation(actual.ScenarioSession);
  const fetcher = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ status: "success", data: { id: "opaque-pinned-session", revision: 7, state: "active", back_targets: [], block: { id: "old_question", kind: "instruction", title: "Продолжение прежней версии", content: { body: "Сохранённые ответы и маршрут" } } } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  try {
    render(<ScenarioEntrances offering={{ offering_code: "printer", full_code: "it.printer", title: "Printing", catalog_items: hasPublishedEntrances ? [{ key: "new", title: "Новая проблема", synonyms: [], entry_point_key: "new", scenario_key: "print", version_id: "v2", target_block_id: "new_question" }] : [] }} owner="pinned-user" deviceId="" />);
    expect(await screen.findByRole("heading", { name: "Продолжение прежней версии" })).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("/api/web/requester/request-scenarios/sessions/opaque-pinned-session");
    expect(fetcher.mock.calls[0][1]).toMatchObject({ method: "GET", body: undefined });
  } finally {
    cleanup(); vi.unstubAllGlobals(); sessionStorage.clear();
    vi.mocked(ScenarioSession).mockImplementation(({ entryPointKey }) => <div>Entrance:{entryPointKey ?? "legacy"}</div>);
  }
});
