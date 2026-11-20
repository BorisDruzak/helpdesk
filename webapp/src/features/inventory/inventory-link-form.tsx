import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "../../components/ui/button";

type InventoryEmployee = {
  inventory_person_id: string;
  full_name: string;
  department: string;
  has_agent: boolean;
};

export type LinkableProfile = {
  name: string;
  department?: string | null;
  logins: string[];
};

async function requestInventoryLink<T>(url: string, fallback: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...init });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.status !== "success" || !payload.data) {
    throw new Error(typeof payload?.error === "string" ? payload.error : fallback);
  }
  return payload.data as T;
}

type Props = {
  personId: string;
  profile: LinkableProfile;
  onCancel: () => void;
  onConfirmed: () => Promise<void>;
};

export function InventoryLinkForm({ personId, profile, onCancel, onConfirmed }: Props) {
  const [search, setSearch] = useState(profile.name);
  const [query, setQuery] = useState(profile.name.trim());
  const [selected, setSelected] = useState("");
  const [login, setLogin] = useState(profile.logins.length === 1 ? profile.logins[0] : "");
  const [reason, setReason] = useState("");
  const matches = useQuery({
    queryKey: ["admin-inventory-link-people", query],
    queryFn: ({ signal }) => requestInventoryLink<{ people: InventoryEmployee[]; refine: boolean }>(
      "/api/web/admin/registry/inventory-people/search",
      "Не удалось найти сотрудника в инвентаризации.",
      { signal, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) },
    ),
    enabled: Boolean(query),
    gcTime: 0,
    retry: false,
  });
  const confirmation = useMutation({
    mutationFn: () => requestInventoryLink(
      `/api/web/admin/registry/people/${encodeURIComponent(personId)}/inventory-link`,
      "Не удалось подтвердить связь.",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inventory_person_id: selected, user_login: login, reason: reason.trim() }),
      },
    ),
    onSuccess: onConfirmed,
  });
  const people = matches.data?.people ?? [];
  const canConfirm = !matches.isError && !matches.isFetching && search.trim() === query
    && people.some((person) => person.inventory_person_id === selected)
    && profile.logins.includes(login) && Boolean(reason.trim());
  return <div className="mt-3 space-y-3 rounded-lg border border-border p-3 text-sm">
    <p>Сверьте ФИО и отдел с карточкой сотрудника в инвентаризации.</p>
    <p className="font-medium">{[profile.name, profile.department].filter(Boolean).join(" · ")}</p>
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
      event.preventDefault();
      setSelected("");
      if (search.trim() === query) void matches.refetch();
      else setQuery(search.trim());
    }}>
      <label className="grid min-w-0 flex-1 gap-1">Имя или фамилия в инвентаризации
        <input className="field-base h-9 px-2" value={search} maxLength={120} required
          disabled={confirmation.isPending}
          onChange={(event) => { setSearch(event.target.value); setSelected(""); }} />
      </label>
      <Button type="submit" variant="outline" size="sm" disabled={!search.trim() || matches.isFetching || confirmation.isPending}>Найти</Button>
    </form>
    {matches.isFetching ? <p role="status">Ищем сотрудника…</p> : null}
    {matches.isError ? <p role="alert" className="text-rose-700">{matches.error.message}</p> : null}
    {matches.data && !people.length ? <p>Карточка сотрудника с подтверждаемой связью не найдена. Проверьте имя в инвентаризации.</p> : null}
    {matches.data?.refine ? <p>Уточните ФИО, если нужной карточки нет в результатах.</p> : null}
    <form className="space-y-3" onSubmit={(event) => {
      event.preventDefault();
      if (canConfirm && !confirmation.isPending) confirmation.mutate();
    }}>
      <fieldset className="space-y-3" disabled={confirmation.isPending}>
        {people.length ? <fieldset className="space-y-1">
          <legend className="font-medium">Карточка сотрудника в инвентаризации</legend>
          {people.map((person) => <label className="flex items-start gap-2 rounded-md border border-border p-2" key={person.inventory_person_id}>
            <input type="radio" name="inventory-employee" className="mt-1" checked={selected === person.inventory_person_id}
              onChange={() => setSelected(person.inventory_person_id)} />
            <span className="min-w-0 break-words">
              <span className="font-medium">{person.full_name}</span>{" · "}{person.department || "Отдел не указан"}
              {person.has_agent ? <span className="block">Есть компьютер с подтверждённым агентом</span> : null}
              {people.some((other) => other !== person && other.full_name === person.full_name && other.department === person.department)
                ? <span className="block">ID карточки {person.inventory_person_id}</span> : null}
            </span>
          </label>)}
        </fieldset> : null}
        {profile.logins.length > 1 ? <label className="grid gap-1">Логин Helpdesk
          <select className="field-base h-9 px-2" value={login} onChange={(event) => setLogin(event.target.value)} required>
            <option value="">Выберите логин</option>
            {profile.logins.map((option) => <option key={option}>{option}</option>)}
          </select>
        </label> : <p>Логин Helpdesk <strong>{profile.logins[0]}</strong></p>}
        <label className="grid gap-1">Причина подтверждения
          <textarea className="field-base min-h-16 p-2" value={reason} maxLength={500} required
            onChange={(event) => setReason(event.target.value)} />
        </label>
      </fieldset>
      {confirmation.isError ? <p role="alert" className="text-rose-700">{confirmation.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={confirmation.isPending}>Отмена</Button>
        <Button type="submit" size="sm" disabled={!canConfirm || confirmation.isPending}>
          {confirmation.isPending ? "Подтверждаем…" : "Подтвердить связь"}
        </Button>
      </div>
    </form>
  </div>;
}
