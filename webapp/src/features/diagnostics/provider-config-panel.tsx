import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlugZap, Save, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Select } from "../../components/ui/select";
import { cn } from "../../shared/ui/cn";
import {
  listDiagnosticProviderConfigs,
  upsertDiagnosticProviderConfig,
  type DiagnosticProviderConfig,
} from "./api";

type ProviderConfigDraft = {
  providerId: string;
  providerType: string;
  integrationKey: string;
  enabled: boolean;
  configText: string;
  credentialKey: string;
  secretRef: string;
  credentialStatus: string;
};

const DEFAULT_DRAFT: ProviderConfigDraft = {
  providerId: "zabbix_connector",
  providerType: "server_connector",
  integrationKey: "zabbix",
  enabled: true,
  configText: '{\n  "api_url": "https://zabbix.example/api_jsonrpc.php",\n  "mappings": {}\n}',
  credentialKey: "api_token",
  secretRef: "",
  credentialStatus: "missing",
};

function statusTone(value: string): "neutral" | "brand" | "success" | "warning" | "danger" | "info" {
  if (["ready", "configured", "available"].includes(value)) {
    return "success";
  }
  if (["credentials_missing", "degraded"].includes(value)) {
    return "warning";
  }
  if (["disabled", "failed"].includes(value)) {
    return "danger";
  }
  return "neutral";
}

function draftFromConfig(config: DiagnosticProviderConfig | null): ProviderConfigDraft {
  if (!config) {
    return DEFAULT_DRAFT;
  }
  const firstCredential = config.credential_refs[0];
  return {
    providerId: config.provider_id,
    providerType: config.provider_type || "server_connector",
    integrationKey: config.integration_key ?? "",
    enabled: config.enabled,
    configText: JSON.stringify(config.config ?? {}, null, 2),
    credentialKey: firstCredential?.credential_key ?? "api_token",
    secretRef: "",
    credentialStatus: firstCredential?.status ?? "missing",
  };
}

export function DiagnosticProviderConfigPanel() {
  const queryClient = useQueryClient();
  const [selectedProviderId, setSelectedProviderId] = useState(DEFAULT_DRAFT.providerId);
  const [draft, setDraft] = useState<ProviderConfigDraft>(DEFAULT_DRAFT);
  const [formError, setFormError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const configsQuery = useQuery({
    queryKey: ["diagnostic-provider-configs"],
    queryFn: listDiagnosticProviderConfigs,
    retry: false,
  });

  const configs = configsQuery.data ?? [];
  const selectedConfig = useMemo(
    () => configs.find((config) => config.provider_id === selectedProviderId) ?? null,
    [configs, selectedProviderId],
  );

  useEffect(() => {
    setDraft(draftFromConfig(selectedConfig));
  }, [selectedConfig]);

  const saveMutation = useMutation({
    mutationFn: () => {
      let parsedConfig: Record<string, unknown>;
      try {
        parsedConfig = JSON.parse(draft.configText || "{}") as Record<string, unknown>;
      } catch {
        throw new Error("Config должен быть валидным JSON.");
      }
      const credentialRefs = draft.secretRef.trim()
        ? [
            {
              credential_key: draft.credentialKey.trim() || "api_token",
              secret_ref: draft.secretRef.trim(),
              status: draft.credentialStatus || "ready",
            },
          ]
        : draft.credentialStatus
          ? [
              {
                credential_key: draft.credentialKey.trim() || "api_token",
                secret_ref: "",
                status: draft.credentialStatus,
              },
            ]
          : [];
      return upsertDiagnosticProviderConfig(draft.providerId.trim(), {
        provider_type: draft.providerType.trim() || "server_connector",
        integration_key: draft.integrationKey.trim() || null,
        enabled: draft.enabled,
        config: parsedConfig,
        credential_refs: credentialRefs,
      });
    },
    onMutate: () => {
      setFormError(null);
      setSavedMessage(null);
    },
    onError: (error) => {
      setFormError(error instanceof Error ? error.message : "Не удалось сохранить provider config.");
    },
    onSuccess: async (config) => {
      setSavedMessage(`Provider config сохранён: ${config.provider_id}`);
      setSelectedProviderId(config.provider_id);
      await queryClient.invalidateQueries({ queryKey: ["diagnostic-provider-configs"] });
    },
  });

  return (
    <Card id="diagnostic-provider-configs">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PlugZap className="h-5 w-5 text-brand-700" />
          Diagnostic provider configs
        </CardTitle>
        <CardDescription>
          Admin-safe настройка server_connector providers. Секреты сохраняются как refs и в ответах редактируются.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5 xl:grid-cols-[minmax(16rem,0.8fr)_minmax(0,1.2fr)]">
        <div className="space-y-2">
          {configsQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем providers...</p> : null}
          {configsQuery.isError ? (
            <p className="rounded-[0.8rem] border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {configsQuery.error instanceof Error
                ? configsQuery.error.message
                : "Не удалось загрузить diagnostic provider configs."}
            </p>
          ) : null}
          <button
            className={cn(
              "w-full rounded-[1rem] border px-4 py-4 text-left",
              selectedProviderId === DEFAULT_DRAFT.providerId && !selectedConfig
                ? "border-brand-200 bg-brand-50"
                : "border-border bg-white",
            )}
            onClick={() => {
              setSelectedProviderId(DEFAULT_DRAFT.providerId);
              setDraft(DEFAULT_DRAFT);
            }}
            type="button"
          >
            <p className="font-semibold text-slate-950">zabbix_connector</p>
            <p className="mt-1 text-sm text-slate-500">Новый или default provider</p>
          </button>
          {configs.map((config) => (
            <button
              className={cn(
                "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                config.provider_id === selectedProviderId
                  ? "border-brand-200 bg-brand-50"
                  : "border-border bg-white hover:border-brand-100",
              )}
              key={config.provider_id}
              onClick={() => setSelectedProviderId(config.provider_id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-950">{config.provider_id}</p>
                  <p className="mt-1 text-xs text-slate-500">{config.integration_key ?? "integration?"}</p>
                </div>
                <Badge tone={statusTone(config.status)}>{config.status}</Badge>
              </div>
            </button>
          ))}
        </div>

        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
        >
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Provider ID
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, providerId: event.target.value }))}
                value={draft.providerId}
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Provider type
              <Select
                onChange={(event) => setDraft((current) => ({ ...current, providerType: event.target.value }))}
                value={draft.providerType}
              >
                <option value="server_connector">server_connector</option>
                <option value="server_builtin">server_builtin</option>
                <option value="observer_provider">observer_provider</option>
                <option value="remote_assist_provider">remote_assist_provider</option>
                <option value="manual_provider">manual_provider</option>
              </Select>
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Integration key
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, integrationKey: event.target.value }))}
                value={draft.integrationKey}
              />
            </label>
            <label className="flex items-center gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm font-medium text-slate-800">
              <input
                checked={draft.enabled}
                onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
                type="checkbox"
              />
              Enabled
            </label>
          </div>

          <label className="space-y-1 text-sm font-medium text-slate-800">
            Config JSON
            <textarea
              className="field-base min-h-40 w-full resize-y px-3 py-2 font-mono text-xs"
              onChange={(event) => setDraft((current) => ({ ...current, configText: event.target.value }))}
              value={draft.configText}
            />
          </label>

          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Credential key
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, credentialKey: event.target.value }))}
                value={draft.credentialKey}
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Secret ref
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, secretRef: event.target.value }))}
                placeholder="secret://zabbix/api-token"
                value={draft.secretRef}
              />
            </label>
            <label className="space-y-1 text-sm font-medium text-slate-800">
              Credential status
              <Select
                onChange={(event) => setDraft((current) => ({ ...current, credentialStatus: event.target.value }))}
                value={draft.credentialStatus}
              >
                <option value="ready">ready</option>
                <option value="missing">missing</option>
                <option value="expired">expired</option>
              </Select>
            </label>
          </div>

          {selectedConfig ? (
            <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-4 text-sm text-slate-600">
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-brand-700" />
                <span>Текущий статус:</span>
                <Badge tone={statusTone(selectedConfig.status)}>{selectedConfig.status}</Badge>
                <span>credentials: {selectedConfig.credential_refs.length}</span>
              </div>
            </div>
          ) : null}

          {formError ? (
            <p className="rounded-[0.8rem] border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {formError}
            </p>
          ) : null}
          {savedMessage ? (
            <p className="rounded-[0.8rem] border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {savedMessage}
            </p>
          ) : null}

          <Button disabled={saveMutation.isPending || !draft.providerId.trim()} leadingIcon={<Save className="h-4 w-4" />} type="submit">
            {saveMutation.isPending ? "Сохраняем..." : "Сохранить provider config"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
