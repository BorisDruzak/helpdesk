import { useQuery } from "@tanstack/react-query";
import { ExternalLink, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "../../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { fetchAccessSummary, type AccessGroupItem } from "../../access-control/api";

function AccessMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-slate-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function AccessGroupCard({ group }: { group: AccessGroupItem }) {
  return (
    <article className="rounded-lg border border-border bg-white px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-950">{group.name}</h3>
          <p className="mt-1 font-mono text-xs text-slate-500">{group.code}</p>
        </div>
        <Badge tone={group.is_active ? "success" : "neutral"}>{group.is_active ? "active" : "disabled"}</Badge>
      </div>
      {group.description ? <p className="mt-3 text-sm text-slate-600">{group.description}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
        <span className="rounded-pill bg-slate-100 px-3 py-1">{group.permissions.length} permissions</span>
        <span className="rounded-pill bg-slate-100 px-3 py-1">{group.members.length} members</span>
        <span className="rounded-pill bg-slate-100 px-3 py-1">{group.queue_grants.length} queues</span>
      </div>
    </article>
  );
}

export function RegistryAccessGroupsTab() {
  const summaryQuery = useQuery({
    queryKey: ["admin-access-summary"],
    queryFn: fetchAccessSummary,
    retry: false,
  });

  const summary = summaryQuery.data ?? null;
  const accessGroups = summary?.access_groups ?? [];
  const activeGroups = accessGroups.filter((group) => group.is_active).length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="gap-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>Группы доступа</CardTitle>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                Registry показывает RBAC-группы как контекст effective identity и аудитории. Редактирование permissions, members и queue grants остаётся в каноническом Access Control.
              </p>
            </div>
            <Link
              className="inline-flex h-9 items-center justify-center gap-2 rounded-pill border border-border bg-white px-3 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
              to="/app/admin/access"
            >
              <ExternalLink className="h-4 w-4" />
              Открыть RBAC-редактор
            </Link>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {summaryQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем сводку RBAC...</p> : null}
          {summaryQuery.isError ? (
            <p className="text-sm text-rose-600">
              {summaryQuery.error instanceof Error ? summaryQuery.error.message : "Не удалось загрузить группы доступа."}
            </p>
          ) : null}
          {summary ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <AccessMetric label="Всего групп" value={accessGroups.length} />
                <AccessMetric label="Активные" value={activeGroups} />
                <AccessMetric label="UI users" value={summary.users.length} />
                <AccessMetric label="Очереди" value={summary.queues.length} />
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>
                    Access groups grant permissions and queue access. Audience groups may use them as targeting facts, but must not grant RBAC permissions.
                  </p>
                </div>
              </div>
              {summary.notes.length > 0 ? (
                <div className="rounded-lg border border-border bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  {summary.notes.map((note) => <p key={note}>{note}</p>)}
                </div>
              ) : null}
              <div className="grid gap-3 xl:grid-cols-2">
                {accessGroups.length ? (
                  accessGroups.map((group) => <AccessGroupCard group={group} key={group.group_id} />)
                ) : (
                  <p className="rounded-lg border border-dashed border-border px-4 py-8 text-sm text-slate-500">Группы доступа ещё не созданы.</p>
                )}
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
