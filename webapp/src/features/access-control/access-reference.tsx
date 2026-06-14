import { AlertTriangle, BookOpen, CheckCircle2, History, Info, Search, ShieldAlert, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import type { AccessAuditPayload, AccessCatalogPayload, AccessGroupItem, AccessQueueItem, AccessSummaryPayload } from "./api";
import {
  buildPermissionMap,
  effectiveGroupUserCount,
  filterPermissionGroups,
  filterQueues,
  queueGrantsForQueue,
  riskLabel,
  riskTone,
} from "./model";

function EmptyBlock({ description, title }: { description: string; title: string }) {
  return (
    <div className="flex min-h-[180px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-slate-50 px-6 py-8 text-center">
      <Info className="h-5 w-5 text-slate-400" />
      <p className="mt-3 font-semibold text-slate-950">{title}</p>
      <p className="mt-1 max-w-lg text-sm text-slate-500">{description}</p>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="surface-panel px-4 py-3">
      <p className="text-xs font-semibold uppercase text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function AuditFindingCard({
  count,
  description,
  title,
  tone = "neutral",
}: {
  count: number;
  description: string;
  title: string;
  tone?: "neutral" | "warning" | "danger";
}) {
  const iconTone = tone === "danger" ? "text-rose-600" : tone === "warning" ? "text-amber-600" : "text-slate-500";
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base">{title}</CardTitle>
          <AlertTriangle className={`h-5 w-5 ${iconTone}`} />
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-2xl font-semibold text-slate-950">{count}</p>
        <p className="mt-2 text-sm text-slate-500">{description}</p>
      </CardContent>
    </Card>
  );
}

export function AccessOverview({
  accessGroups,
  catalog,
  summary,
}: {
  accessGroups: AccessGroupItem[];
  catalog: AccessCatalogPayload;
  summary: AccessSummaryPayload;
}) {
  const permissionMap = buildPermissionMap(catalog);
  const disabledWithAccess = summary.users.filter((user) => !user.is_active && (user.groups.length > 0 || user.queue_count > 0)).length;
  const groupsWithoutMembers = accessGroups.filter((group) => group.is_active && group.members.length === 0).length;
  const queuesWithoutMembers = summary.queues.filter((queue) => queue.is_active && queue.members_count === 0).length;
  const highRiskGrants = accessGroups.reduce(
    (count, group) => count + group.permissions.filter((code) => permissionMap.get(code)?.risk === "high").length,
    0,
  );
  const elevatedUsers = summary.users.filter((user) => ["admin", "support"].includes(user.actor_role)).length;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Версия каталога" value={catalog.version} />
        <MetricCard label="Пользователи" value={summary.users.length} />
        <MetricCard label="Группы доступа" value={accessGroups.length} />
        <MetricCard label="Очереди" value={summary.queues.length} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Формула доступа</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-semibold text-slate-950">Как считается доступ</p>
          <p className="mt-2 text-sm text-slate-500">Базовая роль + группы доступа + прямое членство в очередях = итоговый доступ</p>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <AuditFindingCard
          count={disabledWithAccess}
          description="Пользователи отключены, но по данным API всё ещё имеют группы или прямые очереди."
          title="Отключённые пользователи с доступом"
          tone={disabledWithAccess > 0 ? "warning" : "neutral"}
        />
        <AuditFindingCard
          count={groupsWithoutMembers}
          description="Активные группы без участников: проверьте, нужны ли эти правила."
          title="Группы без участников"
          tone={groupsWithoutMembers > 0 ? "warning" : "neutral"}
        />
        <AuditFindingCard
          count={queuesWithoutMembers}
          description="Активные очереди без прямых участников. Групповые назначения проверяются отдельно."
          title="Очереди без участников"
          tone={queuesWithoutMembers > 0 ? "warning" : "neutral"}
        />
        <AuditFindingCard
          count={highRiskGrants}
          description="Высокорисковые права, назначенные через группы доступа."
          title="Высокорисковые права"
          tone={highRiskGrants > 0 ? "danger" : "neutral"}
        />
        <AuditFindingCard
          count={elevatedUsers}
          description="Пользователи с ролями администратора или поддержки по текущей сводке."
          title="Администраторы и поддержка"
          tone={elevatedUsers > 0 ? "warning" : "neutral"}
        />
      </div>
    </div>
  );
}

export function QueuesAccessTable({ accessGroups, queues }: { accessGroups: AccessGroupItem[]; queues: AccessQueueItem[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selectedQueueId, setSelectedQueueId] = useState<number | null>(queues[0]?.queue_id ?? null);
  const filteredQueues = useMemo(() => filterQueues(queues, query, status), [query, queues, status]);
  const selectedQueue = queues.find((queue) => queue.queue_id === selectedQueueId) ?? filteredQueues[0] ?? null;
  const groupGrants = selectedQueue ? queueGrantsForQueue(accessGroups, selectedQueue.queue_id) : [];

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Очереди</CardTitle>
              <p className="text-sm text-slate-500">Ответ на вопрос: кто может попасть в очередь.</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Поиск очереди" value={query} />
              <Select aria-label="Фильтр очередей" onChange={(event) => setStatus(event.target.value)} value={status}>
                <option value="all">Все статусы</option>
                <option value="active">Активные</option>
                <option value="disabled">Отключённые</option>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {filteredQueues.length === 0 ? (
            <EmptyBlock description="Измените поиск или фильтр статуса." title="Очереди не найдены" />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Очередь</th>
                    <th className="px-5 py-3">Код</th>
                    <th className="px-5 py-3">Прямые участники</th>
                    <th className="px-5 py-3">Группы</th>
                    <th className="px-5 py-3">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredQueues.map((queue) => {
                    const grants = queueGrantsForQueue(accessGroups, queue.queue_id);
                    return (
                      <tr key={queue.queue_id}>
                        <td className="px-5 py-4 font-semibold text-slate-950">{queue.queue_name}</td>
                        <td className="px-5 py-4 font-mono text-xs text-slate-500">{queue.queue_code}</td>
                        <td className="px-5 py-4">{queue.members_count}</td>
                        <td className="px-5 py-4">{grants.length}</td>
                        <td className="px-5 py-4">
                          <Button
                            onClick={() => setSelectedQueueId(queue.queue_id)}
                            size="sm"
                            variant={selectedQueueId === queue.queue_id ? "primary" : "outline"}
                          >
                            {`Открыть очередь ${queue.queue_name}`}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border">
          <CardTitle>Кто может попасть в очередь</CardTitle>
          <p className="text-sm text-slate-500">{selectedQueue?.queue_name ?? "Очередь не выбрана"}</p>
        </CardHeader>
        <CardContent className="space-y-4 p-5">
          {selectedQueue ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-50 px-3 py-3">
                  <p className="text-xs text-slate-500">Прямые участники</p>
                  <p className="mt-1 text-xl font-semibold text-slate-950">{selectedQueue.members_count}</p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-3">
                  <p className="text-xs text-slate-500">Пользователи из групп</p>
                  <p className="mt-1 text-xl font-semibold text-slate-950">
                    {effectiveGroupUserCount(accessGroups, selectedQueue.queue_id)}
                  </p>
                </div>
              </div>
              <p className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-3 text-sm text-blue-900">
                Из API доступно только количество прямых участников, без списка логинов.
              </p>
              <section>
                <p className="mb-2 text-sm font-semibold text-slate-950">Группы с доступом</p>
                {groupGrants.length === 0 ? (
                  <EmptyBlock description="Групповых назначений для этой очереди нет." title="Группы не найдены" />
                ) : (
                  <div className="space-y-2">
                    {groupGrants.map((group) => (
                      <div className="rounded-lg border border-border px-3 py-3" key={group.group_id}>
                        <p className="font-semibold text-slate-950">{group.name}</p>
                        <p className="mt-1 font-mono text-xs text-slate-500">{group.code}</p>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : (
            <EmptyBlock description="Выберите очередь в таблице слева." title="Очередь не выбрана" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function RolesPermissionMatrix({ catalog }: { catalog: AccessCatalogPayload }) {
  const [query, setQuery] = useState("");
  const filteredGroups = filterPermissionGroups(catalog.groups, query);
  const roles = catalog.roles;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Матрица ролей</CardTitle>
            <p className="text-sm text-slate-500">Сравнение встроенных ролей только для чтения. Роли здесь не редактируются.</p>
          </div>
          <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Поиск права в матрице" value={query} />
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="sticky left-0 bg-slate-50 px-5 py-3">Право</th>
                {roles.map((role) => (
                  <th className="px-5 py-3" key={role.code}>
                    {role.label}
                    <span className="block font-mono text-[11px] normal-case text-slate-400">{role.code}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredGroups.flatMap((group) =>
                group.permissions.map((permission) => (
                  <tr key={permission.code}>
                    <td className="sticky left-0 min-w-[280px] bg-white px-5 py-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-950">{permission.label}</span>
                        <Badge tone={riskTone(permission.risk)}>{riskLabel(permission.risk)}</Badge>
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500">{permission.code}</p>
                      <p className="mt-1 text-xs text-slate-500">{group.label}</p>
                    </td>
                    {roles.map((role) => (
                      <td className="px-5 py-4 text-center" key={`${permission.code}:${role.code}`}>
                        {role.permissions.includes(permission.code) ? (
                          <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-600" />
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                    ))}
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

export function PermissionCatalogTab({ catalog }: { catalog: AccessCatalogPayload }) {
  const [query, setQuery] = useState("");
  const filteredGroups = filterPermissionGroups(catalog.groups, query);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Каталог прав</CardTitle>
            <p className="text-sm text-slate-500">Словарь прав: русское название, технический код, описание и риск.</p>
          </div>
          <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Поиск права или кода" value={query} />
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {filteredGroups.length === 0 ? (
          <EmptyBlock description="Измените поисковый запрос." title="Права не найдены" />
        ) : (
          <div className="divide-y divide-border">
            {filteredGroups.map((group) => (
              <section className="px-5 py-4" key={group.code}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-950">{group.label}</p>
                    <p className="font-mono text-xs text-slate-500">{group.code}</p>
                  </div>
                  <Badge tone="neutral">{group.permissions.length} прав</Badge>
                </div>
                <div className="mt-3 grid gap-3 xl:grid-cols-2">
                  {group.permissions.map((permission) => (
                    <div className="rounded-lg border border-border bg-white px-3 py-3" key={permission.code}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-slate-950">{permission.label}</p>
                        <Badge tone={riskTone(permission.risk)}>{riskLabel(permission.risk)}</Badge>
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500">{permission.code}</p>
                      <p className="mt-2 text-sm text-slate-500">{permission.description}</p>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function AccessAuditTab({
  audit,
  auditError,
  auditLoading,
}: {
  audit?: AccessAuditPayload;
  auditError?: Error | null;
  auditLoading: boolean;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border">
        <div className="flex items-start gap-3">
          <History className="mt-0.5 h-5 w-5 text-slate-500" />
          <div>
            <CardTitle>Аудит и журнал изменений</CardTitle>
            <p className="text-sm text-slate-500">Показываем только реальные записи `/api/web/admin/access/audit`.</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {auditLoading ? (
          <EmptyBlock description="Загружаем последние изменения RBAC." title="Загружаем аудит" />
        ) : auditError ? (
          <EmptyBlock description={auditError.message} title="Журнал недоступен" />
        ) : !audit || audit.items.length === 0 ? (
          <EmptyBlock description="Сервер не вернул записей. Фейковые события не показываем." title="Журнал изменений пока пуст" />
        ) : (
          <div className="divide-y divide-border">
            {audit.items.map((item) => (
              <div className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_220px_180px]" key={item.id}>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-slate-950">{item.action}</p>
                    <Badge tone="neutral">{`${item.entity_type} ${item.entity_id}`}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {item.actor_id} · {item.actor_role}
                  </p>
                </div>
                <p className="font-mono text-xs text-slate-500">{item.created_at}</p>
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <BookOpen className="h-4 w-4" />
                  Изменения сохранены в данных аудита
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
