import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, ClipboardList, KeyRound, Save, ShieldCheck } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  checkKnowledgeAiProviderHealth,
  fetchKnowledgeAiAudit,
  fetchKnowledgeAiModelProfiles,
  fetchKnowledgeAiPolicies,
  fetchKnowledgeAiProviders,
  saveKnowledgeAiModelProfile,
  saveKnowledgeAiPolicy,
  saveKnowledgeAiProvider,
  type KnowledgeAiProvider,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

function toneForStatus(status?: string | null) {
  if (status === "ok" || status === "succeeded") {
    return "success" as const;
  }
  if (status === "failed" || status === "disabled") {
    return "danger" as const;
  }
  return "neutral" as const;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "нет";
  }
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function providerLabel(provider: KnowledgeAiProvider | undefined, providerId?: string | null) {
  if (!providerId) {
    return "без провайдера";
  }
  return provider?.title ?? providerId;
}

export function KnowledgeAiSettingsPage() {
  const queryClient = useQueryClient();
  const [providerDraft, setProviderDraft] = useState({
    code: "openrouter-main",
    title: "OpenRouter",
    provider_type: "openrouter",
    base_url: "https://openrouter.ai/api/v1",
    api_key_secret_ref: "",
    data_policy: "no_sensitive",
    enabled: true,
  });
  const [profileDraft, setProfileDraft] = useState({
    provider_id: "",
    code: "answer-default",
    title: "Ответы через OpenRouter",
    task_type: "answer",
    model_name: "openai/gpt-4o-mini",
    enabled: true,
    is_default: true,
  });
  const [policyDraft, setPolicyDraft] = useState({
    policy_id: "global-ai-policy",
    scope_type: "global",
    task_type: "answer",
    enabled: true,
    ai_allowed: false,
    embedding_allowed: false,
    rerank_allowed: false,
    answer_allowed: false,
    rewrite_allowed: false,
    auto_markup_allowed: false,
    redact_before_send: true,
    allow_cloud_for_requester_safe: false,
    require_local_for_security_restricted: true,
  });
  const [statusMessage, setStatusMessage] = useState("");

  const providersQuery = useQuery({ queryKey: ["knowledge-ai-providers"], queryFn: fetchKnowledgeAiProviders });
  const profilesQuery = useQuery({ queryKey: ["knowledge-ai-model-profiles"], queryFn: fetchKnowledgeAiModelProfiles });
  const policiesQuery = useQuery({ queryKey: ["knowledge-ai-policies"], queryFn: fetchKnowledgeAiPolicies });
  const auditQuery = useQuery({ queryKey: ["knowledge-ai-audit"], queryFn: fetchKnowledgeAiAudit });

  const providers = providersQuery.data ?? [];
  const providerById = useMemo(() => new Map(providers.map((provider) => [provider.provider_id, provider])), [providers]);
  const policies = policiesQuery.data ?? [];
  const globalPolicy = policies.find((policy) => policy.scope_type === "global") ?? policies[0];
  const aiEnabled = Boolean(globalPolicy?.enabled && globalPolicy.ai_allowed);

  const saveProviderMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeAiProvider({
        ...providerDraft,
        api_key_secret_ref: providerDraft.api_key_secret_ref.trim() || undefined,
      }),
    onSuccess: (result) => {
      setStatusMessage(result.display_message ?? "Провайдер AI сохранён");
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-providers"] });
    },
  });
  const saveProfileMutation = useMutation({
    mutationFn: () => saveKnowledgeAiModelProfile(profileDraft),
    onSuccess: (result) => {
      setStatusMessage(result.display_message ?? "Профиль модели сохранён");
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-model-profiles"] });
    },
  });
  const savePolicyMutation = useMutation({
    mutationFn: () => saveKnowledgeAiPolicy(policyDraft),
    onSuccess: (result) => {
      setStatusMessage(result.display_message ?? "Политика AI сохранена");
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-policies"] });
    },
  });
  const healthMutation = useMutation({
    mutationFn: (providerId: string) => checkKnowledgeAiProviderHealth(providerId, { model_name: profileDraft.model_name }),
    onSuccess: (result) => {
      setStatusMessage(result.display_message ?? "Проверка провайдера AI завершена");
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-providers"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-ai-audit"] });
    },
  });

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge AI"
        title="Настройки AI для базы знаний"
        description="Провайдеры, профили моделей, политики безопасности и журнал проверок. AI отключается политикой и не нужен для базового поиска или просмотра статей."
      />

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Всего провайдеров</CardTitle>
            <CardDescription>Подключения без вывода raw secret refs</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{providers.length}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Всего профилей</CardTitle>
            <CardDescription>Задачи answer, embedding, rerank</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{profilesQuery.data?.length ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>AI режим</CardTitle>
            <CardDescription>Глобальные и scoped ограничения</CardDescription>
          </CardHeader>
          <CardContent>
            <Badge tone={aiEnabled ? "success" : "danger"}>{aiEnabled ? "AI включен" : "AI выключен"}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Записи журнала</CardTitle>
            <CardDescription>Redacted health и request audit</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{auditQuery.data?.length ?? 0}</CardContent>
        </Card>
      </div>

      {statusMessage ? <div className="rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">{statusMessage}</div> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                Провайдеры
              </CardTitle>
              <CardDescription>Ключ вводится через одобренную secret/config точку. В ответах и UI показывается только маска.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {providers.map((provider) => (
                <div key={provider.provider_id} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950">{provider.title}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {provider.code} · {provider.provider_type} · {provider.data_policy ?? "policy не задана"}
                      </p>
                      <p className="mt-2 text-xs text-slate-600">
                        Secret: {provider.api_key_secret_ref_masked ?? (provider.api_key_configured ? "настроен" : "не настроен")}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={provider.enabled ? "success" : "danger"}>{provider.enabled ? "включен" : "отключен"}</Badge>
                      <Badge tone={toneForStatus(provider.health_status)}>{provider.health_status ?? "health не проверялся"}</Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        leadingIcon={<Activity className="h-4 w-4" />}
                        onClick={() => healthMutation.mutate(provider.provider_id)}
                        disabled={healthMutation.isPending}
                      >
                        Проверить OpenRouter
                      </Button>
                    </div>
                  </div>
                  {provider.last_error_redacted ? <p className="mt-2 text-xs text-red-700">{provider.last_error_redacted}</p> : null}
                </div>
              ))}
              {!providers.length ? <p className="text-sm text-slate-500">Провайдеры AI пока не настроены.</p> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5" />
                Профили моделей
              </CardTitle>
              <CardDescription>Каждая задача может быть отключена независимо от провайдера.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(profilesQuery.data ?? []).map((profile) => (
                <div key={profile.profile_id} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950">{profile.title}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {profile.task_type} · {profile.model_name} · {providerLabel(providerById.get(profile.provider_id ?? ""), profile.provider_id)}
                      </p>
                    </div>
                    <Badge tone={profile.enabled ? "success" : "danger"}>{profile.enabled ? "включен" : "отключен"}</Badge>
                  </div>
                </div>
              ))}
              {!profilesQuery.data?.length ? <p className="text-sm text-slate-500">Профили моделей пока не настроены.</p> : null}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="h-5 w-5" />
                Новый провайдер
              </CardTitle>
              <CardDescription>Для OpenRouter укажите secret ref или оставьте пустым до настройки окружения.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Код
                <input className={fieldClass} value={providerDraft.code} onChange={(event) => setProviderDraft({ ...providerDraft, code: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Название
                <input className={fieldClass} value={providerDraft.title} onChange={(event) => setProviderDraft({ ...providerDraft, title: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Base URL
                <input className={fieldClass} value={providerDraft.base_url} onChange={(event) => setProviderDraft({ ...providerDraft, base_url: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Secret ref
                <input
                  className={fieldClass}
                  value={providerDraft.api_key_secret_ref}
                  onChange={(event) => setProviderDraft({ ...providerDraft, api_key_secret_ref: event.target.value })}
                  placeholder="env:<имя переменной>"
                />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={providerDraft.enabled} onChange={(event) => setProviderDraft({ ...providerDraft, enabled: event.target.checked })} />
                Провайдер включен
              </label>
              <Button leadingIcon={<Save className="h-4 w-4" />} onClick={() => saveProviderMutation.mutate()} disabled={saveProviderMutation.isPending}>
                Сохранить провайдера
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Профиль модели</CardTitle>
              <CardDescription>Минимальный профиль для ответов или health-check.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Провайдер
                <select className={fieldClass} value={profileDraft.provider_id} onChange={(event) => setProfileDraft({ ...profileDraft, provider_id: event.target.value })}>
                  <option value="">Выберите провайдера</option>
                  {providers.map((provider) => (
                    <option key={provider.provider_id} value={provider.provider_id}>
                      {provider.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium">
                Название
                <input className={fieldClass} value={profileDraft.title} onChange={(event) => setProfileDraft({ ...profileDraft, title: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Model name
                <input className={fieldClass} value={profileDraft.model_name} onChange={(event) => setProfileDraft({ ...profileDraft, model_name: event.target.value })} />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={profileDraft.enabled} onChange={(event) => setProfileDraft({ ...profileDraft, enabled: event.target.checked })} />
                Профиль включен
              </label>
              <Button leadingIcon={<Save className="h-4 w-4" />} onClick={() => saveProfileMutation.mutate()} disabled={!profileDraft.provider_id || saveProfileMutation.isPending}>
                Сохранить профиль
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Политики AI
              </CardTitle>
              <CardDescription>security_restricted не отправляется в cloud без явной политики администратора.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                ["ai_allowed", "Глобально разрешить AI"],
                ["embedding_allowed", "Разрешить embeddings"],
                ["rerank_allowed", "Разрешить rerank"],
                ["answer_allowed", "Разрешить Ask/answer"],
                ["rewrite_allowed", "Разрешить rewrite"],
                ["auto_markup_allowed", "Разрешить AI markup"],
                ["redact_before_send", "Редактировать данные перед отправкой"],
                ["allow_cloud_for_requester_safe", "Разрешить cloud для requester-safe"],
                ["require_local_for_security_restricted", "Требовать local для security-restricted"],
              ].map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(policyDraft[key as keyof typeof policyDraft])}
                    onChange={(event) => setPolicyDraft({ ...policyDraft, [key]: event.target.checked })}
                  />
                  {label}
                </label>
              ))}
              <Button leadingIcon={<Save className="h-4 w-4" />} onClick={() => savePolicyMutation.mutate()} disabled={savePolicyMutation.isPending}>
                Сохранить политику
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Журнал AI</CardTitle>
          <CardDescription>Последние проверки и запросы. Prompt/output и ошибки выводятся только в redacted виде.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-hidden rounded-md border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Время</th>
                  <th className="px-3 py-2">Задача</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Ошибка</th>
                </tr>
              </thead>
              <tbody>
                {(auditQuery.data ?? []).map((row) => (
                  <tr key={row.audit_id} className="border-t border-slate-100">
                    <td className="px-3 py-2">{formatDate(row.created_at)}</td>
                    <td className="px-3 py-2">{row.task_type ?? "unknown"}</td>
                    <td className="px-3 py-2">
                      <Badge tone={toneForStatus(row.status)}>{row.status ?? "unknown"}</Badge>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{row.error_message_redacted ?? row.error_code ?? "нет"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!auditQuery.data?.length ? <p className="p-4 text-sm text-slate-500">Журнал AI пока пуст.</p> : null}
          </div>
        </CardContent>
      </Card>

      {providersQuery.isError || profilesQuery.isError || policiesQuery.isError || auditQuery.isError ? (
        <Card>
          <CardContent className="p-4 text-sm text-red-700">Часть настроек AI не загрузилась. Проверьте RBAC и backend API.</CardContent>
        </Card>
      ) : null}
    </section>
  );
}
