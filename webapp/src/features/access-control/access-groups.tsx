import { AlertTriangle, CheckCircle2, Plus, Save, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { SearchField } from "../../components/ui/search-field";
import { Tabs } from "../../components/ui/tabs";
import {
  createAccessGroup,
  saveAccessGroupMembers,
  saveAccessGroupPermissions,
  saveAccessGroupQueues,
  type AccessCatalogPayload,
  type AccessGroupItem,
  type AccessQueueItem,
  type AccessUserItem,
} from "./api";
import {
  buildAccessChangeDiff,
  buildGroupDraft,
  filterGroups,
  filterPermissionGroups,
  riskLabel,
  riskTone,
  type GroupDraft,
} from "./model";

type GroupDetailTab = "summary" | "permissions" | "members" | "queues";

const GROUP_DETAIL_TABS: Array<{ value: GroupDetailTab; label: string }> = [
  { label: "Сводка", value: "summary" },
  { label: "Права", value: "permissions" },
  { label: "Участники", value: "members" },
  { label: "Очереди", value: "queues" },
];

type GroupsAccessPanelProps = {
  accessGroups: AccessGroupItem[];
  catalog: AccessCatalogPayload;
  onGroupChange: (group: AccessGroupItem) => void;
  queues: AccessQueueItem[];
  users: AccessUserItem[];
};

export function GroupsAccessPanel({ accessGroups, catalog, onGroupChange, queues, users }: GroupsAccessPanelProps) {
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(accessGroups[0]?.group_id ?? null);
  const [groupQuery, setGroupQuery] = useState("");
  const [detailTab, setDetailTab] = useState<GroupDetailTab>("permissions");
  const [draft, setDraft] = useState<GroupDraft | null>(accessGroups[0] ? buildGroupDraft(accessGroups[0]) : null);
  const [permissionQuery, setPermissionQuery] = useState("");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [riskConfirmed, setRiskConfirmed] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const selectedGroup = accessGroups.find((group) => group.group_id === selectedGroupId) ?? accessGroups[0] ?? null;
  const filteredGroups = useMemo(() => filterGroups(accessGroups, groupQuery), [accessGroups, groupQuery]);
  const selectedPermissionCodes = useMemo(() => new Set(draft?.permissions ?? []), [draft?.permissions]);
  const filteredPermissionGroups = useMemo(
    () => filterPermissionGroups(catalog.groups, permissionQuery, selectedOnly ? selectedPermissionCodes : undefined),
    [catalog.groups, permissionQuery, selectedOnly, selectedPermissionCodes],
  );
  const diff = useMemo(
    () =>
      selectedGroup && draft
        ? buildAccessChangeDiff(selectedGroup, draft, catalog, queues)
        : {
            addedMembers: [],
            addedPermissions: [],
            addedQueues: [],
            affectedUsersCount: 0,
            hasChanges: false,
            highRiskAdded: [],
            removedMembers: [],
            removedPermissions: [],
            removedQueues: [],
          },
    [catalog, draft, queues, selectedGroup],
  );

  useEffect(() => {
    if (selectedGroupId === null && accessGroups.length > 0) {
      setSelectedGroupId(accessGroups[0].group_id);
    }
  }, [accessGroups, selectedGroupId]);

  useEffect(() => {
    if (!selectedGroup) {
      setDraft(null);
      return;
    }
    setDraft(buildGroupDraft(selectedGroup));
    setReviewOpen(false);
    setRiskConfirmed(false);
    setSuccessMessage(null);
  }, [selectedGroup?.group_id]);

  const createMutation = useMutation({
    mutationFn: createAccessGroup,
    onSuccess: (group) => {
      onGroupChange(group);
      setSelectedGroupId(group.group_id);
      setNewCode("");
      setNewName("");
      setNewDescription("");
      setSuccessMessage("Группа создана");
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!selectedGroup || !draft) {
        throw new Error("Группа не выбрана");
      }
      let group = selectedGroup;
      if (diff.addedPermissions.length > 0 || diff.removedPermissions.length > 0) {
        group = await saveAccessGroupPermissions(group.group_id, draft.permissions);
      }
      if (diff.addedMembers.length > 0 || diff.removedMembers.length > 0) {
        group = await saveAccessGroupMembers(group.group_id, draft.members);
      }
      if (diff.addedQueues.length > 0 || diff.removedQueues.length > 0) {
        group = await saveAccessGroupQueues(group.group_id, draft.queues);
      }
      return group;
    },
    onSuccess: (group) => {
      onGroupChange(group);
      setDraft(buildGroupDraft(group));
      setReviewOpen(false);
      setRiskConfirmed(false);
      setSuccessMessage("Изменения сохранены");
    },
  });

  const updateDraft = (updater: (current: GroupDraft) => GroupDraft) => {
    setSuccessMessage(null);
    setDraft((current) => (current ? updater(current) : current));
  };

  const togglePermission = (permissionCode: string) => {
    updateDraft((current) => {
      const exists = current.permissions.includes(permissionCode);
      const permissions = exists
        ? current.permissions.filter((item) => item !== permissionCode)
        : [...current.permissions, permissionCode].sort();
      return { ...current, permissions };
    });
  };

  const toggleMember = (actorId: string) => {
    updateDraft((current) => {
      const exists = current.members.includes(actorId);
      const members = exists ? current.members.filter((item) => item !== actorId) : [...current.members, actorId].sort();
      return { ...current, members };
    });
  };

  const toggleQueue = (queueId: number) => {
    updateDraft((current) => {
      const exists = current.queues.some((queue) => queue.queue_id === queueId);
      const queuesDraft = exists
        ? current.queues.filter((queue) => queue.queue_id !== queueId)
        : [...current.queues, { queue_id: queueId, role_in_queue: null }].sort((left, right) => left.queue_id - right.queue_id);
      return { ...current, queues: queuesDraft };
    });
  };

  const setQueueRole = (queueId: number, roleInQueue: string) => {
    updateDraft((current) => ({
      ...current,
      queues: current.queues.map((queue) =>
        queue.queue_id === queueId ? { ...queue, role_in_queue: roleInQueue.trim() || null } : queue,
      ),
    }));
  };

  const discardDraft = () => {
    if (!selectedGroup) {
      return;
    }
    setDraft(buildGroupDraft(selectedGroup));
    setReviewOpen(false);
    setRiskConfirmed(false);
    setSuccessMessage(null);
  };

  const queueSelected = (queueId: number) => Boolean(draft?.queues.some((queue) => queue.queue_id === queueId));
  const queueRole = (queueId: number) => draft?.queues.find((queue) => queue.queue_id === queueId)?.role_in_queue ?? "";

  return (
    <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border">
          <CardTitle>Группы доступа</CardTitle>
          <p className="text-sm text-slate-500">Основной список: выберите группу для безопасного редактирования.</p>
          <SearchField onChange={(event) => setGroupQuery(event.target.value)} placeholder="Поиск группы" value={groupQuery} />
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="max-h-[420px] space-y-2 overflow-y-auto">
            {filteredGroups.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
                Группы не найдены.
              </p>
            ) : (
              filteredGroups.map((group) => (
                <button
                  className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
                    selectedGroup?.group_id === group.group_id
                      ? "border-brand-200 bg-brand-50"
                      : "border-border bg-white hover:bg-slate-50"
                  }`}
                  key={group.group_id}
                  onClick={() => setSelectedGroupId(group.group_id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-slate-950">{group.name}</p>
                      <p className="mt-1 font-mono text-xs text-slate-500">{group.code}</p>
                    </div>
                    <Badge tone={group.is_active ? "success" : "neutral"}>{group.is_active ? "Активна" : "Отключена"}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    {group.permissions.length} прав · {group.members.length} участников · {group.queue_grants.length} очередей
                  </p>
                </button>
              ))
            )}
          </div>

          <form
            className="space-y-2 rounded-lg border border-border bg-slate-50 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              createMutation.mutate({ code: newCode, description: newDescription || null, name: newName });
            }}
          >
            <p className="text-sm font-semibold text-slate-950">Новая группа</p>
            <Input aria-label="Код новой группы" onChange={(event) => setNewCode(event.target.value)} placeholder="support_l2" required value={newCode} />
            <Input aria-label="Название новой группы" onChange={(event) => setNewName(event.target.value)} placeholder="Название" required value={newName} />
            <Input aria-label="Описание новой группы" onChange={(event) => setNewDescription(event.target.value)} placeholder="Описание" value={newDescription} />
            <Button disabled={createMutation.isPending} leadingIcon={<Plus className="h-4 w-4" />} size="sm" type="submit">
              Создать группу
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>{selectedGroup?.name ?? "Группа не выбрана"}</CardTitle>
              <p className="font-mono text-xs text-slate-500">{selectedGroup?.code ?? "Выберите группу слева"}</p>
            </div>
            {successMessage ? (
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                {successMessage}
              </div>
            ) : null}
          </div>
          <Tabs items={GROUP_DETAIL_TABS} onValueChange={(value) => setDetailTab(value as GroupDetailTab)} value={detailTab} />
        </CardHeader>

        {selectedGroup && draft && diff.hasChanges ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-900">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span className="font-semibold">Есть несохранённые изменения</span>
              <span>Затронуто пользователей: {diff.affectedUsersCount}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={discardDraft} size="sm" variant="ghost">
                Отменить
              </Button>
              <Button leadingIcon={<Save className="h-4 w-4" />} onClick={() => setReviewOpen(true)} size="sm">
                Сохранить изменения
              </Button>
            </div>
          </div>
        ) : null}

        <CardContent className="p-5">
          {selectedGroup && draft ? (
            <>
              {detailTab === "summary" ? <GroupSummary group={selectedGroup} /> : null}
              {detailTab === "permissions" ? (
                <section className="space-y-4">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="font-semibold text-slate-950">Права группы</p>
                      <p className="text-sm text-slate-500">Права сгруппированы по доменам, технический код показан вторым уровнем.</p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <SearchField
                        onChange={(event) => setPermissionQuery(event.target.value)}
                        placeholder="Поиск права"
                        value={permissionQuery}
                      />
                      <label className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-sm">
                        <input checked={selectedOnly} onChange={(event) => setSelectedOnly(event.target.checked)} type="checkbox" />
                        Только выбранные
                      </label>
                    </div>
                  </div>
                  {filteredPermissionGroups.map((group) => (
                    <div className="rounded-lg border border-border" key={group.code}>
                      <div className="border-b border-border bg-slate-50 px-4 py-3">
                        <p className="font-semibold text-slate-950">{group.label}</p>
                        <p className="font-mono text-xs text-slate-500">{group.code}</p>
                      </div>
                      <div className="grid gap-2 p-4 xl:grid-cols-2">
                        {group.permissions.map((permission) => (
                          <label className="flex gap-3 rounded-lg border border-border bg-white px-3 py-3 text-sm" key={permission.code}>
                            <input
                              checked={draft.permissions.includes(permission.code)}
                              className="mt-1 h-4 w-4"
                              onChange={() => togglePermission(permission.code)}
                              type="checkbox"
                            />
                            <span className="min-w-0">
                              <span className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-slate-950">{permission.label}</span>
                                <Badge tone={riskTone(permission.risk)}>{riskLabel(permission.risk)}</Badge>
                              </span>
                              <span className="mt-1 block font-mono text-xs text-slate-500">{permission.code}</span>
                              <span className="mt-2 block text-xs text-slate-500">{permission.description}</span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>
              ) : null}
              {detailTab === "members" ? (
                <section className="space-y-3">
                  <p className="font-semibold text-slate-950">Участники</p>
                  <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                    {users.map((user) => (
                      <label className="flex gap-2 rounded-lg border border-border bg-white px-3 py-3 text-sm" key={user.user_login}>
                        <input
                          checked={draft.members.includes(user.user_login)}
                          className="mt-1 h-4 w-4"
                          onChange={() => toggleMember(user.user_login)}
                          type="checkbox"
                        />
                        <span>
                          <span className="font-semibold text-slate-950">{user.user_login}</span>
                          <span className="block text-xs text-slate-500">{user.role_label}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </section>
              ) : null}
              {detailTab === "queues" ? (
                <section className="space-y-3">
                  <p className="font-semibold text-slate-950">Очереди</p>
                  <div className="grid gap-3 xl:grid-cols-2">
                    {queues.map((queue) => (
                      <div className="rounded-lg border border-border bg-white px-3 py-3" key={queue.queue_id}>
                        <label className="flex gap-2 text-sm">
                          <input
                            checked={queueSelected(queue.queue_id)}
                            className="mt-1 h-4 w-4"
                            onChange={() => toggleQueue(queue.queue_id)}
                            type="checkbox"
                          />
                          <span>
                            <span className="font-semibold text-slate-950">{queue.queue_name}</span>
                            <span className="block font-mono text-xs text-slate-500">{queue.queue_code}</span>
                          </span>
                        </label>
                        <label className="mt-3 grid gap-1 text-xs font-medium text-slate-500">
                          {`Роль в очереди ${queue.queue_name}`}
                          <Input
                            disabled={!queueSelected(queue.queue_id)}
                            onChange={(event) => setQueueRole(queue.queue_id, event.target.value)}
                            value={queueRole(queue.queue_id)}
                          />
                        </label>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}
            </>
          ) : (
            <p className="rounded-lg border border-border bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              Создайте или выберите группу доступа.
            </p>
          )}
        </CardContent>
      </Card>

      {reviewOpen && selectedGroup && draft ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6">
          <div
            aria-label="Проверка изменений"
            aria-modal="true"
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white shadow-xl"
            role="dialog"
          >
            <div className="border-b border-border px-5 py-4">
              <h2 className="text-lg font-semibold text-slate-950">Проверка изменений</h2>
              <p className="mt-1 text-sm text-slate-500">Предпросмотр изменений перед применением к группе {selectedGroup.name}.</p>
            </div>
            <div className="space-y-4 px-5 py-4">
              <DiffList
                addedMembers={diff.addedMembers}
                addedPermissions={diff.addedPermissions}
                addedQueues={diff.addedQueues}
                removedMembers={diff.removedMembers}
                removedPermissions={diff.removedPermissions}
                removedQueues={diff.removedQueues}
              />
              <div className="rounded-lg border border-border bg-slate-50 px-3 py-3 text-sm">
                <p className="font-semibold text-slate-950">Итог влияния</p>
                <p className="mt-1 text-slate-600">Затронуто пользователей: {diff.affectedUsersCount}</p>
                <p className="text-slate-600">Высокорисковые права добавлены: {diff.highRiskAdded.length}</p>
              </div>
              {diff.highRiskAdded.length > 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle className="h-4 w-4" />
                    Требуется подтверждение риска
                  </div>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {diff.highRiskAdded.map((permission) => (
                      <li key={permission.code}>
                        {permission.label} <span className="font-mono text-xs">{permission.code}</span>
                      </li>
                    ))}
                  </ul>
                  <label className="mt-3 flex items-center gap-2">
                    <input checked={riskConfirmed} onChange={(event) => setRiskConfirmed(event.target.checked)} type="checkbox" />
                    Подтверждаю добавление высокорисковых прав
                  </label>
                </div>
              ) : null}
              {applyMutation.isError ? (
                <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-700">
                  {applyMutation.error instanceof Error ? applyMutation.error.message : "Не удалось сохранить изменения"}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4">
              <Button onClick={() => setReviewOpen(false)} variant="outline">
                Закрыть
              </Button>
              <Button
                disabled={applyMutation.isPending || (diff.highRiskAdded.length > 0 && !riskConfirmed)}
                onClick={() => applyMutation.mutate()}
              >
                Применить изменения
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GroupSummary({ group }: { group: AccessGroupItem }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-lg bg-slate-50 px-3 py-3">
        <p className="text-xs text-slate-500">Права</p>
        <p className="mt-1 text-xl font-semibold text-slate-950">{group.permissions.length}</p>
      </div>
      <div className="rounded-lg bg-slate-50 px-3 py-3">
        <p className="text-xs text-slate-500">Участники</p>
        <p className="mt-1 text-xl font-semibold text-slate-950">{group.members.length}</p>
      </div>
      <div className="rounded-lg bg-slate-50 px-3 py-3">
        <p className="text-xs text-slate-500">Очереди</p>
        <p className="mt-1 text-xl font-semibold text-slate-950">{group.queue_grants.length}</p>
      </div>
    </div>
  );
}

function DiffList({
  addedMembers,
  addedPermissions,
  addedQueues,
  removedMembers,
  removedPermissions,
  removedQueues,
}: {
  addedMembers: string[];
  addedPermissions: Array<{ code: string; label: string }>;
  addedQueues: Array<{ queue_name: string; role_in_queue: string | null }>;
  removedMembers: string[];
  removedPermissions: Array<{ code: string; label: string }>;
  removedQueues: Array<{ queue_name: string; role_in_queue: string | null }>;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3">
        <p className="font-semibold text-emerald-900">Будет добавлено</p>
        <DiffItems
          emptyText="Добавлений нет"
          items={[
            ...addedPermissions.map((permission) => `${permission.label} · ${permission.code}`),
            ...addedMembers.map((member) => `Участник · ${member}`),
            ...addedQueues.map((queue) => `Очередь · ${queue.queue_name}${queue.role_in_queue ? ` · ${queue.role_in_queue}` : ""}`),
          ]}
        />
      </div>
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-3">
        <p className="font-semibold text-rose-900">Будет удалено</p>
        <DiffItems
          emptyText="Удалений нет"
          items={[
            ...removedPermissions.map((permission) => `${permission.label} · ${permission.code}`),
            ...removedMembers.map((member) => `Участник · ${member}`),
            ...removedQueues.map((queue) => `Очередь · ${queue.queue_name}${queue.role_in_queue ? ` · ${queue.role_in_queue}` : ""}`),
          ]}
        />
      </div>
    </div>
  );
}

function DiffItems({ emptyText, items }: { emptyText: string; items: string[] }) {
  if (items.length === 0) {
    return <p className="mt-2 text-sm text-slate-500">{emptyText}</p>;
  }
  return (
    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
