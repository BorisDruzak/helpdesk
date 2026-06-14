import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { AccessControlWorkspace } from "../../features/access-control/access-control-workspace";
import {
  fetchAccessAudit,
  fetchAccessCatalog,
  fetchAccessSummary,
  type AccessGroupItem,
} from "../../features/access-control/api";

function AccessPageState({
  description,
  title,
  tone = "neutral",
}: {
  description: string;
  title: string;
  tone?: "neutral" | "danger";
}) {
  const Icon = tone === "danger" ? ShieldAlert : Activity;
  return (
    <section className="flex min-h-[420px] items-center justify-center px-4 py-12">
      <div className="surface-panel max-w-xl px-8 py-10 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
          <Icon className={tone === "danger" ? "h-5 w-5 text-rose-600" : "h-5 w-5 animate-pulse"} />
        </div>
        <h1 className="mt-4 text-xl font-semibold text-slate-950">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
      </div>
    </section>
  );
}

function updateGroupList(groups: AccessGroupItem[], nextGroup: AccessGroupItem) {
  const exists = groups.some((group) => group.group_id === nextGroup.group_id);
  const nextGroups = exists
    ? groups.map((group) => (group.group_id === nextGroup.group_id ? nextGroup : group))
    : [...groups, nextGroup];
  return nextGroups.sort((left, right) => left.code.localeCompare(right.code));
}

export function AdminAccessPage() {
  const queryClient = useQueryClient();
  const [accessGroups, setAccessGroups] = useState<AccessGroupItem[]>([]);

  const catalogQuery = useQuery({
    queryFn: fetchAccessCatalog,
    queryKey: ["admin-access-catalog"],
    retry: false,
  });

  const summaryQuery = useQuery({
    queryFn: fetchAccessSummary,
    queryKey: ["admin-access-summary"],
    retry: false,
  });

  const auditQuery = useQuery({
    queryFn: fetchAccessAudit,
    queryKey: ["admin-access-audit"],
    retry: false,
  });

  useEffect(() => {
    if (summaryQuery.data) {
      setAccessGroups(summaryQuery.data.access_groups);
    }
  }, [summaryQuery.data]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-access-catalog"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-access-summary"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-access-audit"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-access-effective"] });
  };

  const handleGroupChange = (group: AccessGroupItem) => {
    setAccessGroups((current) => updateGroupList(current, group));
    void queryClient.invalidateQueries({ queryKey: ["admin-access-summary"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-access-audit"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-access-effective"] });
  };

  if (catalogQuery.isLoading || summaryQuery.isLoading) {
    return <AccessPageState description="Собираем роли, пользователей, группы, очереди и каталог прав." title="Загружаем RBAC" />;
  }

  if (catalogQuery.isError || summaryQuery.isError || !catalogQuery.data || !summaryQuery.data) {
    const message =
      catalogQuery.error instanceof Error
        ? catalogQuery.error.message
        : summaryQuery.error instanceof Error
          ? summaryQuery.error.message
          : "Не удалось загрузить данные контроля доступа.";
    return <AccessPageState description={message} title="RBAC недоступен" tone="danger" />;
  }

  return (
    <AccessControlWorkspace
      accessGroups={accessGroups}
      audit={auditQuery.data}
      auditError={auditQuery.error instanceof Error ? auditQuery.error : null}
      auditLoading={auditQuery.isLoading}
      catalog={catalogQuery.data}
      onGroupChange={handleGroupChange}
      onRefresh={refresh}
      summary={summaryQuery.data}
    />
  );
}
