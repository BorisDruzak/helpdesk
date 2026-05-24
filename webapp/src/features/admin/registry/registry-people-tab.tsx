import { Edit3, Fingerprint, GitMerge, Link2, UserCheck } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { formatDateTime, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  people: AdminRegistryPayload["people"];
  onAddIdentity: (person: AdminRegistryPayload["people"][number]) => void;
  onBindToDevice: (person: AdminRegistryPayload["people"][number]) => void;
  onEdit: (person: AdminRegistryPayload["people"][number]) => void;
  onMerge: (person: AdminRegistryPayload["people"][number]) => void;
  onSelect: (selection: RegistrySelection) => void;
  onToggleSelection: (id: string) => void;
  onToggleVisibleSelection: (ids: string[]) => void;
  selectedIds: string[];
};

export function RegistryPeopleTab({ onAddIdentity, onBindToDevice, onEdit, onMerge, onSelect, onToggleSelection, onToggleVisibleSelection, people, selectedIds }: Props) {
  const visibleIds = people.map((person) => person.person_id).filter(Boolean);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div className="grid min-w-[1380px] grid-cols-[48px_190px_160px_150px_190px_130px_160px_150px_120px_100px_100px_100px_120px_130px_260px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
        <input aria-label="Select visible people" checked={allVisibleSelected} disabled={!visibleIds.length} onChange={() => onToggleVisibleSelection(visibleIds)} type="checkbox" />
        <span>ФИО</span><span>Display</span><span>Login</span><span>Email</span><span>Phone</span><span>Department</span><span>Location</span><span>Status</span><span>Primary</span><span>Shared</span><span>Tickets</span><span>Sessions</span><span>Last seen</span><span>Actions</span>
      </div>
      {people.length ? people.map((person) => (
        <div className="grid min-w-[1380px] grid-cols-[48px_190px_160px_150px_190px_130px_160px_150px_120px_100px_100px_100px_120px_130px_260px] gap-3 border-t border-border px-4 py-3 text-sm" key={person.person_id}>
          <input
            aria-label={`Select person ${person.display_name ?? person.full_name ?? person.person_id}`}
            checked={selectedIds.includes(person.person_id)}
            onChange={() => onToggleSelection(person.person_id)}
            type="checkbox"
          />
          <button className="text-left font-semibold text-slate-950" onClick={() => onSelect({ kind: "person", id: person.person_id })} type="button">{person.full_name ?? person.display_name}</button>
          <span className="text-slate-700">{person.display_name}</span>
          <span className="text-slate-700">{person.login ?? "Нет"}</span>
          <span className="break-all text-slate-700">{person.email ?? "Нет"}</span>
          <span className="text-slate-700">{person.phone ?? "Нет"}</span>
          <span className="text-slate-700">{person.department_name ?? "Нет"}</span>
          <span className="text-slate-700">{person.location_name ?? "Нет"}</span>
          <Badge tone={statusTone(person.status)}>{person.status}</Badge>
          <span>{person.primary_device_count ?? 0}</span>
          <span>{person.shared_device_count ?? 0}</span>
          <span>{person.active_ticket_count ?? 0}</span>
          <span>{person.active_session_count ?? 0}</span>
          <span>{formatDateTime(person.last_seen_at)}</span>
          <div className="flex flex-wrap gap-2">
            <Button leadingIcon={<UserCheck className="h-4 w-4" />} onClick={() => onSelect({ kind: "person", id: person.person_id })} size="sm" variant="outline">Карточка</Button>
            <Button leadingIcon={<Edit3 className="h-4 w-4" />} onClick={() => onEdit(person)} size="sm" variant="ghost">Edit</Button>
            <Button leadingIcon={<Fingerprint className="h-4 w-4" />} onClick={() => onAddIdentity(person)} size="sm" variant="ghost">Identity</Button>
            <Button leadingIcon={<GitMerge className="h-4 w-4" />} onClick={() => onMerge(person)} size="sm" variant="ghost">Merge</Button>
            <Button leadingIcon={<Link2 className="h-4 w-4" />} onClick={() => onBindToDevice(person)} size="sm" variant="ghost">К устройству</Button>
          </div>
        </div>
      )) : (
        <div className="border-t border-border p-4">
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Пользователи не найдены.</p>
        </div>
      )}
    </div>
  );
}
