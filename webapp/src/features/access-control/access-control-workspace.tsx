import { useQuery } from "@tanstack/react-query";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "../../components/ui/button";
import { PageHeading } from "../../components/ui/page-heading";
import { Tabs } from "../../components/ui/tabs";
import { fetchEffectiveAccess, type AccessAuditPayload, type AccessCatalogPayload, type AccessGroupItem, type AccessSummaryPayload, type AccessUserItem } from "./api";
import { AccessAuditTab, AccessOverview, PermissionCatalogTab, QueuesAccessTable, RolesPermissionMatrix } from "./access-reference";
import { GroupsAccessPanel } from "./access-groups";
import { UsersAccessTable } from "./access-users";
import { ACCESS_TABS, type AccessTab } from "./model";

type AccessControlWorkspaceProps = {
  accessGroups: AccessGroupItem[];
  audit?: AccessAuditPayload;
  auditError?: Error | null;
  auditLoading: boolean;
  catalog: AccessCatalogPayload;
  onGroupChange: (group: AccessGroupItem) => void;
  onRefresh: () => void;
  summary: AccessSummaryPayload;
};

function summaryNoteLabel(note: string): string {
  if (note === "Access groups are enabled; effective access is role defaults + group grants + direct queue membership.") {
    return "Группы доступа включены: итоговый доступ складывается из базовой роли, групповых назначений и прямого членства в очередях.";
  }
  if (note === "DB-backed users/queues are temporarily unavailable.") {
    return "Пользователи или очереди из БД временно недоступны.";
  }
  return note;
}

export function AccessControlWorkspace({
  accessGroups,
  audit,
  auditError,
  auditLoading,
  catalog,
  onGroupChange,
  onRefresh,
  summary,
}: AccessControlWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<AccessTab>("overview");
  const [selectedUser, setSelectedUser] = useState<AccessUserItem | null>(null);

  useEffect(() => {
    setSelectedUser((current) => current ?? summary.users[0] ?? null);
  }, [summary.users]);

  const effectiveQuery = useQuery({
    enabled: Boolean(selectedUser),
    queryFn: () =>
      fetchEffectiveAccess({
        actorRole: selectedUser?.actor_role ?? "user",
        userLogin: selectedUser?.user_login ?? "",
      }),
    queryKey: ["admin-access-effective", selectedUser?.user_login, selectedUser?.actor_role],
    retry: false,
  });

  const tabItems = useMemo(
    () =>
      ACCESS_TABS.map((tab) => ({
        ...tab,
        count:
          tab.value === "users"
            ? summary.users.length
            : tab.value === "groups"
              ? accessGroups.length
              : tab.value === "queues"
                ? summary.queues.length
                : undefined,
      })),
    [accessGroups.length, summary.queues.length, summary.users.length],
  );

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <PageHeading
          description="Рабочее место администратора для поиска пользователя, объяснения итогового доступа, безопасного редактирования групп и аудита рискованных назначений."
          eyebrow="Рабочее место RBAC"
          title="Контроль доступа"
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button leadingIcon={<RefreshCw className="h-4 w-4" />} onClick={onRefresh} variant="outline">
            Обновить
          </Button>
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700">
            <ShieldCheck className="h-4 w-4" />
            Русская локализация
          </div>
        </div>
      </div>

      <Tabs
        className="rounded-lg"
        items={tabItems}
        onValueChange={(value) => setActiveTab(value as AccessTab)}
        value={activeTab}
      />

      {summary.notes.length > 0 ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {summary.notes.map(summaryNoteLabel).join(" ")}
        </div>
      ) : null}

      {activeTab === "overview" ? (
        <AccessOverview accessGroups={accessGroups} catalog={catalog} summary={summary} />
      ) : null}
      {activeTab === "users" ? (
        <UsersAccessTable
          accessGroups={accessGroups}
          catalog={catalog}
          effective={effectiveQuery.data}
          effectiveLoading={effectiveQuery.isLoading}
          onSelectUser={setSelectedUser}
          selectedUser={selectedUser}
          users={summary.users}
        />
      ) : null}
      {activeTab === "groups" ? (
        <GroupsAccessPanel
          accessGroups={accessGroups}
          catalog={catalog}
          onGroupChange={onGroupChange}
          queues={summary.queues}
          users={summary.users}
        />
      ) : null}
      {activeTab === "queues" ? (
        <QueuesAccessTable accessGroups={accessGroups} queues={summary.queues} />
      ) : null}
      {activeTab === "roles" ? <RolesPermissionMatrix catalog={catalog} /> : null}
      {activeTab === "catalog" ? <PermissionCatalogTab catalog={catalog} /> : null}
      {activeTab === "audit" ? (
        <AccessAuditTab audit={audit} auditError={auditError} auditLoading={auditLoading} />
      ) : null}
    </section>
  );
}
