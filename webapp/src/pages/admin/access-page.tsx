import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { startTransition, useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import {
  fetchAccessCatalog,
  fetchAccessSummary,
  fetchEffectiveAccess,
  type AccessPermissionGroup,
  type AccessRoleItem,
  type AccessUserItem,
} from "../../features/access-control/api";
import { cn } from "../../shared/ui/cn";

function EmptyState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Activity className="h-5 w-5" />
      </div>
      <p className="mt-3 font-semibold text-slate-950">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
    </div>
  );
}

function getRiskTone(risk: string): "danger" | "neutral" | "warning" {
  return risk === "high" ? "warning" : "neutral";
}

function UserRow({
  active,
  onSelect,
  user,
}: {
  active: boolean;
  onSelect: (user: AccessUserItem) => void;
  user: AccessUserItem;
}) {
  return (
    <button
      className={cn(
        "grid w-full gap-3 border-b border-border px-5 py-4 text-left transition-colors lg:grid-cols-[minmax(0,1fr)_140px_120px]",
        active ? "bg-brand-50/70" : "bg-white hover:bg-slate-50",
      )}
      onClick={() => onSelect(user)}
      type="button"
    >
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold text-slate-950">{user.user_login}</p>
          <Badge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "Активен" : "Отключён"}</Badge>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          {user.role_label} / role: {user.actor_role}
        </p>
      </div>
      <div className="text-sm text-slate-600">
        <p className="font-medium text-slate-900">{user.queue_count}</p>
        <p className="text-xs text-slate-500">очередей</p>
      </div>
      <div className="text-sm text-slate-600">
        <p className="font-medium text-slate-900">{user.groups.length}</p>
        <p className="text-xs text-slate-500">групп</p>
      </div>
    </button>
  );
}

function RoleMatrix({ roles }: { roles: AccessRoleItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-5 py-3">Роль</th>
            <th className="px-5 py-3">Permissions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {roles.map((role) => (
            <tr key={role.code}>
              <td className="px-5 py-4 align-top">
                <p className="font-semibold text-slate-950">{role.label}</p>
                <p className="text-xs text-slate-500">{role.code}</p>
              </td>
              <td className="px-5 py-4">
                <div className="flex flex-wrap gap-2">
                  {role.permissions.map((permission) => (
                    <span
                      className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                      key={`${role.code}:${permission}`}
                    >
                      {permission}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PermissionCatalog({ groups }: { groups: AccessPermissionGroup[] }) {
  return (
    <div className="divide-y divide-border">
      {groups.map((group) => (
        <section className="px-5 py-4" key={group.code}>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-slate-950">{group.label}</p>
              <p className="text-xs text-slate-500">{group.code}</p>
            </div>
            <Badge tone="neutral">{group.permissions.length} прав</Badge>
          </div>
          <div className="mt-3 grid gap-2 xl:grid-cols-2">
            {group.permissions.map((permission) => (
              <div className="rounded-lg border border-border bg-white px-3 py-3" key={permission.code}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-950">{permission.label}</p>
                  <Badge tone={getRiskTone(permission.risk)}>{permission.risk}</Badge>
                </div>
                <p className="mt-1 font-mono text-xs text-slate-500">{permission.code}</p>
                <p className="mt-2 text-sm text-slate-500">{permission.description}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function AdminAccessPage() {
  const [selectedUser, setSelectedUser] = useState<AccessUserItem | null>(null);
  const [query, setQuery] = useState("");

  const catalogQuery = useQuery({
    queryKey: ["admin-access-catalog"],
    queryFn: fetchAccessCatalog,
    retry: false,
  });

  const summaryQuery = useQuery({
    queryKey: ["admin-access-summary"],
    queryFn: fetchAccessSummary,
    retry: false,
  });

  const users = summaryQuery.data?.users ?? [];
  const filteredUsers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return users;
    }
    return users.filter((user) =>
      [user.user_login, user.actor_role, user.role_label].some((value) =>
        value.toLowerCase().includes(normalized),
      ),
    );
  }, [query, users]);

  useEffect(() => {
    if (selectedUser || users.length === 0) {
      return;
    }
    setSelectedUser(users[0]);
  }, [selectedUser, users]);

  const effectiveQuery = useQuery({
    queryKey: ["admin-access-effective", selectedUser?.user_login, selectedUser?.actor_role],
    queryFn: () =>
      fetchEffectiveAccess({
        userLogin: selectedUser?.user_login ?? "",
        actorRole: selectedUser?.actor_role ?? "user",
      }),
    enabled: Boolean(selectedUser),
    retry: false,
  });

  if (catalogQuery.isLoading || summaryQuery.isLoading) {
    return <EmptyState title="Загружаем RBAC" description="Собираем роли, пользователей, очереди и каталог прав." />;
  }

  if (catalogQuery.isError || summaryQuery.isError || !catalogQuery.data || !summaryQuery.data) {
    return (
      <EmptyState
        title="RBAC недоступен"
        description={
          catalogQuery.error instanceof Error
            ? catalogQuery.error.message
            : summaryQuery.error instanceof Error
              ? summaryQuery.error.message
              : "Не удалось загрузить access-control payload."
        }
      />
    );
  }

  const catalog = catalogQuery.data;
  const summary = summaryQuery.data;
  const effective = effectiveQuery.data;

  return (
    <section className="space-y-5">
      <PageHeading
        description="Единая точка для проверки ролей, видимости workspace, очередей, module/tool launch policy и итоговых прав пользователя."
        eyebrow="Admin workspace"
        title="Access Control"
      />

      <div className="grid gap-3 md:grid-cols-4">
        <div className="surface-panel px-4 py-3">
          <p className="text-xs font-semibold uppercase text-slate-400">Версия каталога</p>
          <p className="mt-1 font-semibold text-slate-950">{catalog.version}</p>
        </div>
        <div className="surface-panel px-4 py-3">
          <p className="text-xs font-semibold uppercase text-slate-400">Пользователи</p>
          <p className="mt-1 font-semibold text-slate-950">{summary.users.length}</p>
        </div>
        <div className="surface-panel px-4 py-3">
          <p className="text-xs font-semibold uppercase text-slate-400">Очереди</p>
          <p className="mt-1 font-semibold text-slate-950">{summary.queues.length}</p>
        </div>
        <div className="surface-panel px-4 py-3">
          <p className="text-xs font-semibold uppercase text-slate-400">Группы доступа</p>
          <p className="mt-1 font-semibold text-slate-950">{summary.access_groups.length}</p>
        </div>
      </div>

      {summary.notes.length > 0 ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{summary.notes.join(" ")}</p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <CardTitle>Пользователи и роли</CardTitle>
                  <p className="mt-1 text-sm text-slate-500">Выберите пользователя, чтобы увидеть effective access.</p>
                </div>
                <SearchField
                  className="lg:w-[300px]"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Поиск по логину или роли"
                  value={query}
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {filteredUsers.length === 0 ? (
                <EmptyState title="Пользователей нет" description="DB-backed users не вернули записей для текущего фильтра." />
              ) : (
                filteredUsers.map((user) => (
                  <UserRow
                    active={selectedUser?.user_login === user.user_login}
                    key={user.user_login}
                    onSelect={(nextUser) => {
                      startTransition(() => {
                        setSelectedUser(nextUser);
                      });
                    }}
                    user={user}
                  />
                ))
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <CardTitle>Permissions Matrix</CardTitle>
              <p className="text-sm text-slate-500">Built-in роли пока являются базовым слоем прав; группы будут additive-слоем.</p>
            </CardHeader>
            <CardContent className="p-0">
              <RoleMatrix roles={catalog.roles} />
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <CardTitle>Каталог permissions</CardTitle>
              <p className="text-sm text-slate-500">Технические codes стабильны, operator labels остаются человекочитаемыми.</p>
            </CardHeader>
            <CardContent className="p-0">
              <PermissionCatalog groups={catalog.groups} />
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-5">
          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>Effective Access</CardTitle>
                  <p className="mt-1 text-sm text-slate-500">{selectedUser?.user_login ?? "Пользователь не выбран"}</p>
                </div>
                <ShieldCheck className="h-5 w-5 text-brand-600" />
              </div>
            </CardHeader>
            <CardContent className="space-y-5 p-5">
              {effectiveQuery.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Activity className="h-4 w-4 animate-spin" />
                  Считаем итоговый доступ
                </div>
              ) : effective ? (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-xs text-slate-500">Роль</p>
                      <p className="mt-1 font-semibold text-slate-950">{effective.role_label}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-xs text-slate-500">Workspace</p>
                      <p className="mt-1 font-semibold text-slate-950">{effective.workspaces.join(", ") || "нет"}</p>
                    </div>
                  </div>

                  <section>
                    <div className="mb-2 flex items-center gap-2">
                      <KeyRound className="h-4 w-4 text-slate-500" />
                      <p className="text-sm font-semibold text-slate-950">Permissions</p>
                    </div>
                    <div className="flex max-h-[260px] flex-wrap gap-2 overflow-y-auto rounded-lg border border-border bg-white p-3">
                      {effective.permissions.map((permission) => (
                        <span className="rounded-full bg-brand-50 px-2.5 py-1 font-mono text-xs text-brand-800" key={permission}>
                          {permission}
                        </span>
                      ))}
                    </div>
                  </section>

                  <section>
                    <div className="mb-2 flex items-center gap-2">
                      <UsersRound className="h-4 w-4 text-slate-500" />
                      <p className="text-sm font-semibold text-slate-950">Очереди</p>
                    </div>
                    {effective.queues.length === 0 ? (
                      <p className="rounded-lg border border-border bg-slate-50 px-3 py-3 text-sm text-slate-500">
                        Прямых memberships нет.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {effective.queues.map((queue) => (
                          <div className="rounded-lg border border-border px-3 py-3" key={queue.queue_id}>
                            <div className="flex items-center justify-between gap-2">
                              <p className="font-semibold text-slate-950">{queue.queue_name}</p>
                              {queue.role_in_queue ? <Badge tone="success">{queue.role_in_queue}</Badge> : null}
                            </div>
                            <p className="mt-1 text-xs text-slate-500">{queue.queue_code}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </>
              ) : (
                <EmptyState title="Нет расчёта" description="Выберите пользователя для расчёта итоговых прав." />
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <CardTitle>Очереди</CardTitle>
              <p className="text-sm text-slate-500">Queue membership остаётся источником видимости support-тикетов.</p>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {summary.queues.map((queue) => (
                  <div className="px-5 py-4" key={queue.queue_id}>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-950">{queue.queue_name}</p>
                        <p className="text-xs text-slate-500">{queue.queue_code}</p>
                      </div>
                      <Badge tone={queue.is_active ? "success" : "neutral"}>
                        {queue.members_count} members
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border">
              <CardTitle>Следующий слой</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-5">
              <div className="flex gap-2 text-sm text-slate-600">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                <p>Добавить CRUD групп доступа и explicit save/apply для grant matrix.</p>
              </div>
              <div className="flex gap-2 text-sm text-slate-600">
                <Search className="mt-0.5 h-4 w-4 text-slate-500" />
                <p>Подключить disabled reasons к действиям тикета, модулей и плейбуков.</p>
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
