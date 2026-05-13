import { X } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import type { CapabilityDescriptor } from "./types";
import { label, readinessTone, riskTone, targetTone } from "./labels";

type CapabilityDetailDrawerProps = {
  capability: CapabilityDescriptor | null;
  onClose: () => void;
};

function JsonBlock({ value }: { value: unknown }) {
  if (!value || (typeof value === "object" && !Array.isArray(value) && !Object.keys(value as Record<string, unknown>).length)) {
    return <p className="text-sm text-slate-500">Не задано.</p>;
  }
  return (
    <pre className="max-h-72 overflow-auto rounded-[0.75rem] bg-slate-950 p-4 text-xs leading-5 text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function DetailField({ label: title, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">{title}</p>
      <p className="mt-1 break-words text-sm text-slate-800">
        {typeof value === "boolean" ? (value ? "Да" : "Нет") : String(value ?? "Не задано")}
      </p>
    </div>
  );
}

function Section({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="space-y-3 border-t border-border pt-5">
      <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
      {children}
    </section>
  );
}

export function CapabilityDetailDrawer({ capability, onClose }: CapabilityDetailDrawerProps) {
  if (!capability) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30" role="dialog" aria-modal="true">
      <button aria-label="Закрыть drawer" className="absolute inset-0 cursor-default" onClick={onClose} type="button" />
      <aside className="relative flex h-full w-full max-w-3xl flex-col overflow-hidden bg-white shadow-2xl">
        <header className="border-b border-border px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Capability detail</p>
              <h2 className="mt-2 break-words text-2xl font-semibold tracking-tight text-slate-950">
                {capability.title || capability.id}
              </h2>
              <p className="mt-2 break-all text-xs text-slate-500">{capability.id}</p>
            </div>
            <Button aria-label="Закрыть" onClick={onClose} size="icon" variant="ghost">
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone={targetTone(capability.execution_target)}>{label(capability.execution_target)}</Badge>
            <Badge tone={riskTone(capability.risk_level)}>{capability.risk_level ?? "unknown"}</Badge>
            <Badge tone={readinessTone(capability.readiness)}>{capability.readiness ?? "unknown"}</Badge>
            {capability.evidence?.produces_evidence ? <Badge tone="success">evidence</Badge> : null}
          </div>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <Section title="Overview">
            <p className="text-sm leading-6 text-slate-600">{capability.description || "Описание capability не передано."}</p>
            <div className="grid gap-4 md:grid-cols-2">
              <DetailField label="Provider" value={capability.provider_id} />
              <DetailField label="Provider type" value={capability.provider_type} />
              <DetailField label="Source" value={capability.source} />
              <DetailField label="Aliases" value={capability.aliases?.join(", ")} />
            </div>
          </Section>

          <Section title="Execution">
            <div className="grid gap-4 md:grid-cols-2">
              <DetailField label="Где выполняется" value={label(capability.execution_target)} />
              <DetailField label="Requires device" value={capability.requires_device} />
              <DetailField label="Requires agent online" value={capability.requires_agent_online} />
              <DetailField label="Supports auto-install" value={capability.supports_auto_install} />
              <DetailField label="Requires integration" value={capability.requires_integration} />
              <DetailField label="Integration key" value={capability.integration_key} />
              <DetailField label="Install required on agent" value={capability.install_required_on_agent} />
              <DetailField label="Platforms" value={capability.platforms?.join(", ") || "any"} />
            </div>
          </Section>

          <Section title="Safety">
            <div className="grid gap-4 md:grid-cols-2">
              <DetailField label="Tool kind" value={capability.tool_kind} />
              <DetailField label="Risk level" value={capability.risk_level} />
              <DetailField label="Side effects" value={capability.side_effects} />
              <DetailField label="Requires consent" value={capability.requires_consent} />
              <DetailField label="Readiness reason" value={capability.reason} />
              <DetailField label="Reason code" value={capability.reason_code} />
            </div>
          </Section>

          <Section title="Contract">
            <div className="grid gap-4 lg:grid-cols-3">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Params schema</p>
                <JsonBlock value={capability.params_schema} />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Output schema</p>
                <JsonBlock value={capability.output_schema} />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Output contract</p>
                <JsonBlock value={capability.output_contract} />
              </div>
            </div>
          </Section>

          <Section title="Evidence">
            <div className="grid gap-4 md:grid-cols-2">
              <DetailField label="Produces evidence" value={capability.evidence?.produces_evidence} />
              <DetailField label="Kind" value={capability.evidence?.kind} />
              <DetailField label="Domain" value={capability.evidence?.domain} />
              <DetailField label="Perspective" value={capability.evidence?.perspective} />
              <DetailField label="Passport eligible" value={capability.evidence?.passport_eligible} />
              <DetailField label="Summary template" value={capability.evidence?.summary_template} />
            </div>
          </Section>

          <Section title="Artifacts">
            <div className="grid gap-4 md:grid-cols-2">
              <DetailField label="May produce artifacts" value={capability.artifacts?.may_produce_artifacts} />
              <DetailField label="Artifact kinds" value={capability.artifacts?.artifact_kinds?.join(", ")} />
            </div>
          </Section>

          <Section title="Where used">
            <p className="rounded-[0.8rem] border border-dashed border-border bg-surface-subtle px-4 py-3 text-sm text-slate-500">
              Where-used API не подключён в MVP. Playbooks и Diagnostic Center уже используют этот capability id через существующие catalogs.
            </p>
          </Section>

          <details className="rounded-[0.9rem] border border-border bg-white px-4 py-3">
            <summary className="cursor-pointer text-sm font-semibold text-slate-800">Расширенные данные</summary>
            <div className="mt-3">
              <JsonBlock value={capability} />
            </div>
          </details>
        </div>
      </aside>
    </div>
  );
}
