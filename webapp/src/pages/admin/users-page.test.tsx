import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { catalogFixture, registryFixture, summaryFixture } from "../../features/users/users-fixtures";
import { AdminUsersPage } from "./users-page";

const json = (data: unknown, status = 200) => new Response(JSON.stringify(status === 200 ? { status: "success", data } : { status: "error", error: data }), { status, headers: { "Content-Type": "application/json" } });
function setup(options: { error?: boolean; readError?: boolean; degraded?: boolean; accounts?: Record<string, unknown[]>; delayed?: Promise<Response>; profileDelay?: Promise<Response> } = {}) {
  const writes: Array<{ url: string; body: Record<string, unknown> }> = [];
  const registry = structuredClone(registryFixture);
  const accounts = structuredClone(options.accounts ?? {}) as Record<string, Array<Record<string, unknown>>>;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "PATCH" && options.profileDelay) return options.profileDelay;
    if (init?.method === "POST" && url.endsWith("/registry/people")) {
      registry.people.push({ ...registry.people[0], person_id: "person-new", id: "person-new", ...JSON.parse(init.body as string) });
      return json({ person: { person_id: "person-new" } });
    }
    if (init?.method === "PUT") {
      writes.push({ url, body: JSON.parse(init.body as string) });
      if (options.delayed) return options.delayed;
      if (options.error) return json("Не удалось сохранить: очередь недоступна", 400);
      const { password: _password, reason: _reason, ...account } = JSON.parse(init.body as string);
      const personKey = url.includes("person-marina") ? "marina" : "ivan";
      accounts[personKey] = [...(accounts[personKey] ?? []).filter((item) => item.user_login !== account.user_login), account];
      return json({ account });
    }
    if (url.endsWith("/registry")) return json(registry);
    if (url.endsWith("/catalog")) return json(catalogFixture);
    if (url.endsWith("/summary")) return json(options.degraded ? { ...summaryFixture, queues: [], access_groups: [], users: [], notes: ["DB-backed users/queues are temporarily unavailable."] } : summaryFixture);
    if (url.endsWith("/audit")) return json({ items: [] });
    if (url.includes("/effective?")) return json({ actor_id: "marina", actor_role: "support", role_label: "Сотрудник техподдержки", permissions: [], workspaces: [], groups: ["specialists"], queues: [{ queue_id: 8, queue_name: "Вторая линия", queue_code: "l2", role_in_queue: null }], sources: {} });
    if (url.includes("/account?user_login=")) return json({ accounts: [{ user_login: "unlinked.marina", actor_role: "user", is_active: true, queue_ids: [7], group_ids: [10] }] });
    if (url.endsWith("/account")) return options.readError ? json("Не удалось обновить входы", 503) : json({ accounts: accounts[url.includes("person-marina") ? "marina" : "ivan"] ?? [] });
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AdminUsersPage /></MemoryRouter></QueryClientProvider>);
  return { writes, client, accounts };
}
afterEach(() => vi.unstubAllGlobals());

async function fillAccount() {
  fireEvent.click(await screen.findByRole("button", { name: "Учётная запись" }));
  fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "marina" } });
  fireEvent.change(screen.getByLabelText("Пароль для нового входа"), { target: { value: "Example-password-42" } });
  fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "support" } });
  fireEvent.change(screen.getByLabelText("Причина изменения"), { target: { value: "Назначение в техподдержку" } });
  fireEvent.click(screen.getByRole("button", { name: "Права и очереди" }));
  fireEvent.click(screen.getByLabelText("ServiceDesk L1"));
}

describe("unified users workspace", () => {
  it("creates Marina's account, support role and direct queue in one save", async () => {
    const { writes } = setup();
    await fillAccount();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    await screen.findByText("Доступ сохранён");
    expect(writes).toEqual([{ url: "/api/web/admin/users/person-marina/account", body: { user_login: "marina", password: "Example-password-42", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [], reason: "Назначение в техподдержку" } }]);
  });
  it("preserves drafts on save error and background refetch", async () => {
    const { client } = setup({ error: true });
    await fillAccount();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    await screen.findByRole("alert");
    await client.invalidateQueries({ queryKey: ["admin-user-accounts", "person-marina"] });
    expect(screen.getByLabelText("ServiceDesk L1")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Учётная запись" }));
    expect(screen.getByLabelText("Логин")).toHaveValue("marina");
    expect(screen.getByLabelText("Пароль для нового входа")).toHaveValue("Example-password-42");
  });
  it("finds unlinked accounts and links them to a named person", async () => {
    const { writes } = setup();
    fireEvent.change(await screen.findByLabelText("Поиск пользователей"), { target: { value: "unlinked.marina" } });
    fireEvent.click(screen.getByRole("button", { name: /unlinked.marina/ }));
    fireEvent.change(screen.getByLabelText("Пользователь для привязки"), { target: { value: "person-marina" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть карточку для привязки" }));
    await screen.findByLabelText("Логин");
    expect(screen.getByLabelText("Логин")).toHaveValue("unlinked.marina");
    expect(screen.queryByLabelText("Пароль для нового входа")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Причина изменения"), { target: { value: "Привязка профиля" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    await screen.findByText("Доступ сохранён");
    expect(writes[0].body).toMatchObject({ queue_ids: [7], group_ids: [10] });
  });
  it("keeps a late save result scoped to the original person", async () => {
    let resolve!: (response: Response) => void;
    const delayed = new Promise<Response>((done) => { resolve = done; });
    setup({ delayed });
    await fillAccount();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    fireEvent.click(screen.getByRole("button", { name: /Иван Петров/ }));
    await screen.findByRole("heading", { name: "Иван Петров" });
    resolve(json({ account: { user_login: "marina", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [] } }));
    await waitFor(() => expect(screen.queryByText("Доступ сохранён")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Иван Петров" })).toBeInTheDocument();
  });
  it("requires explicit account selection and separates inherited queues", async () => {
    const accounts = [{ user_login: "marina", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [10] }, { user_login: "marina.admin", actor_role: "admin", is_active: true, queue_ids: [], group_ids: [] }];
    setup({ accounts: { marina: accounts } });
    fireEvent.click(await screen.findByRole("button", { name: "Права и очереди" }));
    expect(screen.getByLabelText("Выберите учётную запись")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Выберите учётную запись"), { target: { value: "existing:marina" } });
    expect(screen.getByLabelText("ServiceDesk L1")).toBeChecked();
    expect(screen.getByLabelText("Вторая линия")).not.toBeChecked();
    expect(await screen.findByText(/Через группы: Вторая линия/)).toBeInTheDocument();
  });
  it("rejects degraded access data without offering an empty grant editor", async () => {
    setup({ degraded: true });
    expect(await screen.findByRole("alert")).toHaveTextContent("Настройки доступа временно недоступны");
    expect(screen.queryByRole("button", { name: "Сохранить доступ" })).not.toBeInTheDocument();
  });
  it("preserves the draft but disables save during a degraded summary refresh", async () => {
    const options = { degraded: false };
    const { client } = setup(options);
    await fillAccount();
    options.degraded = true;
    await client.invalidateQueries({ queryKey: ["admin-access-summary"] });
    expect(await screen.findByRole("alert")).toHaveTextContent("Настройки доступа временно недоступны");
    expect(screen.getByRole("button", { name: "Сохранить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("ServiceDesk L1")).toBeChecked();
  });
  it("keeps the draft and explains failed account refreshes", async () => {
    const options = { readError: false };
    const { client } = setup(options);
    await fillAccount();
    options.readError = true;
    await client.invalidateQueries({ queryKey: ["admin-user-accounts", "person-marina"] });
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось обновить учётные записи");
    expect(screen.getByRole("button", { name: "Сохранить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("ServiceDesk L1")).toBeChecked();
  });
  it("uses refreshed saved accounts when returning from another account selection", async () => {
    const { client, accounts } = setup();
    await fillAccount();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить доступ" }));
    await screen.findByText("Доступ сохранён");
    expect(screen.getByLabelText("Способ входа")).toHaveValue("existing:marina");
    accounts.marina = [{ user_login: "marina", actor_role: "auditor", is_active: false, queue_ids: [], group_ids: [] }];
    await client.invalidateQueries({ queryKey: ["admin-user-accounts", "person-marina"] });
    await screen.findByRole("option", { name: "marina · Вход отключён" });
    fireEvent.change(screen.getByLabelText("Способ входа"), { target: { value: "new" } });
    fireEvent.change(screen.getByLabelText("Способ входа"), { target: { value: "existing:marina" } });
    fireEvent.click(screen.getByRole("button", { name: "Учётная запись" }));
    expect(screen.getByLabelText("Роль")).toHaveValue("auditor");
    expect(screen.getByLabelText("Учётная запись активна")).not.toBeChecked();
  });
  it("freezes profile fields during a pending save", async () => {
    let resolve!: (response: Response) => void;
    const profileDelay = new Promise<Response>((done) => { resolve = done; });
    setup({ profileDelay });
    fireEvent.click(await screen.findByRole("button", { name: "Редактировать профиль" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить профиль" }));
    await screen.findByRole("button", { name: "Сохраняем…" });
    expect(screen.getByLabelText("Отображаемое имя")).toBeDisabled();
    resolve(json({ updated: true }));
    await screen.findByText("Профиль сохранён");
  });
  it("adopts authoritative account changes after returning from operations when clean", async () => {
    const initial = { user_login: "marina", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [] };
    const { client, accounts } = setup({ accounts: { marina: [initial] } });
    fireEvent.click(await screen.findByRole("button", { name: "Учётная запись" }));
    fireEvent.click(screen.getByRole("button", { name: "Дополнительные операции" }));
    accounts.marina = [{ ...initial, actor_role: "auditor", is_active: false }];
    await client.invalidateQueries({ queryKey: ["admin-user-accounts", "person-marina"] });
    fireEvent.click(screen.getByRole("button", { name: "Пользователи" }));
    await waitFor(() => expect(screen.getByLabelText("Учётная запись активна")).not.toBeChecked());
    expect(screen.getByLabelText("Роль")).toHaveValue("auditor");
  });
  it("blocks a stale dirty draft from overwriting an external disable until explicitly reloaded", async () => {
    const initial = { user_login: "marina", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [] };
    const { client, accounts, writes } = setup({ accounts: { marina: [initial] } });
    fireEvent.click(await screen.findByRole("button", { name: "Учётная запись" }));
    fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Причина изменения"), { target: { value: "Изменение роли" } });
    accounts.marina = [{ ...initial, is_active: false }];
    await client.invalidateQueries({ queryKey: ["admin-user-accounts", "person-marina"] });
    expect(await screen.findByRole("alert")).toHaveTextContent("Запись изменилась на сервере");
    expect(screen.getByLabelText("Роль")).toHaveValue("admin");
    expect(screen.getByRole("button", { name: "Сохранить доступ" })).toBeDisabled();
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Отменить черновик и загрузить актуальные данные" }));
    expect(screen.getByLabelText("Учётная запись активна")).not.toBeChecked();
    expect(screen.getByLabelText("Роль")).toHaveValue("support");
    expect(screen.getByRole("button", { name: "Сохранить доступ" })).toBeEnabled();
  });
  it("focuses a modal create form, restores focus on cancel, and opens a created profile", async () => {
    setup();
    const opener = await screen.findByRole("button", { name: "Добавить пользователя" });
    opener.focus(); fireEvent.click(opener);
    const dialog = screen.getByRole("dialog");
    expect(screen.getByLabelText("Отображаемое имя")).toHaveFocus();
    fireEvent(dialog, new Event("cancel", { bubbles: false, cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    fireEvent.click(opener);
    fireEvent.change(screen.getByLabelText("Отображаемое имя"), { target: { value: "Новый сотрудник" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать профиль" }));
    await screen.findByRole("heading", { name: "Новый сотрудник" });
    expect(await screen.findByLabelText("Логин")).toBeVisible();
  });
});
