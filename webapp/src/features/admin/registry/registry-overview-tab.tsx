import { AlertTriangle, ArrowUpRight } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { StatTile } from "../../../components/ui/stat-tile";
import type { AdminRegistryPayload } from "../api";
import { statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  registry: AdminRegistryPayload;
  onSelect: (selection: RegistrySelection) => void;
  onFixIssue: (issue: AdminRegistryPayload["data_quality"][number]) => void;
};

export function RegistryOverviewTab({ onFixIssue, onSelect, registry }: Props) {
  const summary = registry.summary;
  const actionItems = [
    ...registry.registration_claims.filter((claim) => ["pending_user_confirmation", "pending_admin_review", "conflict", "user_confirmed", "self_reported"].includes(claim.status)).slice(0, 6).map((claim) => ({
      id: claim.claim_id,
      title: claim.person_name ?? claim.device_id,
      description: `${claim.status} · ${claim.relationship_type}`,
      tone: statusTone(claim.status),
      open: () => onSelect({ kind: "claim", id: claim.claim_id }),
    })),
    ...registry.data_quality.slice(0, 8).map((issue) => ({
      id: `${issue.kind}-${issue.object_id}`,
      title: issue.title,
      description: issue.description,
      tone: issue.severity,
      open: () => onFixIssue(issue),
    })),
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatTile label="Устройств всего" value={String(summary.devices_total ?? summary.assets)} helper="PC assets in registry" />
        <StatTile label="Зарегистрировано" value={String(summary.devices_registered ?? summary.active_bindings)} helper="Есть активная связь" />
        <StatTile label="Без пользователя" value={String(summary.devices_unregistered ?? summary.unregistered_devices)} helper="Требуют действия" />
        <StatTile label="Pending claims" value={String(summary.claims_pending ?? summary.registrations_pending)} helper="Регистрация устройства" />
        <StatTile label="Account sessions" value={String(summary.sessions_active ?? 0)} helper="Активные requester sessions" />
        <StatTile label="Конфликты" value={String(summary.claims_conflict ?? summary.registrations_conflicts)} helper="Нужна ручная проверка" />
        <StatTile label="Active bindings" value={String(summary.bindings_active ?? summary.active_bindings)} helper="Primary/shared/responsible" />
        <StatTile label="Shared devices" value={String(summary.shared_devices ?? 0)} helper="Общие рабочие места" />
        <StatTile label="Other-account" value={String(summary.other_account_requests ?? 0)} helper="Заявки на вход" />
        <StatTile label="Качество данных" value={String(summary.quality_issues ?? summary.data_quality_issues)} helper="Actionable issues" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Требует действия
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {actionItems.length ? actionItems.map((item) => (
            <div className="flex flex-col gap-3 rounded-lg border border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between" key={item.id}>
              <div>
                <div className="flex items-center gap-2">
                  <Badge tone={item.tone}>{item.title}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-600">{item.description}</p>
              </div>
              <Button leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={item.open} size="sm" variant="outline">
                Открыть
              </Button>
            </div>
          )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Очередь действий пуста.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
