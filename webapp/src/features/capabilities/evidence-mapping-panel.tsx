import { CheckCircle2, Eye } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import type { CapabilityDescriptor, EvidenceMappingRow } from "./types";

type EvidenceMappingPanelProps = {
  capabilities: CapabilityDescriptor[];
  onOpenCapability: (capability: CapabilityDescriptor) => void;
};

function mappingStatus(capability: CapabilityDescriptor): EvidenceMappingRow["mapping_status"] {
  if (!capability.evidence?.produces_evidence) {
    return "missing";
  }
  if (capability.evidence.status_mapping || capability.evidence.severity_mapping || capability.evidence.summary_template) {
    return "configured";
  }
  if (capability.evidence.kind && capability.evidence.domain && capability.evidence.perspective) {
    return "inferred";
  }
  return "read-only";
}

function statusTone(status: EvidenceMappingRow["mapping_status"]) {
  if (status === "configured") {
    return "success" as const;
  }
  if (status === "inferred") {
    return "info" as const;
  }
  if (status === "missing") {
    return "warning" as const;
  }
  if (status === "invalid") {
    return "danger" as const;
  }
  return "neutral" as const;
}

export function EvidenceMappingPanel({ capabilities, onOpenCapability }: EvidenceMappingPanelProps) {
  const rows = useMemo(
    () =>
      capabilities
        .filter((capability) => capability.evidence?.produces_evidence || capability.output_contract)
        .map((capability) => ({ capability, mapping_status: mappingStatus(capability) })),
    [capabilities],
  );
  const [selectedId, setSelectedId] = useState(rows[0]?.capability.id ?? "");
  const selected = rows.find((row) => row.capability.id === selectedId) ?? rows[0] ?? null;

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Evidence Mapping</CardTitle>
          <CardDescription>
            Read-only карта того, как capabilities превращаются в diagnostic evidence. Persisted editing не включён в MVP.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto px-0 pb-0">
          <table className="min-w-full divide-y divide-border text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
              <tr>
                <th className="px-5 py-3">Capability</th>
                <th className="px-5 py-3">Evidence kind</th>
                <th className="px-5 py-3">Domain</th>
                <th className="px-5 py-3">Perspective</th>
                <th className="px-5 py-3">Passport</th>
                <th className="px-5 py-3">Mapping status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-white">
              {rows.map((row) => (
                <tr
                  className="cursor-pointer hover:bg-brand-50/30"
                  key={row.capability.id}
                  onClick={() => setSelectedId(row.capability.id)}
                >
                  <td className="px-5 py-4">
                    <p className="font-semibold text-slate-950">{row.capability.title}</p>
                    <p className="mt-1 break-all text-xs text-slate-500">{row.capability.id}</p>
                  </td>
                  <td className="px-5 py-4 text-slate-600">{row.capability.evidence?.kind ?? "Не задано"}</td>
                  <td className="px-5 py-4 text-slate-600">{row.capability.evidence?.domain ?? "Не задано"}</td>
                  <td className="px-5 py-4 text-slate-600">{row.capability.evidence?.perspective ?? "Не задано"}</td>
                  <td className="px-5 py-4">
                    <Badge tone={row.capability.evidence?.passport_eligible ? "success" : "neutral"}>
                      {row.capability.evidence?.passport_eligible ? "eligible" : "no"}
                    </Badge>
                  </td>
                  <td className="px-5 py-4">
                    <Badge tone={statusTone(row.mapping_status)}>{row.mapping_status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length ? (
            <div className="px-6 py-10 text-center text-sm text-slate-500">Evidence-producing capabilities не найдены.</div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mapping preview</CardTitle>
          <CardDescription>
            Превью использует metadata из descriptor. Сохранение declarative mapping появится после persisted mapping.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {selected ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge tone={statusTone(selected.mapping_status)}>{selected.mapping_status}</Badge>
                <Badge tone="neutral">{selected.capability.evidence?.kind ?? "kind?"}</Badge>
                <Badge tone="neutral">{selected.capability.evidence?.perspective ?? "perspective?"}</Badge>
              </div>
              <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-4 py-4 text-sm text-slate-700">
                <p className="flex items-center gap-2 font-semibold text-slate-950">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  {selected.capability.title}
                </p>
                <p className="mt-2">
                  Evidence status: <span className="font-medium">inferred from output/status fields</span>
                </p>
                <p className="mt-1">
                  Severity: <span className="font-medium">inferred or unknown</span>
                </p>
                <p className="mt-1">
                  Summary: {selected.capability.evidence?.summary_template ?? "будет собран из output summary/result"}
                </p>
              </div>
              <Button leadingIcon={<Eye className="h-4 w-4" />} onClick={() => onOpenCapability(selected.capability)} variant="outline">
                Открыть capability
              </Button>
              <p className="rounded-[0.8rem] border border-dashed border-border bg-white px-4 py-3 text-sm text-slate-500">
                Редактирование mapping будет доступно после включения persisted mapping.
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">Выберите capability с evidence metadata.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
