import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioVersionHistory } from "./scenario-version-history";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("copies a chosen version to a new draft revision without publishing it", async () => {
  const detail = { scenario: { id: "scenario" }, draft: { revision: 3, definition: { title: "Ранее" } } };
  const accept = vi.fn();
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/versions")) return new Response(JSON.stringify({ status: "success", data: [{ id: "v1", version: 1, state: "retired" }] }), { headers: { "Content-Type": "application/json" } });
    expect(url).toContain("/rollback-draft");
    expect(JSON.parse(String(init?.body))).toEqual({ revision: 2, version_id: "v1" });
    return new Response(JSON.stringify({ status: "success", data: detail }), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioVersionHistory id="scenario" revision={2} disabled={false} onAccept={accept} />);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "История версий" }));
  await screen.findByRole("option", { name: "Версия 1 — ранее опубликована" });
  const restore = screen.getByRole("button", { name: "Вернуть выбранную версию в черновик" });
  expect(restore).toBeDisabled();
  fireEvent.change(screen.getByRole("combobox", { name: "Версия для черновика" }), { target: { value: "v1" } });
  fireEvent.click(restore);
  await screen.findByText("Версия скопирована в черновик. Перед публикацией проверьте её заново.");
  expect(accept).toHaveBeenCalledWith(detail);
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
