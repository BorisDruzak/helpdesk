import { PlugZap, ShieldCheck } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import type { ProviderSummary } from "./types";
import { PROVIDER_GROUP_LABELS, readinessTone } from "./labels";

type CapabilityProviderCardsProps = {
  providers: ProviderSummary[];
  onSelectProvider: (providerId: string) => void;
};

function statusLabel(provider: ProviderSummary): string {
  if (!provider.config && provider.provider_type === "server_connector") {
    return "integration_not_configured";
  }
  return provider.config?.status ?? "available";
}

export function CapabilityProviderCards({ providers, onSelectProvider }: CapabilityProviderCardsProps) {
  const grouped = providers.reduce<Record<string, ProviderSummary[]>>((acc, provider) => {
    const target = provider.execution_targets[0] ?? "unknown";
    acc[target] = [...(acc[target] ?? []), provider];
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      {Object.entries(grouped).map(([target, items]) => (
        <section key={target} className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{PROVIDER_GROUP_LABELS[target] ?? target}</h2>
            <p className="text-sm text-slate-500">Провайдеры и модули, которые отдают capabilities этого типа.</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {items.map((provider) => {
              const status = statusLabel(provider);
              return (
                <Card key={provider.provider_id}>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <PlugZap className="h-5 w-5 text-brand-700" />
                          {provider.provider_id}
                        </CardTitle>
                        <CardDescription>{provider.provider_type}</CardDescription>
                      </div>
                      <Badge tone={readinessTone(status)}>{status}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-slate-400">Capabilities</p>
                        <p className="mt-1 font-semibold text-slate-950">{provider.capability_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Evidence</p>
                        <p className="mt-1 font-semibold text-slate-950">{provider.evidence_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">High risk</p>
                        <p className="mt-1 font-semibold text-slate-950">{provider.high_risk_count}</p>
                      </div>
                    </div>
                    <div className="rounded-[0.9rem] border border-border bg-surface-subtle px-4 py-3 text-sm text-slate-600">
                      {provider.integration_key ? (
                        <p>Integration: {provider.integration_key}</p>
                      ) : (
                        <p>Без внешней интеграции.</p>
                      )}
                      {provider.config ? (
                        <p className="mt-1 flex items-center gap-2">
                          <ShieldCheck className="h-4 w-4 text-emerald-600" />
                          Credentials: {provider.config.credential_refs.length}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => onSelectProvider(provider.provider_id)} size="sm" variant="outline">
                        Capabilities
                      </Button>
                      {provider.provider_type === "server_connector" ? (
                        <a href="/app/admin/capabilities?tab=providers">
                          <Button size="sm" variant="ghost">Открыть настройки</Button>
                        </a>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
