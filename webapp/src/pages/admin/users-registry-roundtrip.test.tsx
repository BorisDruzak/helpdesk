import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogFixture, registryFixture, summaryFixture } from "../../features/users/users-fixtures";
import { AdminUsersPage } from "./users-page";
import { RegistryPersonOperations } from "./registry-page";

const json = (data: unknown) => new Response(JSON.stringify({ status: "success", data }), { headers: { "Content-Type": "application/json" } });

function setup() {
  const registry = structuredClone(registryFixture);
  registry.ui_users = [{ ...registry.ui_users![0], user_login: "marina", linked_person_id: "person-marina", linked_person_name: "Марина Заваруха" }];
  let account = { user_login: "marina", actor_role: "user", is_active: true, queue_ids: [7], group_ids: [] };
  const writes: Array<Record<string, unknown>> = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/ui-users/marina/disable") && init?.method === "POST") {
      account = { ...account, is_active: false };
      registry.ui_users![0].is_active = false;
      return json({ updated: true });
    }
    if (url.endsWith("/account") && init?.method === "PUT") {
      writes.push(JSON.parse(String(init.body)));
      return json({ account });
    }
    if (url.endsWith("/registry")) return json(registry);
    if (url.endsWith("/catalog")) return json(catalogFixture);
    if (url.endsWith("/summary")) return json({ ...summaryFixture, users: [{ ...summaryFixture.users[0], user_login: "marina", is_active: account.is_active }] });
    if (url.endsWith("/account")) return json({ accounts: [account] });
    if (url.includes("/effective?")) return json({ actor_id: "marina", actor_role: "user", role_label: "Сотрудник", permissions: [], workspaces: [], groups: [], queues: [], sources: {} });
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: Infinity } } });
  const invalidations = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><MemoryRouter><AdminUsersPage renderOperations={personId => <RegistryPersonOperations personId={personId} />} /></MemoryRouter></QueryClientProvider>);
  return { writes, invalidations };
}

afterEach(() => vi.unstubAllGlobals());

describe("Users and advanced Registry operations", () => {
  it("refreshes account and access caches after disabling a login and uses the disabled state on the next save", async () => {
    const { writes, invalidations } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Учётная запись" }));
    expect(screen.getByLabelText("Учётная запись активна")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Дополнительные операции" }));
    fireEvent.click(await screen.findByRole("button", { name: "Отключить вход marina" }));
    fireEvent.change(screen.getByLabelText("Причина"), { target: { value: "Временное отключение" } });
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await waitFor(() => {
      for (const key of ["admin-user-accounts", "admin-access-summary", "admin-access-effective", "admin-access-audit"]) {
        expect(invalidations).toHaveBeenCalledWith({ queryKey: [key] });
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "Пользователи" }));
    await waitFor(() => expect(screen.getByLabelText("Учётная запись активна")).not.toBeChecked());
    fireEvent.change(screen.getByLabelText("Причина изменения"), { target: { value: "Подтверждение состояния" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].is_active).toBe(false);
  });

  it("preserves an edited card across advanced operations but blocks stale access until the administrator reloads it", async () => {
    const { writes, invalidations } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Учётная запись" }));
    fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "support" } });
    fireEvent.change(screen.getByLabelText("Причина изменения"), { target: { value: "Назначение поддержки" } });
    fireEvent.click(screen.getByRole("button", { name: "Дополнительные операции" }));
    fireEvent.click(await screen.findByRole("button", { name: "Отключить вход marina" }));
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));
    await waitFor(() => expect(invalidations).toHaveBeenCalledWith({ queryKey: ["admin-user-accounts"] }));
    fireEvent.click(screen.getByRole("button", { name: "Пользователи" }));
    expect(screen.getByLabelText("Роль")).toHaveValue("support");
    expect(screen.getByLabelText("Причина изменения")).toHaveValue("Назначение поддержки");
    await waitFor(() => expect(screen.getByRole("button", { name: "Сохранить доступ" })).toBeDisabled());
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Отменить черновик и загрузить актуальные данные" }));
    expect(screen.getByLabelText("Роль")).toHaveValue("user");
    expect(screen.getByLabelText("Учётная запись активна")).not.toBeChecked();
  });
});
