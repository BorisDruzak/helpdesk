import { Wrench } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { type RegistrySelection } from "./registry-utils";

type Props = {
  issues: AdminRegistryPayload["data_quality"];
  suggestions: AdminRegistryPayload["suggestions"];
  onFix: (issue: AdminRegistryPayload["data_quality"][number]) => void;
  onSelect: (selection: RegistrySelection) => void;
};

export function RegistryQualityTab({ issues, onFix, onSelect, suggestions }: Props) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="space-y-3">
        <p className="text-sm font-semibold text-slate-950">Data-quality issues</p>
        {issues.length ? issues.map((issue) => (
          <div className="rounded-lg border border-border bg-white px-4 py-3" key={`${issue.kind}-${issue.object_id}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <Badge tone={issue.severity}>{issue.kind}</Badge>
                <p className="mt-3 font-semibold text-slate-950">{issue.title}</p>
                <p className="mt-1 text-sm text-slate-500">{issue.description}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!issue.device_id && !issue.person_id && !issue.binding_id && !issue.claim_id} onClick={() => {
                  if (issue.binding_id) onSelect({ kind: "binding", id: issue.binding_id });
                  else if (issue.claim_id) onSelect({ kind: "claim", id: issue.claim_id });
                  else if (issue.person_id) onSelect({ kind: "person", id: issue.person_id });
                  else if (issue.device_id) onSelect({ kind: "device", id: issue.device_id });
                }} size="sm" variant="outline">Открыть</Button>
                <Button leadingIcon={<Wrench className="h-4 w-4" />} onClick={() => onFix(issue)} size="sm">Исправить</Button>
              </div>
            </div>
          </div>
        )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Критичных пробелов нет.</p>}
      </section>
      <section className="space-y-3">
        <p className="text-sm font-semibold text-slate-950">Автоподсказки</p>
        {suggestions.length ? suggestions.map((suggestion) => (
          <div className="rounded-lg border border-border bg-white px-4 py-3" key={`${suggestion.kind}-${suggestion.object_id}`}>
            <Badge tone="info">{Math.round(suggestion.confidence * 100)}%</Badge>
            <p className="mt-3 font-semibold text-slate-950">{suggestion.title}</p>
            <p className="mt-1 text-sm text-slate-500">{suggestion.description}</p>
          </div>
        )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Новых подсказок нет.</p>}
      </section>
    </div>
  );
}
