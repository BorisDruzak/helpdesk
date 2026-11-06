import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Tabs } from "../../components/ui/tabs";
import type { AccessSummaryPayload } from "../access-control/api";
import type { AdminRegistryPayload } from "../admin/api";
import { AccountEditor } from "./account-editor";
import { fetchUserAccounts, type UserAccount } from "./api";
import { emptyAccount, fieldClass, labelClass, type Person } from "./model";
import { ProfilePanel } from "./profile-panel";

type Props = { person: Person; registry: AdminRegistryPayload; summary: AccessSummaryPayload; candidateLogin?: string; accessUnavailable?: boolean; initialTab?: string };

function LoadedUserCard({ person, registry, summary, candidateLogin, accounts, accessUnavailable, initialTab }: Props & { accounts: UserAccount[] }) {
  const [tab, setTab] = useState(initialTab ?? (candidateLogin ? "account" : "profile"));
  const [mode, setMode] = useState(() => candidateLogin ? `link:${candidateLogin}` : accounts.length === 1 ? `existing:${accounts[0].user_login}` : accounts.length ? "" : "new");
  const [success, setSuccess] = useState(false);
  const linking = mode.startsWith("link:");
  const selectedLogin = mode.slice(mode.indexOf(":") + 1);
  const candidate = useQuery({ queryKey: ["admin-user-accounts", person.person_id, selectedLogin], queryFn: () => fetchUserAccounts(person.person_id, selectedLogin), enabled: linking, retry: false });
  const snapshot = mode === "new" ? emptyAccount() : linking ? candidate.data?.[0] : accounts.find((account) => account.user_login === selectedLogin);
  const unlinked = (registry.ui_users ?? []).filter((account) => !account.linked_person_id);
  return <article aria-label="Карточка пользователя" className="min-w-0 overflow-hidden rounded-2xl border border-border bg-white">
    <header className="border-b border-border px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="break-words text-xl font-semibold tracking-tight text-slate-950">{person.display_name}</h2><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{accounts.length ? `${accounts.length} учётн. зап.` : "Без учётной записи"}</span></div>
      <p className="mt-1 text-sm text-slate-500">{[person.position, person.department_name].filter(Boolean).join(" · ") || person.email || "Профиль, вход и доступ в одном месте"}</p>
      <Tabs className="mt-4" items={[{ value: "profile", label: "Профиль" }, { value: "account", label: "Учётная запись" }, { value: "permissions", label: "Права и очереди" }]} value={tab} onValueChange={setTab} />
    </header>
    <div className="p-5">
      <div hidden={tab !== "profile"}><ProfilePanel person={person} registry={registry} /></div>
      <div hidden={tab === "profile"} className="space-y-4">
        {success ? <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">Доступ сохранён</p> : null}
        <label className={labelClass}>{accounts.length > 1 ? "Выберите учётную запись" : "Способ входа"}<select aria-label={accounts.length > 1 ? "Выберите учётную запись" : "Способ входа"} className={fieldClass} value={mode} onChange={(event) => { setMode(event.target.value); setSuccess(false); }}>
          {accounts.length > 1 ? <option value="">Выберите логин для редактирования</option> : null}
          {accounts.map((account) => <option key={account.user_login} value={`existing:${account.user_login}`}>{account.user_login} · {account.is_active ? "Вход разрешён" : "Вход отключён"}</option>)}
          <option value="new">Создать новый локальный вход</option>
          {unlinked.map((account) => <option key={account.user_login} value={`link:${account.user_login}`}>Привязать существующий: {account.user_login}</option>)}
          {candidateLogin && !unlinked.some((account) => account.user_login === candidateLogin) && mode === `link:${candidateLogin}` ? <option value={`link:${candidateLogin}`}>{candidateLogin}</option> : null}
        </select></label>
        {!mode ? <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">У пользователя несколько входов. Выберите нужную учётную запись, чтобы изменить её права.</p> : null}
        {linking && candidate.isLoading ? <p role="status" className="text-sm text-slate-500">Загружаем текущие назначения выбранного логина…</p> : null}
        {linking && candidate.isError ? <div role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{candidate.error.message}<Button className="ml-3" variant="outline" size="sm" onClick={() => void candidate.refetch()}>Повторить</Button></div> : null}
        {snapshot ? <AccountEditor key={`${person.person_id}:${mode}`} personId={person.person_id} initial={snapshot} isNew={mode === "new"} linking={linking} archived={person.status === "archived"} accessUnavailable={accessUnavailable || (linking && candidate.isError)} tab={tab} summary={summary} onDirty={() => setSuccess(false)} onSaved={(account) => { setMode(`existing:${account.user_login}`); setSuccess(true); }} /> : null}
      </div>
    </div>
  </article>;
}

export function UserCard(props: Props) {
  const query = useQuery({ queryKey: ["admin-user-accounts", props.person.person_id], queryFn: () => fetchUserAccounts(props.person.person_id), retry: false });
  if (query.data) return <><LoadedUserCard {...props} accounts={query.data} accessUnavailable={props.accessUnavailable || query.isError} />{query.isError ? <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Не удалось обновить учётные записи. Черновик сохранён; повторите загрузку перед сохранением.<Button variant="outline" size="sm" className="ml-2" onClick={() => void query.refetch()}>Повторить</Button></p> : null}</>;
  return <section className="rounded-2xl border border-border bg-white p-6" aria-label="Карточка пользователя"><h2 className="text-xl font-semibold">{props.person.display_name}</h2>{query.isError ? <div role="alert" className="mt-4 text-sm text-rose-700">{query.error.message}<Button className="mt-3 block" variant="outline" onClick={() => void query.refetch()}>Повторить загрузку</Button></div> : <p role="status" className="mt-4 text-sm text-slate-500">Загружаем учётные записи…</p>}</section>;
}
