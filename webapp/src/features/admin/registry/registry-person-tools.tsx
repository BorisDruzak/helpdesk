import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";

type Person = AdminRegistryPayload["people"][number];
type UiUser = NonNullable<AdminRegistryPayload["ui_users"]>[number];

type Props = {
  person: Person | null;
  people: Person[];
  uiUsers: UiUser[];
  bindings: AdminRegistryPayload["active_bindings"];
  selectedIds: string[];
  onToggleSelection: (id: string) => void;
  onEdit: (person: Person) => void;
  onIdentity: (person: Person) => void;
  onMerge: (person: Person) => void;
  onArchive: (person: Person) => void;
  onBind: (person: Person) => void;
  onLink: (person: Person) => void;
  onDisable: (user: UiUser) => void;
  onHistory: (person: Person) => void;
  onDevice: (deviceId: string) => void;
};

/** Rare operations for the already selected Users card; never a second people grid. */
export function RegistryPersonTools(props: Props) {
  const { person } = props;
  return <div className="space-y-4">
    {person ? <>
      <div className="rounded-lg border border-border p-4">
        <h3 className="font-semibold">{person.full_name ?? person.display_name}</h3>
        <p className="mt-1 text-sm text-slate-600">{[person.position, person.workplace_label, person.internal_extension, person.manager_name].filter(Boolean).join(" · ")}</p>
        {person.profile_completion && !person.profile_completion.complete ? <p className="mt-2 text-sm text-amber-700">Нужно заполнить профиль</p> : null}
        {person.profile_completion?.missing_fields.length ? <p className="text-sm text-slate-600">Не хватает: {person.profile_completion.missing_fields.map(field => field.label).join(", ")}</p> : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => props.onEdit(person)} size="sm" variant="outline">Править</Button>
          <Button onClick={() => props.onIdentity(person)} size="sm" variant="outline">Добавить идентичность</Button>
          <Button onClick={() => props.onBind(person)} size="sm" variant="outline">Привязать устройство</Button>
          <Button onClick={() => props.onHistory(person)} size="sm" variant="outline">История и устройства</Button>
          <Button onClick={() => props.onLink(person)} size="sm" variant="outline">Связать учётную запись</Button>
          <Button disabled={person.status === "archived"} onClick={() => props.onMerge(person)} size="sm" variant="outline">Слияние дублей</Button>
          <Button disabled={person.status === "archived"} onClick={() => props.onArchive(person)} size="sm" variant="outline">Архив</Button>
        </div>
        {props.uiUsers.filter(user => user.linked_person_id === person.person_id).map(user => <div className="mt-3 flex flex-wrap items-center gap-2 text-sm" key={user.user_login}>
          <span>{user.user_login}</span>
          {user.actor_role === "user" ? <Button disabled={!user.is_active} onClick={() => props.onDisable(user)} size="sm" variant="outline">Отключить вход {user.user_login}</Button> : <span className="text-slate-500">Статус входа настраивается на вкладке «Учётная запись».</span>}
        </div>)}
        <div className="mt-3 space-y-2">
          {props.bindings.filter(binding => binding.person_id === person.person_id).map(binding => <div className="flex flex-wrap items-center gap-2 text-sm" key={binding.binding_id}>
            <span>{binding.hostname ?? binding.device_id}</span>
            <Button onClick={() => props.onDevice(binding.device_id)} size="sm" variant="outline">Карточка устройства</Button>
          </div>)}
        </div>
      </div>
    </> : <p className="text-sm text-slate-500">Выберите карточку пользователя для операций с идентичностями, устройствами и архивом.</p>}
    <details className="rounded-lg border border-border p-3">
      <summary className="cursor-pointer text-sm font-semibold">Массовое назначение подразделения</summary>
      <p className="my-2 text-sm text-slate-500">Выберите участников. Изменения применяются только после предпросмотра и указания причины.</p>
      <div className="max-h-48 space-y-2 overflow-y-auto">
        {props.people.filter(item => item.status !== "archived").map(item => <label className="flex items-center gap-2 text-sm" key={item.person_id}>
          <input checked={props.selectedIds.includes(item.person_id)} onChange={() => props.onToggleSelection(item.person_id)} type="checkbox" />
          {item.full_name ?? item.display_name}
        </label>)}
      </div>
    </details>
  </div>;
}
