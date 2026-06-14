import { Activity, KeyRound, Layers3, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import type { AccessCatalogPayload, AccessEffectivePayload, AccessGroupItem, AccessUserItem } from "./api";
import { buildEffectivePermissionRows, filterUsers, riskLabel, riskTone, statusLabel, workspaceLabel } from "./model";

type UsersAccessTableProps = {
  accessGroups: AccessGroupItem[];
  catalog: AccessCatalogPayload;
  effective?: AccessEffectivePayload;
  effectiveLoading: boolean;
  onSelectUser: (user: AccessUserItem) => void;
  selectedUser: AccessUserItem | null;
  users: AccessUserItem[];
};

export function UsersAccessTable({
  accessGroups,
  catalog,
  effective,
  effectiveLoading,
  onSelectUser,
  selectedUser,
  users,
}: UsersAccessTableProps) {
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [flagFilter, setFlagFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const roleOptions = useMemo(() => Array.from(new Set(users.map((user) => user.actor_role))).sort(), [users]);
  const roleLabelByCode = useMemo(() => new Map(catalog.roles.map((role) => [role.code, role.label])), [catalog.roles]);
  const filteredUsers = useMemo(
    () => filterUsers(users, query, roleFilter, statusFilter, flagFilter),
    [flagFilter, query, roleFilter, statusFilter, users],
  );

  useEffect(() => {
    if (filteredUsers.length === 0) {
      return;
    }
    if (!selectedUser || !filteredUsers.some((user) => user.user_login === selectedUser.user_login)) {
      onSelectUser(filteredUsers[0]);
    }
  }, [filteredUsers, onSelectUser, selectedUser]);

  const toggleSelection = (userLogin: string) => {
    setSelectedIds((current) =>
      current.includes(userLogin) ? current.filter((item) => item !== userLogin) : [...current, userLogin].sort(),
    );
  };

  return (
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_440px]">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border">
          <div className="flex flex-col gap-3">
            <div>
              <CardTitle>Пользователи</CardTitle>
              <p className="text-sm text-slate-500">Найдите пользователя, затем откройте объяснение итогового доступа.</p>
            </div>
            <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_160px_170px_220px]">
              <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Логин, имя, email или роль" value={query} />
              <Select aria-label="Фильтр по роли" onChange={(event) => setRoleFilter(event.target.value)} value={roleFilter}>
                <option value="all">Все роли</option>
                {roleOptions.map((role) => (
                  <option key={role} value={role}>
                    {roleLabelByCode.get(role) ? `${roleLabelByCode.get(role)} (${role})` : role}
                  </option>
                ))}
              </Select>
              <Select aria-label="Фильтр по статусу" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
                <option value="all">Все статусы</option>
                <option value="active">Активные</option>
                <option value="disabled">Отключённые</option>
              </Select>
              <Select aria-label="Фильтр по признаку доступа" onChange={(event) => setFlagFilter(event.target.value)} value={flagFilter}>
                <option value="all">Все признаки</option>
                <option value="groups">Есть группы</option>
                <option value="queues">Есть прямые очереди</option>
                <option value="elevated">Администратор/поддержка</option>
              </Select>
            </div>
          </div>
        </CardHeader>
        {selectedIds.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 border-b border-border bg-brand-50 px-5 py-3 text-sm">
            <span className="font-semibold text-brand-900">Выбрано: {selectedIds.length}</span>
            <Button disabled size="sm" variant="outline">
              Добавить в группу
            </Button>
            <Button disabled size="sm" variant="outline">
              Удалить из группы
            </Button>
            <Button onClick={() => setSelectedIds([])} size="sm" variant="ghost">
              Очистить выбор
            </Button>
          </div>
        ) : null}
        <CardContent className="p-0">
          {filteredUsers.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="font-semibold text-slate-950">Пользователей нет</p>
              <p className="mt-1 text-sm text-slate-500">Пользователи из БД не вернули записей для текущего фильтра.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="w-12 px-5 py-3">Выбор</th>
                    <th className="px-5 py-3">Логин</th>
                    <th className="px-5 py-3">Отображаемое имя</th>
                    <th className="px-5 py-3">Роль</th>
                    <th className="px-5 py-3">Статус</th>
                    <th className="px-5 py-3">Группы</th>
                    <th className="px-5 py-3">Очереди</th>
                    <th className="px-5 py-3">Риск</th>
                    <th className="px-5 py-3">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredUsers.map((user) => (
                    <tr className={selectedUser?.user_login === user.user_login ? "bg-brand-50/70" : "bg-white"} key={user.user_login}>
                      <td className="px-5 py-4">
                        <input
                          aria-label={`Выбрать ${user.user_login}`}
                          checked={selectedIds.includes(user.user_login)}
                          className="h-4 w-4"
                          onChange={() => toggleSelection(user.user_login)}
                          type="checkbox"
                        />
                      </td>
                      <td className="px-5 py-4">
                        <p className="font-semibold text-slate-950">{user.user_login}</p>
                      </td>
                      <td className="px-5 py-4 text-slate-500">Не передано API</td>
                      <td className="px-5 py-4">
                        <p className="font-semibold text-slate-950">{user.role_label}</p>
                        <p className="font-mono text-xs text-slate-500">{user.actor_role}</p>
                      </td>
                      <td className="px-5 py-4">
                        <Badge tone={user.is_active ? "success" : "neutral"}>{statusLabel(user.is_active)}</Badge>
                      </td>
                      <td className="px-5 py-4">{user.groups.length}</td>
                      <td className="px-5 py-4">{user.queue_count}</td>
                      <td className="px-5 py-4">
                        <Badge tone={["admin", "support"].includes(user.actor_role) ? "warning" : "neutral"}>
                          {["admin", "support"].includes(user.actor_role) ? "Повышенный" : "Обычный"}
                        </Badge>
                      </td>
                      <td className="px-5 py-4">
                        <Button onClick={() => onSelectUser(user)} size="sm" variant="outline">
                          {`Открыть доступ ${user.user_login}`}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <UserEffectiveAccessPanel
        accessGroups={accessGroups}
        catalog={catalog}
        effective={effective}
        loading={effectiveLoading}
        user={selectedUser}
      />
    </div>
  );
}

function UserEffectiveAccessPanel({
  accessGroups,
  catalog,
  effective,
  loading,
  user,
}: {
  accessGroups: AccessGroupItem[];
  catalog: AccessCatalogPayload;
  effective?: AccessEffectivePayload;
  loading: boolean;
  user: AccessUserItem | null;
}) {
  const permissionRows = useMemo(
    () => (effective ? buildEffectivePermissionRows(catalog, accessGroups, effective) : []),
    [accessGroups, catalog, effective],
  );

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border">
        <CardTitle>Эффективный доступ</CardTitle>
        <p className="text-sm text-slate-500">{user?.user_login ?? "Пользователь не выбран"}</p>
      </CardHeader>
      <CardContent className="space-y-5 p-5">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Activity className="h-4 w-4 animate-spin" />
            Считаем итоговый доступ
          </div>
        ) : effective && user ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-slate-50 px-3 py-3">
                <p className="text-xs text-slate-500">Роль</p>
                <p className="mt-1 font-semibold text-slate-950">{effective.role_label}</p>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-3">
                <p className="text-xs text-slate-500">Статус</p>
                <p className="mt-1 font-semibold text-slate-950">{statusLabel(user.is_active)}</p>
              </div>
            </div>

            <section>
              <div className="mb-2 flex items-center gap-2">
                <Layers3 className="h-4 w-4 text-slate-500" />
                <p className="text-sm font-semibold text-slate-950">Почему есть доступ</p>
              </div>
              <div className="space-y-2 rounded-lg border border-border bg-white p-3 text-sm">
                <p>
                  <span className="font-semibold">Роль:</span> {effective.role_label}
                </p>
                {effective.groups.length > 0 ? (
                  effective.groups.map((group) => (
                    <p key={group}>
                      <span className="font-semibold">Группа:</span> {group}
                    </p>
                  ))
                ) : (
                  <p className="text-slate-500">Группы доступа не назначены.</p>
                )}
                {effective.queues.length > 0 ? (
                  <p>
                    <span className="font-semibold">Очереди:</span> {effective.queues.map((queue) => queue.queue_code).join(", ")}
                  </p>
                ) : null}
              </div>
            </section>

            <section>
              <div className="mb-2 flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-slate-500" />
                <p className="text-sm font-semibold text-slate-950">Права по доменам</p>
              </div>
              <div className="max-h-[380px] overflow-y-auto rounded-lg border border-border">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Право</th>
                      <th className="px-3 py-2">Домен</th>
                      <th className="px-3 py-2">Источник</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {permissionRows.map((permission) => (
                      <tr key={permission.code}>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-slate-950">{permission.label}</span>
                            <Badge tone={riskTone(permission.risk)}>{riskLabel(permission.risk)}</Badge>
                          </div>
                          <p className="mt-1 font-mono text-xs text-slate-500">{permission.code}</p>
                        </td>
                        <td className="px-3 py-3 text-slate-600">{permission.domain}</td>
                        <td className="px-3 py-3 text-slate-600">{permission.sourceLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section>
              <div className="mb-2 flex items-center gap-2">
                <UsersRound className="h-4 w-4 text-slate-500" />
                <p className="text-sm font-semibold text-slate-950">Рабочие области и очереди</p>
              </div>
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {effective.workspaces.length > 0 ? (
                    effective.workspaces.map((workspace) => (
                      <Badge key={workspace} tone="brand">
                        {workspaceLabel(workspace)}
                      </Badge>
                    ))
                  ) : (
                    <Badge tone="neutral">Нет рабочих областей</Badge>
                  )}
                </div>
                {effective.queues.length > 0 ? (
                  <div className="space-y-2">
                    {effective.queues.map((queue) => (
                      <div className="rounded-lg border border-border px-3 py-3" key={queue.queue_id}>
                        <p className="font-semibold text-slate-950">{queue.queue_name}</p>
                        <p className="mt-1 font-mono text-xs text-slate-500">{queue.queue_code}</p>
                        {queue.role_in_queue ? <Badge className="mt-2" tone="success">{queue.role_in_queue}</Badge> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-lg border border-border bg-slate-50 px-3 py-3 text-sm text-slate-500">
                    Прямых очередей нет.
                  </p>
                )}
              </div>
            </section>
          </>
        ) : (
          <p className="rounded-lg border border-border bg-slate-50 px-3 py-3 text-sm text-slate-500">
            Выберите пользователя для расчёта итоговых прав.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
