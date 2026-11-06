import { useState } from "react";
import { Unlink } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { AdminRegistryPayload, AdminRegistryUiUser } from "../admin/api";
import { fieldClass, labelClass, roleLabels } from "./model";

export function UnlinkedAccount({ account, registry, onLink, onCreate }: { account: AdminRegistryUiUser; registry: AdminRegistryPayload; onLink: (personId: string, login: string) => void; onCreate: () => void }) {
  const [personId, setPersonId] = useState("");
  const [query, setQuery] = useState("");
  const people = registry.people.filter((person) => person.status !== "archived" && `${person.display_name} ${person.email ?? ""} ${person.department_name ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="min-w-0 rounded-2xl border border-border bg-white p-6">
    <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-700"><Unlink aria-hidden="true" className="h-5 w-5" /></div>
    <h2 className="break-all text-xl font-semibold text-slate-950">{account.user_login}</h2>
    <p className="mt-2 text-sm text-slate-500">{roleLabels[account.actor_role] || "Учётная запись"} · {account.is_active ? "Вход разрешён" : "Вход отключён"}</p>
    <p className="mt-5 max-w-xl text-sm leading-6 text-slate-600">У этого входа пока нет профиля пользователя. Найдите человека по имени, чтобы привязать логин и проверить его роль, очереди и группы в одной карточке.</p>
    <div className="mt-5 max-w-lg space-y-4">
      <label className={labelClass}>Найти профиль<input className={fieldClass} placeholder="Имя, отдел или почта" value={query} onChange={(event) => { setQuery(event.target.value); setPersonId(""); }} type="search" /></label>
      <label className={labelClass}>Пользователь для привязки<select className={fieldClass} value={personId} onChange={(event) => setPersonId(event.target.value)}><option value="">Выберите пользователя по имени</option>{people.map((person) => <option key={person.person_id} value={person.person_id}>{person.display_name}{person.department_name ? ` · ${person.department_name}` : ""}</option>)}</select></label>
      <Button onClick={() => onLink(personId, account.user_login)} disabled={!personId}>Открыть карточку для привязки</Button>
      <div className="border-t border-border pt-4"><p className="mb-2 text-xs text-slate-500">Если человека ещё нет в списке, сначала создайте его профиль.</p><Button variant="outline" onClick={onCreate}>Создать профиль</Button></div>
    </div>
  </section>;
}
