import { Archive, Edit3, Fingerprint, GitMerge, Link2, UserCheck, UserRoundPlus, UserX } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { formatDateTime, registryStatusLabel, statusTone, type RegistrySelection } from "./registry-utils";

type PersonRow = AdminRegistryPayload["people"][number];
type UiUserRow = NonNullable<AdminRegistryPayload["ui_users"]>[number];

type Props = {
  people: AdminRegistryPayload["people"];
  onAddIdentity: (person: PersonRow) => void;
  onArchive: (person: PersonRow) => void;
  onBindToDevice: (person: PersonRow) => void;
  onDisableUiUser: (uiUser: UiUserRow) => void;
  onEdit: (person: PersonRow) => void;
  onLinkUiUser: (person: PersonRow) => void;
  onMerge: (person: PersonRow) => void;
  onSelect: (selection: RegistrySelection) => void;
  onToggleSelection: (id: string) => void;
  onToggleVisibleSelection: (ids: string[]) => void;
  selectedIds: string[];
  uiUsers?: AdminRegistryPayload["ui_users"];
};

const peopleGridClass = "grid min-w-[1900px] grid-cols-[48px_190px_160px_150px_170px_190px_130px_210px_180px_160px_150px_120px_100px_100px_100px_120px_130px_300px] gap-3";

function personContextSummary(person: PersonRow): string {
  const parts = [
    person.position,
    person.workplace_label,
    person.internal_extension ? `доб. ${person.internal_extension}` : null,
    person.manager_name ? `рук. ${person.manager_name}` : null,
  ].filter(Boolean);
  return parts.join(" · ") || "Нет";
}

function ProfileCompletionCell({ person }: { person: PersonRow }) {
  const completion = person.profile_completion;
  if (!completion) {
    return <span className="text-slate-500">Нет данных</span>;
  }
  if (completion.complete) {
    return <Badge tone="success">Профиль заполнен</Badge>;
  }
  const missing = completion.missing_fields.map((field) => field.label).filter(Boolean).join(", ");
  return (
    <div className="space-y-1">
      <Badge tone="warning">Нужно заполнить профиль</Badge>
      {missing ? <p className="text-xs leading-5 text-slate-500">Не хватает: {missing}</p> : null}
    </div>
  );
}

export function RegistryPeopleTab({
  onAddIdentity,
  onArchive,
  onBindToDevice,
  onDisableUiUser,
  onEdit,
  onLinkUiUser,
  onMerge,
  onSelect,
  onToggleSelection,
  onToggleVisibleSelection,
  people,
  selectedIds,
  uiUsers = [],
}: Props) {
  const visibleIds = people.map((person) => person.person_id).filter(Boolean);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className={`${peopleGridClass} bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500`}>
        <input aria-label="Выбрать всех видимых пользователей" checked={allVisibleSelected} disabled={!visibleIds.length} onChange={() => onToggleVisibleSelection(visibleIds)} title="Выбрать или снять выбор со всех людей в текущем фильтре" type="checkbox" />
        <span>ФИО</span><span>Отображаемое имя</span><span>Логин</span><span>UI-аккаунт</span><span>Почта</span><span>Телефон</span><span>Контекст</span><span>Профиль</span><span>Подразделение</span><span>Локация</span><span>Статус</span><span>Основные ПК</span><span>Совместные ПК</span><span>Тикеты</span><span>Сессии</span><span>Последняя активность</span><span>Действия</span>
      </div>
      {people.length ? people.map((person) => {
        const linkedUiUsers = uiUsers.filter((user) => user.linked_person_id === person.person_id);
        return (
          <div className={`${peopleGridClass} border-t border-border px-4 py-3 text-sm`} key={person.person_id}>
            <input
              aria-label={`Выбрать пользователя ${person.display_name ?? person.full_name ?? person.person_id}`}
              checked={selectedIds.includes(person.person_id)}
              onChange={() => onToggleSelection(person.person_id)}
              type="checkbox"
            />
            <button className="text-left font-semibold text-slate-950" onClick={() => onSelect({ kind: "person", id: person.person_id })} type="button">{person.full_name ?? person.display_name}</button>
            <span className="text-slate-700">{person.display_name}</span>
            <span className="text-slate-700">{person.login ?? "Нет"}</span>
            <span className="break-all text-slate-700">{linkedUiUsers.length ? linkedUiUsers.map((user) => user.user_login).join(", ") : "Нет"}</span>
            <span className="break-all text-slate-700">{person.email ?? "Нет"}</span>
            <span className="text-slate-700">{person.phone ?? "Нет"}</span>
            <span className="break-words text-slate-700">{personContextSummary(person)}</span>
            <ProfileCompletionCell person={person} />
            <span className="text-slate-700">{person.department_name ?? "Нет"}</span>
            <span className="text-slate-700">{person.location_name ?? "Нет"}</span>
            <Badge tone={statusTone(person.status)}>{registryStatusLabel(person.status)}</Badge>
            <span>{person.primary_device_count ?? 0}</span>
            <span>{person.shared_device_count ?? 0}</span>
            <span>{person.active_ticket_count ?? 0}</span>
            <span>{person.active_session_count ?? 0}</span>
            <span>{formatDateTime(person.last_seen_at)}</span>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<UserCheck className="h-4 w-4" />} onClick={() => onSelect({ kind: "person", id: person.person_id })} size="sm" title="Открыть карточку пользователя и историю изменений" variant="outline">Карточка</Button>
              <Button leadingIcon={<Edit3 className="h-4 w-4" />} onClick={() => onEdit(person)} size="sm" title="Изменить ФИО, контакты и статус пользователя" variant="ghost">Править</Button>
              <Button leadingIcon={<Fingerprint className="h-4 w-4" />} onClick={() => onAddIdentity(person)} size="sm" title="Добавить идентичность: Windows-логин, UI-аккаунт, почту или телефон" variant="ghost">Идентичность</Button>
              <Button leadingIcon={<UserRoundPlus className="h-4 w-4" />} onClick={() => onLinkUiUser(person)} size="sm" title="Связать UI-аккаунт входа с этой карточкой человека" variant="ghost">UI-аккаунт</Button>
              <Button leadingIcon={<GitMerge className="h-4 w-4" />} onClick={() => onMerge(person)} size="sm" title="Объединить дубль пользователя через предпросмотр" variant="ghost">Слияние</Button>
              <Button leadingIcon={<Link2 className="h-4 w-4" />} onClick={() => onBindToDevice(person)} size="sm" title="Назначить пользователя основным владельцем устройства" variant="ghost">К устройству</Button>
              {linkedUiUsers.filter((user) => user.is_active && user.actor_role === "user").map((user) => (
                <Button
                  key={user.user_login}
                  leadingIcon={<UserX className="h-4 w-4" />}
                  onClick={() => onDisableUiUser(user)}
                  size="sm"
                  title={`Отключить вход для UI аккаунта ${user.user_login} без архивации карточки пользователя`}
                  variant="ghost"
                >
                  Отключить вход
                </Button>
              ))}
              <Button disabled={person.status === "archived"} leadingIcon={<Archive className="h-4 w-4" />} onClick={() => onArchive(person)} size="sm" title="Архивировать пользователя, отозвать активные привязки и account-сессии" variant="ghost">Архив</Button>
            </div>
          </div>
        );
      }) : (
        <div className="border-t border-border p-4">
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Пользователи не найдены.</p>
        </div>
      )}
    </div>
  );
}
