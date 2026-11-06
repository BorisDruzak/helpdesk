export type UserAccount = {
  user_login: string;
  actor_role: string;
  is_active: boolean;
  queue_ids: number[];
  group_ids: number[];
};

export type UserAccountInput = UserAccount & { password?: string; reason: string };

function accountSnapshot(value: UserAccount): UserAccount {
  if (!value || typeof value.user_login !== "string" || typeof value.actor_role !== "string" || typeof value.is_active !== "boolean" || !Array.isArray(value.queue_ids) || !Array.isArray(value.group_ids) || ![...value.queue_ids, ...value.group_ids].every(Number.isInteger)) {
    throw new Error("Сервер вернул неполные данные учётной записи. Обновите страницу перед сохранением.");
  }
  return { user_login: value.user_login, actor_role: value.actor_role, is_active: value.is_active, queue_ids: value.queue_ids, group_ids: value.group_ids };
}

export async function createUserProfile(input: Record<string, unknown>): Promise<string> {
  const response = await fetch("/api/web/admin/registry/people", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.status !== "success") throw new Error(payload?.error ?? "Не удалось создать профиль пользователя.");
  if (!payload.data?.person?.person_id) throw new Error("Сервер не подтвердил новый профиль. Обновите список перед повторным созданием.");
  return payload.data.person.person_id as string;
}

async function request<T>(personId: string, input?: UserAccountInput, userLogin?: string): Promise<T> {
  const query = userLogin ? `?${new URLSearchParams({ user_login: userLogin })}` : "";
  const response = await fetch(`/api/web/admin/users/${encodeURIComponent(personId)}/account${query}`, {
    credentials: "same-origin",
    ...(input ? { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) } : {}),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.status !== "success" || !payload.data) {
    throw new Error(payload?.error ?? (input ? "Не удалось сохранить доступ. Повторите попытку." : "Не удалось загрузить учётные записи. Повторите попытку."));
  }
  return payload.data as T;
}

export async function fetchUserAccounts(personId: string, userLogin?: string): Promise<UserAccount[]> {
  const payload = await request<{ accounts: UserAccount[] }>(personId, undefined, userLogin);
  if (!Array.isArray(payload.accounts)) throw new Error("Сервер вернул неполные данные учётных записей.");
  return payload.accounts.map(accountSnapshot);
}

export async function saveUserAccount(personId: string, input: UserAccountInput): Promise<UserAccount> {
  const payload = await request<{ account: UserAccount }>(personId, input);
  if (!payload.account?.user_login) throw new Error("Сервер не подтвердил сохранение. Обновите данные перед повторной попыткой.");
  return accountSnapshot(payload.account);
}
