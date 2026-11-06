import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSaveRecovery } from "./scenario-save-recovery";
afterEach(() => vi.unstubAllGlobals());
it.each([[null, false], ["other", false], ["admin-2", true]])("only retries for the original administrator after checking the session: %s", async (login, retries) => {
  const retry = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { user_login: login, actor_role: "admin" } }), { status: login ? 200 : 401, headers: { "content-type": "application/json" } })));
  render(<ScenarioSaveRecovery kind="session" actorLogin="admin-2" disabled={false} onRetry={retry} />);
  expect(screen.getByRole("link", { name: "Войти в отдельной вкладке" })).toHaveAttribute("target", "_blank");
  fireEvent.click(screen.getByRole("button", { name: "Проверить вход и сохранить" }));
  await waitFor(() => retries ? expect(retry).toHaveBeenCalledOnce() : expect(screen.getByRole("status")).toHaveTextContent(login ? "другой учётной записью" : "Вход ещё не выполнен"));
  expect(retry).toHaveBeenCalledTimes(retries ? 1 : 0);
});
