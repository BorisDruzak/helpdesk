import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { updateAdminRegistryPerson, type AdminRegistryPayload } from "../admin/api";
import { registryStatusLabel } from "../admin/registry/registry-utils";
import { fieldClass, labelClass, type Person } from "./model";
import { createUserProfile } from "./api";

export function PersonProfileForm({ person, registry, onClose, onSaved, onBusyChange }: { person?: Person; registry: AdminRegistryPayload; onClose: () => void; onSaved?: (personId: string) => void; onBusyChange?: (busy: boolean) => void }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState({ display_name: person?.display_name ?? "", full_name: person?.full_name ?? "", email: person?.email ?? "", phone: person?.phone ?? "", position: person?.position ?? "", workplace_label: person?.workplace_label ?? "", internal_extension: person?.internal_extension ?? "", manager_person_id: person?.manager_person_id ?? "", department_id: person?.department_id ?? "", location_id: person?.location_id ?? "" });
  const mutation = useMutation({
    mutationFn: async () => {
      const payload = { ...draft, manager_person_id: draft.manager_person_id || null, department_id: draft.department_id || null, location_id: draft.location_id || null };
      if (!person) return createUserProfile({ ...payload, status: "active", reason: "Создание профиля администратором" });
      await updateAdminRegistryPerson(person.person_id, payload);
      return person.person_id;
    },
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["admin-registry"] }); },
  });
  const change = (field: keyof typeof draft, value: string) => setDraft((current) => ({ ...current, [field]: value }));
  useEffect(() => { onBusyChange?.(mutation.isPending); }, [mutation.isPending, onBusyChange]);
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); mutation.mutate(undefined, { onSuccess: (personId) => { onSaved?.(personId); onClose(); } }); }}>
    <fieldset disabled={mutation.isPending} className="grid gap-3 sm:grid-cols-2">
      {([{ key: "display_name", label: "Отображаемое имя", required: true }, { key: "full_name", label: "Полное имя" }, { key: "email", label: "Электронная почта" }, { key: "phone", label: "Телефон" }, { key: "position", label: "Должность" }, { key: "workplace_label", label: "Рабочее место" }, { key: "internal_extension", label: "Внутренний номер" }] as const).map((field) => <label className={labelClass} key={field.key}>{field.label}<input className={fieldClass} value={draft[field.key]} onChange={(event) => change(field.key, event.target.value)} required={field.key === "display_name"} type={field.key === "email" ? "email" : "text"} /></label>)}
      <label className={labelClass}>Руководитель<select className={fieldClass} value={draft.manager_person_id} onChange={(event) => change("manager_person_id", event.target.value)}><option value="">Не указан</option>{registry.people.filter((item) => item.person_id !== person?.person_id).map((item) => <option key={item.person_id} value={item.person_id}>{item.display_name}</option>)}</select></label>
      <label className={labelClass}>Подразделение<select className={fieldClass} value={draft.department_id} onChange={(event) => change("department_id", event.target.value)}><option value="">Не указано</option>{registry.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className={labelClass}>Локация<select className={fieldClass} value={draft.location_id} onChange={(event) => change("location_id", event.target.value)}><option value="">Не указана</option>{registry.locations.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
    </fieldset>
    {mutation.isError ? <p className="text-sm text-rose-700" role="alert">{mutation.error.message}</p> : null}
    <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>Отмена</Button><Button type="submit" disabled={mutation.isPending || !draft.display_name.trim()}>{mutation.isPending ? "Сохраняем…" : person ? "Сохранить профиль" : "Создать профиль"}</Button></div>
  </form>;
}

export function ProfilePanel({ person, registry }: { person: Person; registry: AdminRegistryPayload }) {
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  if (editing) return <PersonProfileForm person={person} registry={registry} onClose={() => setEditing(false)} onSaved={() => setSaved(true)} />;
  const rows = [["Полное имя", person.full_name], ["Подразделение", person.department_name], ["Должность", person.position], ["Электронная почта", person.email], ["Телефон", person.phone], ["Местоположение", [person.location_name, person.workplace_label].filter(Boolean).join(" · ")], ["Руководитель", person.manager_name], ["Статус профиля", registryStatusLabel(person.status)]];
  return <div className="space-y-4">
    {saved ? <p role="status" className="text-sm text-emerald-700">Профиль сохранён</p> : null}
    <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">{rows.map(([label, value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-900">{value || "Не указано"}</dd></div>)}</dl>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"><p className="text-xs text-slate-500">{person.primary_device_count ?? 0} личных устройств · {person.active_ticket_count ?? 0} активных заявок</p><Button variant="outline" size="sm" onClick={() => setEditing(true)}>Редактировать профиль</Button></div>
  </div>;
}
