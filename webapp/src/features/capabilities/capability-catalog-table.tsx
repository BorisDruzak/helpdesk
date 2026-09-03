import { ExternalLink, FlaskConical, PackageOpen } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import type { CapabilityDescriptor } from "./types";
import { label, readinessTone, riskTone, targetTone } from "./labels";

type CapabilityCatalogTableProps = {
  capabilities: CapabilityDescriptor[];
  isLoading?: boolean;
  onOpen: (capability: CapabilityDescriptor) => void;
  onReadiness: (capability: CapabilityDescriptor) => void;
};

export function CapabilityCatalogTable({
  capabilities,
  isLoading = false,
  onOpen,
  onReadiness,
}: CapabilityCatalogTableProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-slate-500">Загружаем каталог capabilities...</CardContent>
      </Card>
    );
  }

  if (!capabilities.length) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <PackageOpen className="mx-auto h-9 w-9 text-slate-300" />
          <p className="mt-4 font-semibold text-slate-950">Capabilities пока не найдены</p>
          <p className="mt-2 text-sm text-slate-500">
            Проверьте module registry и diagnostics providers.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="overflow-x-auto px-0 pb-0">
        <table className="min-w-full divide-y divide-border text-left text-sm">
          <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            <tr>
              <th className="px-5 py-3">Capability</th>
              <th className="px-5 py-3">Execution target</th>
              <th className="px-5 py-3">Provider</th>
              <th className="px-5 py-3">Kind</th>
              <th className="px-5 py-3">Risk</th>
              <th className="px-5 py-3">Evidence</th>
              <th className="px-5 py-3">Platforms</th>
              <th className="px-5 py-3">Readiness</th>
              <th className="px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {capabilities.map((capability) => (
              <tr key={capability.id} className="align-top hover:bg-brand-50/30">
                <td className="max-w-[22rem] px-5 py-4">
                  <button
                    className="text-left"
                    onClick={() => onOpen(capability)}
                    type="button"
                  >
                    <span className="block font-semibold text-slate-950">{capability.title || capability.id}</span>
                    <span className="mt-1 block break-all text-xs text-slate-500">{capability.id}</span>
                  </button>
                </td>
                <td className="px-5 py-4">
                  <Badge tone={targetTone(capability.execution_target)}>{label(capability.execution_target)}</Badge>
                </td>
                <td className="px-5 py-4">
                  <span className="font-medium text-slate-800">{capability.provider_id ?? "unknown"}</span>
                  {capability.integration_key ? (
                    <span className="mt-1 block text-xs text-slate-500">{capability.integration_key}</span>
                  ) : null}
                </td>
                <td className="px-5 py-4 text-slate-600">{capability.tool_kind ?? "diagnostic"}</td>
                <td className="px-5 py-4">
                  <Badge tone={riskTone(capability.risk_level)}>{capability.risk_level ?? "unknown"}</Badge>
                </td>
                <td className="px-5 py-4">
                  {capability.evidence?.produces_evidence ? (
                    <div className="space-y-1">
                      <Badge tone="success">produces evidence</Badge>
                      <p className="text-xs text-slate-500">{capability.evidence.kind ?? "evidence"}</p>
                    </div>
                  ) : (
                    <Badge tone="neutral">no evidence</Badge>
                  )}
                </td>
                <td className="px-5 py-4 text-slate-500">
                  {capability.platforms?.length ? capability.platforms.join(", ") : "any"}
                </td>
                <td className="px-5 py-4">
                  <Badge tone={readinessTone(capability.readiness)}>{capability.readiness ?? "unknown"}</Badge>
                </td>
                <td className="px-5 py-4">
                  <div className="flex min-w-[11rem] flex-wrap gap-2">
                    <Button onClick={() => onOpen(capability)} size="sm" variant="outline">
                      Открыть
                    </Button>
                    <Button
                      leadingIcon={<FlaskConical className="h-4 w-4" />}
                      onClick={() => onReadiness(capability)}
                      size="sm"
                      variant="ghost"
                    >
                      Readiness
                    </Button>
                    {capability.source === "managed_module" || capability.execution_target === "agent_managed_module" ? (
                      <Button
                        leadingIcon={<ExternalLink className="h-4 w-4" />}
                        onClick={() => navigate("/app/admin/capabilities")}
                        size="sm"
                        variant="ghost"
                      >
                        Endpoint
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
