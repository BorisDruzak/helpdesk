import { Search, UserRound, Unlink } from "lucide-react";
import type { AdminRegistryPayload, AdminRegistryUiUser } from "../admin/api";
import { roleLabels } from "./model";

type Props = {
  registry: AdminRegistryPayload;
  query: string;
  onQueryChange: (query: string) => void;
  selection: string | null;
  onPersonSelect: (id: string) => void;
  onAccountSelect: (account: AdminRegistryUiUser) => void;
};

export function UsersList({ registry, query, onQueryChange, selection, onPersonSelect, onAccountSelect }: Props) {
  const needle = query.trim().toLocaleLowerCase("ru");
  const accounts = registry.ui_users ?? [];
  const people = registry.people.filter((person) => [person.display_name, person.full_name, person.email, person.phone, person.department_name,
    ...accounts.filter((account) => account.linked_person_id === person.person_id).map((account) => account.user_login), person.login,
  ].some((value) => value?.toLocaleLowerCase("ru").includes(needle)));
  const unlinked = accounts.filter((account) => !account.linked_person_id && account.user_login.toLocaleLowerCase("ru").includes(needle));
  const rowClass = (active: boolean) => `flex w-full items-start gap-3 border-l-[3px] px-4 py-3 text-left transition-colors ${active ? "border-brand-600 bg-brand-50" : "border-transparent hover:bg-slate-50"}`;
  return <aside aria-label="Список пользователей" className="min-w-0 overflow-hidden rounded-2xl border border-border bg-white">
    <div className="border-b border-border p-4">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-slate-900">Люди и учётные записи</h2><span className="text-xs text-slate-500">{people.length + unlinked.length}</span></div>
      <label className="relative block"><Search aria-hidden="true" className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input aria-label="Поиск пользователей" className="field-base h-10 w-full pl-9 pr-3 text-sm" placeholder="Имя, логин, отдел, почта" value={query} onChange={(event) => onQueryChange(event.target.value)} type="search" /></label>
    </div>
    <div className="max-h-[460px] overflow-y-auto">
      {people.map((person) => {
        const linked = accounts.filter((account) => account.linked_person_id === person.person_id);
        return <button key={person.person_id} className={rowClass(selection === person.person_id)} onClick={() => onPersonSelect(person.person_id)} type="button" aria-pressed={selection === person.person_id}>
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500"><UserRound className="h-4 w-4" /></span>
          <span className="min-w-0"><span className="block break-words text-sm font-semibold text-slate-900">{person.display_name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{person.department_name || person.email || "Подразделение не указано"}</span>
            <span className={`mt-1 block text-[11px] ${linked.length ? "text-brand-700" : "text-slate-400"}`}>{person.status === "archived" ? "В архиве · " : ""}{linked.length ? linked.map((account) => account.user_login).join(", ") : "Без учётной записи"}</span></span>
        </button>;
      })}
      {unlinked.length ? <p className="border-t border-border bg-slate-50 px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Без профиля пользователя</p> : null}
      {unlinked.map((account) => <button key={account.user_login} type="button" className={rowClass(selection === `login:${account.user_login}`)} onClick={() => onAccountSelect(account)}>
        <Unlink aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-amber-600" /><span className="min-w-0"><span className="block break-all text-sm font-semibold text-slate-900">{account.user_login}</span><span className="mt-1 block text-xs text-slate-500">{roleLabels[account.actor_role] || "Учётная запись"} · {account.is_active ? "Вход разрешён" : "Вход отключён"}</span></span>
      </button>)}
      {!people.length && !unlinked.length ? <p className="p-6 text-center text-sm text-slate-500">Ничего не найдено. Попробуйте имя или логин.</p> : null}
    </div>
  </aside>;
}
