import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, UsersRound } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Tabs } from "../../components/ui/tabs";
import { GroupsAccessPanel } from "../../features/access-control/access-groups";
import { AccessAuditTab, PermissionCatalogTab, RolesPermissionMatrix } from "../../features/access-control/access-reference";
import { fetchAccessAudit, fetchAccessCatalog, fetchAccessSummary, type AccessSummaryPayload } from "../../features/access-control/api";
import { fetchAdminRegistry, type AdminRegistryUiUser } from "../../features/admin/api";
import { CreatePersonDialog } from "../../features/users/create-person-dialog";
import { UnlinkedAccount } from "../../features/users/unlinked-account";
import { UserCard } from "../../features/users/user-card";
import { UsersList } from "../../features/users/users-list";
import { roleLabels } from "../../features/users/model";

type Props = { renderOperations?: (personId: string | null) => ReactNode };
const workspaceTabs = [{ value: "people", label: "Пользователи" }, { value: "groups", label: "Группы доступа" }, { value: "reference", label: "Роли и разрешения" }, { value: "audit", label: "Журнал изменений" }, { value: "operations", label: "Дополнительные операции" }];
async function fetchUsersAccessSummary() {
  const data = await fetchAccessSummary();
  if (data.notes.includes("DB-backed users/queues are temporarily unavailable.")) {
    throw new Error("Настройки доступа временно недоступны. Повторите загрузку перед изменением ролей, очередей или групп.");
  }
  return data;
}

export function AdminUsersPage({ renderOperations }: Props) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [create, setCreate] = useState(false);
  const [candidateLogin, setCandidateLogin] = useState<string>();
  const [initialCardTab, setInitialCardTab] = useState<string>();
  const registry = useQuery({ queryKey: ["admin-registry"], queryFn: fetchAdminRegistry, retry: false });
  const summary = useQuery({ queryKey: ["admin-access-summary"], queryFn: fetchUsersAccessSummary, retry: false });
  const catalog = useQuery({ queryKey: ["admin-access-catalog"], queryFn: fetchAccessCatalog, retry: false });
  const rawTab = params.get("tab") ?? "people";
  const tab = rawTab === "access" ? "groups" : workspaceTabs.some((item) => item.value === rawTab) ? rawTab : "people";
  const audit = useQuery({ queryKey: ["admin-access-audit"], queryFn: fetchAccessAudit, retry: false, enabled: tab === "audit" });
  const selectedLogin = params.get("login");
  const personId = params.get("person") ?? params.get("person_id") ?? (selectedLogin ? null : registry.data?.people[0]?.person_id ?? null);
  const person = registry.data?.people.find((item) => item.person_id === personId);
  const unlinkedAccount = registry.data?.ui_users?.find((item) => item.user_login === selectedLogin && !item.linked_person_id);
  const selectPerson = (id: string, login?: string, cardTab?: string) => {
    setCandidateLogin(login);
    setInitialCardTab(cardTab);
    setParams((current) => { const next = new URLSearchParams(current); next.set("person", id); next.delete("person_id"); next.delete("login"); next.set("tab", "people"); return next; }, { replace: true });
  };
  const selectAccount = (account: AdminRegistryUiUser) => { setCandidateLogin(undefined); setParams((current) => { const next = new URLSearchParams(current); next.delete("person"); next.delete("person_id"); next.set("login", account.user_login); next.set("tab", "people"); return next; }, { replace: true }); };
  const refresh = () => Promise.all(["admin-registry", "admin-access-summary", "admin-access-catalog", "admin-user-accounts", "admin-access-effective", "admin-access-audit"].map((key) => client.invalidateQueries({ queryKey: [key] })));
  if (!registry.data || !summary.data || !catalog.data) {
    const error = registry.error || summary.error || catalog.error;
    return <section className="rounded-2xl border border-border bg-white p-8"><h1 className="text-2xl font-semibold">Пользователи</h1>{error ? <><p role="alert" className="mt-4 text-sm text-rose-700">{error.message}</p><Button className="mt-4" onClick={() => void refresh()} variant="outline">Повторить загрузку</Button></> : <p role="status" className="mt-4 text-sm text-slate-500">Загружаем профили и настройки доступа…</p>}</section>;
  }
  const localizedCatalog = { ...catalog.data, roles: catalog.data.roles.map((role) => ({ ...role, label: roleLabels[role.code] || role.label })) };
  return <section className="min-w-0 space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3"><span className="hidden rounded-xl bg-brand-50 p-2.5 text-brand-700 sm:block"><UsersRound aria-hidden="true" className="h-5 w-5" /></span><div><h1 className="text-2xl font-semibold tracking-tight text-slate-950">Пользователи</h1><p className="mt-1 text-sm text-slate-500">Профили, учётные записи и доступ сотрудников</p></div></div>
      <div className="flex gap-2"><Button size="sm" variant="outline" leadingIcon={<RefreshCw className="h-4 w-4" />} onClick={() => void refresh()}>Обновить</Button><Button size="sm" leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setCreate(true)}>Добавить пользователя</Button></div>
    </header>
    <Tabs aria-label="Разделы пользователей" value={tab} items={workspaceTabs} onValueChange={(value) => setParams((current) => { const next = new URLSearchParams(current); next.set("tab", value); return next; }, { replace: true })} />
    {registry.isError || summary.isError || catalog.isError ? <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{summary.isError ? summary.error.message : "Не удалось обновить данные. Показаны ранее загруженные значения, черновики сохранены."}<Button className="ml-2" size="sm" variant="outline" onClick={() => void refresh()}>Повторить</Button></p> : null}
    <div hidden={tab !== "people"} className="grid items-start gap-4 lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
      <UsersList registry={registry.data} query={query} onQueryChange={setQuery} selection={selectedLogin ? `login:${selectedLogin}` : personId} onPersonSelect={(id) => selectPerson(id)} onAccountSelect={selectAccount} />
      {unlinkedAccount ? <UnlinkedAccount key={unlinkedAccount.user_login} account={unlinkedAccount} registry={registry.data} onLink={(id, login) => { setQuery(""); selectPerson(id, login); }} onCreate={() => setCreate(true)} /> : person ? <UserCard key={`${person.person_id}:${candidateLogin ?? ""}`} person={person} registry={registry.data} summary={summary.data} candidateLogin={candidateLogin} initialTab={initialCardTab} accessUnavailable={summary.isError || catalog.isError || registry.isError} /> : <p className="rounded-2xl border border-dashed border-border p-8 text-sm text-slate-500">Выберите пользователя в списке или создайте профиль.</p>}
    </div>
    {tab === "groups" && !summary.isError ? <GroupsAccessPanel accessGroups={summary.data.access_groups} catalog={localizedCatalog} queues={summary.data.queues} users={summary.data.users} onGroupChange={(group) => { client.setQueryData<AccessSummaryPayload>(["admin-access-summary"], (current) => current ? { ...current, access_groups: [...current.access_groups.filter((item) => item.group_id !== group.group_id), group] } : current); void refresh(); }} /> : null}
    {tab === "reference" ? <div className="space-y-5"><RolesPermissionMatrix catalog={localizedCatalog} /><PermissionCatalogTab catalog={localizedCatalog} /></div> : null}
    {tab === "audit" ? <AccessAuditTab audit={audit.data} auditError={audit.error} auditLoading={audit.isLoading} /> : null}
    {tab === "operations" ? renderOperations?.(personId) ?? <p className="rounded-xl bg-white p-5 text-sm text-slate-500">Выберите пользователя для дополнительных операций.</p> : null}
    {create ? <CreatePersonDialog registry={registry.data} onClose={() => setCreate(false)} onSaved={(id) => { setQuery(""); selectPerson(id, unlinkedAccount?.user_login, "account"); }} /> : null}
  </section>;
}
