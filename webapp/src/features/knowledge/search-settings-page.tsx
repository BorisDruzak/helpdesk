import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gauge, Save, Search, ShieldCheck, SlidersHorizontal } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  fetchKnowledgeSearchSettings,
  previewKnowledgeRetrieval,
  saveKnowledgeSearchSettings,
  type KnowledgeSearchSettings,
  type KnowledgeRetrievalResult,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const numberFieldClass = "mt-1 block w-full max-w-36 rounded-md border border-slate-200 px-3 py-2 text-sm";

type SearchSettingsDraft = {
  search_mode: string;
  keyword_enabled: boolean;
  full_text_enabled: boolean;
  vector_enabled: boolean;
  rerank_enabled: boolean;
  ai_query_rewrite_enabled: boolean;
  rag_answer_enabled: boolean;
  keyword_weight: number;
  full_text_weight: number;
  vector_weight: number;
  max_results: number;
  snippet_length: number;
};

const defaultDraft: SearchSettingsDraft = {
  search_mode: "keyword_only",
  keyword_enabled: true,
  full_text_enabled: false,
  vector_enabled: false,
  rerank_enabled: false,
  ai_query_rewrite_enabled: false,
  rag_answer_enabled: false,
  keyword_weight: 1,
  full_text_weight: 1,
  vector_weight: 1,
  max_results: 10,
  snippet_length: 180,
};

const searchModes = [
  ["keyword_only", "Keyword only"],
  ["full_text", "Full-text"],
  ["hybrid_no_ai", "Hybrid без AI"],
  ["hybrid_vector", "Hybrid vector"],
  ["hybrid_vector_rerank", "Vector + rerank"],
  ["rag_answer", "RAG answer"],
] as const;

const aiDependentSwitches = new Set(["vector_enabled", "rerank_enabled", "ai_query_rewrite_enabled", "rag_answer_enabled"]);

const searchModeGuidance = [
  "Keyword: быстрые совпадения по названию, slug, ключевым словам, сервису и шаблону обращения.",
  "Full-text: поиск по опубликованному тексту статьи, чанкам и активным сегментам без AI-провайдера.",
  "Vector: семантический поиск по embeddings; включается только при готовой индексации и разрешенной AI policy.",
  "RAG: ответ только по найденным и разрешённым источникам; не расширяет видимость статьи и не обходит аудиторию.",
];

const ragEligibilityGuidance =
  "RAG может использовать статью, когда она опубликована, доступна текущей роли/аудитории, раздел разрешает AI/RAG, а политика статьи не запрещает RAG.";

const visibilityGuidance =
  "Фильтры видимости и аудитории применяются до ранжирования, сниппетов и цитат. Запрещённые статьи не попадают в выдачу, счетчики и диагностические результаты requester/agent поверхностей.";

function draftFromSettings(settings?: KnowledgeSearchSettings): SearchSettingsDraft {
  if (!settings) {
    return defaultDraft;
  }
  return {
    search_mode: settings.search_mode || defaultDraft.search_mode,
    keyword_enabled: Boolean(settings.keyword_enabled),
    full_text_enabled: Boolean(settings.full_text_enabled),
    vector_enabled: Boolean(settings.vector_enabled),
    rerank_enabled: Boolean(settings.rerank_enabled),
    ai_query_rewrite_enabled: Boolean(settings.ai_query_rewrite_enabled),
    rag_answer_enabled: Boolean(settings.rag_answer_enabled),
    keyword_weight: Number(settings.keyword_weight ?? defaultDraft.keyword_weight),
    full_text_weight: Number(settings.full_text_weight ?? defaultDraft.full_text_weight),
    vector_weight: Number(settings.vector_weight ?? defaultDraft.vector_weight),
    max_results: Number(settings.max_results ?? defaultDraft.max_results),
    snippet_length: Number(settings.snippet_length ?? defaultDraft.snippet_length),
  };
}

function boundedNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.max(min, Math.min(max, value));
}

function modeLabel(mode?: string | null) {
  return searchModes.find(([value]) => value === mode)?.[1] ?? mode ?? "не задан";
}

export function KnowledgeSearchSettingsPage() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["knowledge-search-settings"], queryFn: fetchKnowledgeSearchSettings });
  const [draft, setDraft] = useState<SearchSettingsDraft>(defaultDraft);
  const [draftInitialized, setDraftInitialized] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [previewQuery, setPreviewQuery] = useState("");
  const [previewActorRole, setPreviewActorRole] = useState("support");
  const [previewSurface, setPreviewSurface] = useState("admin_knowledge_search");
  const [previewResult, setPreviewResult] = useState<KnowledgeRetrievalResult | null>(null);

  useEffect(() => {
    if (settingsQuery.data && !draftInitialized) {
      setDraft(draftFromSettings(settingsQuery.data));
      setDraftInitialized(true);
    }
  }, [draftInitialized, settingsQuery.data]);

  const aiSwitchesEnabled = draft.vector_enabled || draft.rerank_enabled || draft.ai_query_rewrite_enabled || draft.rag_answer_enabled;
  const aiControlsDisabled = settingsQuery.data ? !settingsQuery.data.ai_enabled : false;
  const effectiveMode = settingsQuery.data?.effective_mode ?? draft.search_mode;
  const savePayload = useMemo(
    () => ({
      ...draft,
      keyword_weight: boundedNumber(draft.keyword_weight, 0, 10),
      full_text_weight: boundedNumber(draft.full_text_weight, 0, 10),
      vector_weight: boundedNumber(draft.vector_weight, 0, 10),
      max_results: boundedNumber(Math.round(draft.max_results), 1, 50),
      snippet_length: boundedNumber(Math.round(draft.snippet_length), 80, 1000),
    }),
    [draft],
  );

  const saveMutation = useMutation({
    mutationFn: () => saveKnowledgeSearchSettings(savePayload),
    onSuccess: (result) => {
      setStatusMessage(result.display_message ?? "Настройки поиска сохранены");
      setDraft(draftFromSettings(result.settings));
      setDraftInitialized(true);
      queryClient.invalidateQueries({ queryKey: ["knowledge-search-settings"] });
    },
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      previewKnowledgeRetrieval({
        query: previewQuery.trim(),
        actor_role: previewActorRole,
        surface: previewSurface,
      }),
    onSuccess: (result) => {
      setPreviewResult(result);
    },
  });

  function updateDraft(nextDraft: SearchSettingsDraft) {
    setDraftInitialized(true);
    setDraft(nextDraft);
  }

  function updateBoolean(key: keyof SearchSettingsDraft, value: boolean) {
    setDraftInitialized(true);
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function updateNumber(key: keyof SearchSettingsDraft, value: string) {
    setDraftInitialized(true);
    setDraft((current) => ({ ...current, [key]: Number(value) }));
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Search"
        title="Настройки поиска базы знаний"
        description="Базовый поиск работает без AI-провайдеров, embeddings и vector index. Векторные и RAG режимы включаются отдельно."
      />

      <div className="sticky top-20 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div>
          <p className="text-sm font-semibold text-slate-950">Основное действие</p>
          <p className="text-xs text-slate-500">Сохранить режим retrieval, веса и лимиты выдачи.</p>
        </div>
        <Button
          leadingIcon={<Save className="h-4 w-4" />}
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || settingsQuery.isLoading}
        >
          Сохранить настройки
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Текущий режим
            </CardTitle>
            <CardDescription>Сохранённый режим retrieval</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-2xl font-semibold text-slate-950">{settingsQuery.data?.search_mode ?? draft.search_mode}</p>
            <Badge tone={settingsQuery.data?.ai_enabled ? "success" : "danger"}>
              {settingsQuery.data?.ai_enabled ? "AI включен" : "AI выключен"}
            </Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5" />
              Эффективный режим
            </CardTitle>
            <CardDescription>Фактический fallback после переключателей</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold text-slate-950">{effectiveMode}</p>
            <p className="mt-2 text-sm text-slate-500">{modeLabel(effectiveMode)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SlidersHorizontal className="h-5 w-5" />
              Лимиты выдачи
            </CardTitle>
            <CardDescription>Ограничение результата и сниппета</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-slate-700">
            <p>{draft.max_results} результатов</p>
            <p className="mt-1">{draft.snippet_length} символов сниппета</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Как читать режимы поиска
            </CardTitle>
            <CardDescription>Короткая расшифровка, чтобы настройки не выглядели как набор технических флагов.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm leading-6 text-slate-700 md:grid-cols-2">
            {searchModeGuidance.map((item) => (
              <p key={item} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                {item}
              </p>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              Видимость, аудитория и RAG
            </CardTitle>
            <CardDescription>Эти фильтры являются guardrail, а не настройкой ранжирования.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-slate-700">
            <p>{visibilityGuidance}</p>
            <p>{ragEligibilityGuidance}</p>
            <p className="text-xs text-slate-500">RAG trace и score breakdown показываются только привилегированным ролям; requester-safe ответы не получают скрытые заголовки, чанки или причины отказа.</p>
          </CardContent>
        </Card>
      </div>

      {statusMessage ? <div className="rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">{statusMessage}</div> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Режим и источники поиска</CardTitle>
            <CardDescription>Keyword и full-text не зависят от AI. Vector, rerank, rewrite и RAG считаются AI-зависимыми.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <label className="block text-sm font-medium">
              Режим поиска
              <select className={fieldClass} value={draft.search_mode} onChange={(event) => updateDraft({ ...draft, search_mode: event.target.value })}>
                {searchModes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-3 md:grid-cols-2">
              {[
                ["keyword_enabled", "Keyword поиск"],
                ["full_text_enabled", "Full-text поиск"],
                ["vector_enabled", "Vector поиск"],
                ["rerank_enabled", "Rerank"],
                ["ai_query_rewrite_enabled", "AI rewrite"],
                ["rag_answer_enabled", "RAG ответы"],
              ].map(([key, label]) => {
                const disabled = aiControlsDisabled && aiDependentSwitches.has(key);
                return (
                <label key={key} className={`flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm ${disabled ? "bg-slate-50 text-slate-400" : ""}`}>
                  <span>{label}</span>
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={Boolean(draft[key as keyof SearchSettingsDraft])}
                    onChange={(event) => updateBoolean(key as keyof SearchSettingsDraft, event.target.checked)}
                  />
                </label>
              );
              })}
            </div>

            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {aiControlsDisabled
                ? "AI-политика выключена. Vector, rerank, rewrite и RAG включаются через AI Governance перед изменением retrieval."
                : aiSwitchesEnabled
                  ? "Включены AI-зависимые переключатели. Проверьте политики AI и провайдеры перед production."
                  : "AI-зависимые переключатели выключены. Поиск останется в безопасном baseline режиме."}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Лимиты и веса</CardTitle>
            <CardDescription>Значения применяются backend API при сохранении.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-sm font-medium">
              Максимум результатов
              <input
                aria-label="Максимум результатов"
                className={numberFieldClass}
                min={1}
                max={50}
                type="number"
                value={draft.max_results}
                onChange={(event) => updateNumber("max_results", event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium">
              Длина сниппета
              <input
                aria-label="Длина сниппета"
                className={numberFieldClass}
                min={80}
                max={1000}
                type="number"
                value={draft.snippet_length}
                onChange={(event) => updateNumber("snippet_length", event.target.value)}
              />
            </label>
            {[
              ["keyword_weight", "Вес keyword"],
              ["full_text_weight", "Вес full-text"],
              ["vector_weight", "Вес vector"],
            ].map(([key, label]) => (
              <label key={key} className="block text-sm font-medium">
                {label}
                <input
                  className={numberFieldClass}
                  min={0}
                  max={10}
                  step={0.1}
                  type="number"
                  value={Number(draft[key as keyof SearchSettingsDraft])}
                  onChange={(event) => updateNumber(key as keyof SearchSettingsDraft, event.target.value)}
                />
              </label>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Проверка поиска</CardTitle>
          <CardDescription>Проверяет фактический backend fallback и выдачу без embeddings или AI-провайдера.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_260px_auto] lg:items-end">
            <label className="block text-sm font-medium">
              Проверочный запрос
              <input
                aria-label="Проверочный запрос"
                className={fieldClass}
                placeholder="Например: VPN"
                value={previewQuery}
                onChange={(event) => setPreviewQuery(event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium">
              Роль
              <select className={fieldClass} value={previewActorRole} onChange={(event) => setPreviewActorRole(event.target.value)}>
                <option value="support">support</option>
                <option value="admin">admin</option>
                <option value="auditor">auditor</option>
              </select>
            </label>
            <label className="block text-sm font-medium">
              Поверхность
              <select className={fieldClass} value={previewSurface} onChange={(event) => setPreviewSurface(event.target.value)}>
                <option value="admin_knowledge_search">admin_knowledge_search</option>
                <option value="support_workspace">support_workspace</option>
                <option value="requester_portal">requester_portal</option>
              </select>
            </label>
            <Button
              leadingIcon={<Search className="h-4 w-4" />}
              onClick={() => previewMutation.mutate()}
              disabled={!previewQuery.trim() || previewMutation.isPending}
            >
              Проверить поиск
            </Button>
          </div>

          {previewMutation.isError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              Не удалось выполнить проверочный поиск.
            </div>
          ) : null}

          {previewResult ? (
            <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {previewResult.display_message ? <span className="font-medium text-slate-900">{previewResult.display_message}</span> : null}
                <Badge tone={previewResult.ai_used ? "warning" : "success"}>
                  {previewResult.ai_used ? "AI использовался" : "AI не использовался"}
                </Badge>
                <Badge>{previewResult.effective_mode ?? previewResult.search_mode ?? "режим не задан"}</Badge>
              </div>
              {previewResult.results.length ? (
                <div className="space-y-2">
                  {previewResult.results.map((result, index) => {
                    const scoreParts = Object.entries(result.score_parts ?? {});
                    return (
                    <div key={result.item.item_id ?? result.item.slug ?? `${result.item.title}-${index}`} className="rounded-md border border-slate-200 bg-white p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-slate-950">{result.item.title}</p>
                        {result.item.visibility ? <Badge>{result.item.visibility}</Badge> : null}
                      </div>
                      {result.item.summary ? <p className="mt-1 text-sm text-slate-600">{result.item.summary}</p> : null}
                      {result.snippet ? <p className="mt-2 text-sm text-slate-700">{result.snippet}</p> : null}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {(result.source_mode ?? []).map((source) => (
                          <Badge key={source}>{source}</Badge>
                        ))}
                        {typeof result.score === "number" ? <Badge tone="success">score {result.score}</Badge> : null}
                      </div>
                      {scoreParts.length ? (
                        <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
                          {scoreParts.map(([key, value]) => (
                            <div key={key} className="rounded border border-slate-100 bg-slate-50 px-2 py-1">
                              <dt className="font-medium text-slate-600">{key}</dt>
                              <dd className="text-slate-900">{Number(value).toFixed(2)}</dd>
                            </div>
                          ))}
                        </dl>
                      ) : null}
                      <p className="mt-2 text-xs text-slate-500">
                        {result.item.slug ? `slug: ${result.item.slug}` : "slug не задан"}
                        {result.citations?.length ? ` · citations: ${result.citations.length}` : ""}
                      </p>
                    </div>
                  );
                  })}
                </div>
              ) : (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  По запросу ничего не найдено. Zero-result должен попасть в observer/search analytics.
                </div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {settingsQuery.isError ? (
        <Card>
          <CardContent className="p-4 text-sm text-red-700">Настройки поиска не загрузились. Проверьте доступ администратора и backend API.</CardContent>
        </Card>
      ) : null}
    </section>
  );
}
