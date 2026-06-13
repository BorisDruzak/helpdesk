import { Archive, Eye, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type {
  AdminRegistryAudienceGroup,
  AdminRegistryAudienceGroupMember,
  AdminRegistryAudienceMemberType,
  AdminRegistryAudiencePreview,
  AdminRegistryPayload,
} from "../api";
import { statusTone } from "./registry-utils";

type Props = {
  busy?: boolean;
  groups: AdminRegistryAudienceGroup[];
  members: AdminRegistryAudienceGroupMember[];
  preview: AdminRegistryAudiencePreview | null;
  registry: AdminRegistryPayload;
  selectedGroupId: string | null;
  onArchive: (group: AdminRegistryAudienceGroup, reason: string) => void;
  onCreate: (payload: { code: string; name: string; description: string; reason: string }) => void;
  onPreviewMembers: (groupId: string, members: AdminRegistryAudienceGroupMember[]) => Promise<void>;
  onSaveMembers: (groupId: string, members: AdminRegistryAudienceGroupMember[], reason: string) => void;
  onSelectGroup: (groupId: string) => void;
  onUpdate: (groupId: string, payload: { code: string; name: string; description: string; reason: string }) => void;
};

const memberTypeLabels: Record<AdminRegistryAudienceMemberType, string> = {
  person: "Пользователь",
  department: "Подразделение",
  department_tree: "Подразделение и дочерние",
  location: "Локация",
  access_group: "Группа доступа",
  role: "Роль",
  service: "Сервис",
};

const memberTypes: AdminRegistryAudienceMemberType[] = [
  "person",
  "department_tree",
  "department",
  "location",
  "role",
  "service",
];

function memberLabel(member: AdminRegistryAudienceGroupMember, registry: AdminRegistryPayload): string {
  if (member.member_type === "person") {
    return registry.people.find((person) => person.person_id === member.member_id)?.display_name ?? member.member_id;
  }
  if (member.member_type === "department" || member.member_type === "department_tree") {
    return registry.departments.find((department) => (department.department_id ?? department.id) === member.member_id)?.name ?? member.member_id;
  }
  if (member.member_type === "location") {
    return registry.locations.find((location) => (location.location_id ?? location.id) === member.member_id)?.display_name ?? member.member_id;
  }
  if (member.member_type === "service") {
    return registry.services.find((service) => service.id === member.member_id)?.name ?? member.member_id;
  }
  return member.member_id;
}

function normalizeMembers(members: AdminRegistryAudienceGroupMember[]): AdminRegistryAudienceGroupMember[] {
  const byKey = new Map<string, AdminRegistryAudienceGroupMember>();
  for (const member of members) {
    const includeChildren = member.member_type === "department_tree" || Boolean(member.include_children);
    byKey.set(`${member.member_type}:${member.member_id}:${includeChildren}`, {
      member_type: member.member_type,
      member_id: member.member_id,
      include_children: includeChildren,
      source: member.source ?? "manual",
      metadata_json: member.metadata_json ?? {},
    });
  }
  return Array.from(byKey.values()).sort((left, right) =>
    `${left.member_type}:${left.member_id}`.localeCompare(`${right.member_type}:${right.member_id}`)
  );
}

export function RegistryAudienceGroupsTab({
  busy,
  groups,
  members,
  onArchive,
  onCreate,
  onPreviewMembers,
  onSaveMembers,
  onSelectGroup,
  onUpdate,
  preview,
  registry,
  selectedGroupId,
}: Props) {
  const selectedGroup = groups.find((group) => group.audience_group_id === selectedGroupId) ?? null;
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [groupReason, setGroupReason] = useState("");
  const [memberDraft, setMemberDraft] = useState<AdminRegistryAudienceGroupMember[]>([]);
  const [memberType, setMemberType] = useState<AdminRegistryAudienceMemberType>("person");
  const [memberId, setMemberId] = useState("");
  const [memberQuery, setMemberQuery] = useState("");
  const [memberReason, setMemberReason] = useState("");

  useEffect(() => {
    setCode(selectedGroup?.code ?? "");
    setName(selectedGroup?.name ?? "");
    setDescription(selectedGroup?.description ?? "");
    setGroupReason("");
  }, [selectedGroup]);

  useEffect(() => {
    setMemberDraft([]);
    setMemberReason("");
    setMemberType("person");
    setMemberId("");
    setMemberQuery("");
  }, [selectedGroupId]);

  useEffect(() => {
    if (!members.length) {
      return;
    }
    setMemberDraft((current) => current.length ? current : normalizeMembers(members));
  }, [members]);

  const targetOptions = useMemo(() => {
    const normalized = memberQuery.trim().toLowerCase();
    if (memberType === "person") {
      return registry.people
        .filter((person) => person.status === "active")
        .filter((person) => !normalized || `${person.display_name} ${person.login ?? ""} ${person.email ?? ""}`.toLowerCase().includes(normalized))
        .map((person) => ({ id: person.person_id, label: `${person.display_name}${person.login ? ` · ${person.login}` : ""}` }));
    }
    if (memberType === "department" || memberType === "department_tree") {
      return registry.departments
        .filter((department) => department.status === "active")
        .filter((department) => !normalized || `${department.code ?? ""} ${department.name}`.toLowerCase().includes(normalized))
        .map((department) => ({ id: department.department_id ?? department.id, label: `${department.code ? `${department.code} · ` : ""}${department.name}` }));
    }
    if (memberType === "location") {
      return registry.locations
        .filter((location) => location.status === "active")
        .filter((location) => !normalized || `${location.display_name} ${location.building ?? ""} ${location.room ?? ""}`.toLowerCase().includes(normalized))
        .map((location) => ({ id: location.location_id ?? location.id, label: location.display_name }));
    }
    if (memberType === "role") {
      return ["user", "support", "admin", "auditor"]
        .filter((role) => !normalized || role.includes(normalized))
        .map((role) => ({ id: role, label: role }));
    }
    if (memberType === "service") {
      return registry.services
        .filter((service) => !normalized || `${service.code ?? ""} ${service.name}`.toLowerCase().includes(normalized))
        .map((service) => ({ id: service.code ?? service.id, label: `${service.code ? `${service.code} · ` : ""}${service.name}` }));
    }
    return [];
  }, [memberQuery, memberType, registry.departments, registry.locations, registry.people, registry.services]);

  const resetCreate = () => {
    setCreating(false);
    setCode(selectedGroup?.code ?? "");
    setName(selectedGroup?.name ?? "");
    setDescription(selectedGroup?.description ?? "");
    setGroupReason("");
  };

  const addMember = () => {
    if (!memberId) {
      return;
    }
    setMemberDraft((current) => normalizeMembers([
      ...current,
      {
        member_type: memberType,
        member_id: memberId,
        include_children: memberType === "department_tree",
        source: "manual",
        metadata_json: {},
      },
    ]));
    setMemberId("");
  };

  const activeFormIsCreate = creating || !selectedGroup;

  return (
    <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-slate-950">Аудитории</p>
          <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)} size="sm">Создать</Button>
        </div>
        <div className="space-y-2">
          {groups.length ? groups.map((group) => (
            <button
              className={`w-full rounded-lg border px-3 py-3 text-left text-sm transition-colors ${group.audience_group_id === selectedGroupId ? "border-brand-300 bg-brand-50" : "border-border bg-white hover:bg-slate-50"}`}
              key={group.audience_group_id}
              onClick={() => {
                setCreating(false);
                onSelectGroup(group.audience_group_id);
              }}
              type="button"
            >
              <span className="font-semibold text-slate-950">{group.name}</span>
              <span className="mt-1 block text-xs text-slate-500">{group.code}</span>
              <Badge className="mt-2" tone={statusTone(group.status)}>{group.status}</Badge>
            </button>
          )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Аудитории ещё не созданы.</p>}
        </div>
      </section>

      <section className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{activeFormIsCreate ? "Создать аудиторию" : "Параметры аудитории"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                Код
                <Input className="mt-2" onChange={(event) => setCode(event.target.value)} value={code} />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Название
                <Input className="mt-2" onChange={(event) => setName(event.target.value)} value={name} />
              </label>
            </div>
            <label className="block text-sm font-medium text-slate-700">
              Описание
              <Input className="mt-2" onChange={(event) => setDescription(event.target.value)} value={description} />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Причина
              <Input className="mt-2" onChange={(event) => setGroupReason(event.target.value)} value={groupReason} />
            </label>
            <div className="flex justify-end gap-2">
              {creating ? <Button onClick={resetCreate} variant="ghost">Отмена</Button> : null}
              {!activeFormIsCreate && selectedGroup ? (
                <Button
                  className="bg-rose-600 hover:bg-rose-700 active:bg-rose-800"
                  disabled={busy || !groupReason.trim()}
                  leadingIcon={<Archive className="h-4 w-4" />}
                  onClick={() => onArchive(selectedGroup, groupReason.trim())}
                  variant="primary"
                >
                  Архивировать
                </Button>
              ) : null}
              <Button
                disabled={busy || !code.trim() || !name.trim() || !groupReason.trim()}
                leadingIcon={<Save className="h-4 w-4" />}
                onClick={() => {
                  if (activeFormIsCreate) {
                    onCreate({ code: code.trim(), name: name.trim(), description: description.trim(), reason: groupReason.trim() });
                  } else if (selectedGroup) {
                    onUpdate(selectedGroup.audience_group_id, { code: code.trim(), name: name.trim(), description: description.trim(), reason: groupReason.trim() });
                  }
                }}
              >
                {activeFormIsCreate ? "Создать" : "Сохранить"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {selectedGroup ? (
          <Card>
            <CardHeader>
              <CardTitle>Состав аудитории</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 lg:grid-cols-[190px_minmax(180px,1fr)_minmax(220px,1fr)_auto]">
                <label className="block text-sm font-medium text-slate-700">
                  Тип участника
                  <select
                    aria-label="Тип участника"
                    className="field-base mt-2 h-11 w-full px-3 text-sm"
                    onChange={(event) => {
                      setMemberType(event.target.value as AdminRegistryAudienceMemberType);
                      setMemberId("");
                    }}
                    value={memberType}
                  >
                    {memberTypes.map((type) => <option key={type} value={type}>{memberTypeLabels[type]}</option>)}
                  </select>
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Поиск
                  <Input className="mt-2" onChange={(event) => setMemberQuery(event.target.value)} value={memberQuery} />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Участник
                  <select
                    aria-label="Участник"
                    className="field-base mt-2 h-11 w-full px-3 text-sm"
                    onChange={(event) => setMemberId(event.target.value)}
                    value={memberId}
                  >
                    <option value="">Выберите участника</option>
                    {targetOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                </label>
                <div className="flex items-end">
                  <Button disabled={!memberId} onClick={addMember} size="sm">Добавить участника</Button>
                </div>
              </div>

              {memberDraft.length ? (
                <div className="rounded-lg border border-border">
                  {memberDraft.map((member) => (
                    <div className="grid grid-cols-[160px_minmax(0,1fr)_auto] gap-3 border-t border-border px-3 py-2 text-sm first:border-t-0" key={`${member.member_type}:${member.member_id}:${member.include_children ? "tree" : "direct"}`}>
                      <span className="font-medium text-slate-700">{memberTypeLabels[member.member_type]}</span>
                      <span className="text-slate-900">{memberLabel(member, registry)}</span>
                      <Button
                        leadingIcon={<Trash2 className="h-4 w-4" />}
                        onClick={() => setMemberDraft((current) => current.filter((item) => item !== member))}
                        size="sm"
                        variant="ghost"
                      >
                        Убрать
                      </Button>
                    </div>
                  ))}
                </div>
              ) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Состав пуст. Добавьте участников и выполните предпросмотр.</p>}

              <label className="block text-sm font-medium text-slate-700">
                Причина изменения аудитории
                <Input
                  aria-label="Причина изменения аудитории"
                  className="mt-2"
                  onChange={(event) => setMemberReason(event.target.value)}
                  value={memberReason}
                />
              </label>

              {preview ? (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950">
                  <p className="font-semibold">Людей в аудитории: {preview.person_count}</p>
                  <p className="mt-1 text-emerald-800">Правил состава: {preview.member_count}</p>
                  {preview.warnings.length ? (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-amber-800">
                      {preview.warnings.map((warning) => <li key={`${warning.code}-${warning.message}`}>{warning.code}: {warning.message}</li>)}
                    </ul>
                  ) : null}
                  {preview.people.length ? (
                    <p className="mt-2 text-emerald-800">Примеры: {preview.people.slice(0, 4).map((person) => person.display_name).join(", ")}</p>
                  ) : null}
                </div>
              ) : null}

              <div className="flex justify-end gap-2">
                <Button
                  disabled={busy}
                  leadingIcon={<Eye className="h-4 w-4" />}
                  onClick={() => void onPreviewMembers(selectedGroup.audience_group_id, memberDraft)}
                  variant="outline"
                >
                  Предпросмотр состава
                </Button>
                <Button
                  disabled={busy || !preview || !memberReason.trim()}
                  onClick={() => onSaveMembers(selectedGroup.audience_group_id, memberDraft, memberReason.trim())}
                >
                  Сохранить участников
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}
      </section>
    </div>
  );
}
