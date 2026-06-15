import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bot, FileSearch, Gauge, GitBranch, Layers, ListChecks, Search, ShieldAlert } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import {
  fetchKnowledgeMetadata,
  fetchKnowledgeOpsSummary,
  type KnowledgeMetadataBundle,
  type KnowledgeOpsMetric,
  type KnowledgeOpsQueue,
  type KnowledgeOpsSummary,
} from "./api";

function metricValue(metric?: KnowledgeOpsMetric | null) {
  return Number(metric?.total ?? 0);
}

function statusTone(status?: string) {
  return status === "degraded" ? "danger" : "success";
}

function OpsCard({
  title,
  value,
  description,
}: {
  title: string;
  value: number | string;
  description: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-slate-600">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="text-3xl font-semibold text-slate-950">{value}</CardContent>
    </Card>
  );
}

function SummaryGrid({ summary }: { summary: KnowledgeOpsSummary }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <OpsCard description="Опубликованные requester/public/agent-safe статьи" title="Безопасное покрытие" value={metricValue(summary.coverage.requester_safe)} />
      <OpsCard description="Поиски без подходящей статьи" title="Поиски без результатов" value={metricValue(summary.search.zero_result_searches)} />
      <OpsCard description="Попытки Ask/RAG без достаточных оснований" title="RAG без ответа" value={metricValue(summary.rag.no_answer_count)} />
      <OpsCard description="Задачи индексации, требующие внимания" title="Ошибки индексации" value={metricValue(summary.indexing.failed)} />
      <OpsCard description="Средняя объяснимая оценка контента" title="Среднее качество" value={summary.quality.average_score.toFixed(1)} />
      <OpsCard description="Открытые задачи кураторов" title="Назначенные проверки" value={metricValue(summary.review.assigned_open)} />
      <OpsCard description="Узлы графа без связанной статьи" title="Узлы графа без связей" value={metricValue(summary.graph.orphan_nodes)} />
      <OpsCard description="Блокировки политик поиска/RAG/индексации" title="Блокировки AI-политик" value={metricValue(summary.ai.policy_blocks)} />
    </div>
  );
}

type ActionQueueKey = keyof NonNullable<KnowledgeOpsSummary["action_queues"]>;
type ActionQueueItem = NonNullable<KnowledgeOpsQueue["items"]>[number];

const queueDefinitions: Array<{
  key: ActionQueueKey;
  title: string;
  description: string;
  fallback: string;
  actionLabel: string;
  actionHint: string;
  fallbackActionUrl: string;
}> = [
  {
    key: "no_audience_users",
    title: "Статьи без аудитории",
    description: "Проверьте правила видимости: опубликованный материал не попадает ни к одному пользователю.",
    fallback: "Аудитории статей не требуют вмешательства.",
    actionLabel: "Проверить аудиторию",
    actionHint: "Откройте статью и проверьте аудиторию, видимость раздела и правила доступа.",
    fallbackActionUrl: "/app/admin/knowledge/sections",
  },
  {
    key: "missing_helpdesk_binding",
    title: "Статьи без связи с обращениями",
    description: "Свяжите материал с услугой, предложением или формой, чтобы он появлялся в нужном helpdesk-сценарии.",
    fallback: "Все статьи связаны с услугами или формами.",
    actionLabel: "Настроить связь",
    actionHint: "Откройте панель связи с обращениями и выберите service/offering/template плюс поверхности показа.",
    fallbackActionUrl: "/app/admin/knowledge/studio",
  },
  {
    key: "stale_article",
    title: "Просроченные статьи",
    description: "Обновите устаревшие материалы и сохраните новую опубликованную версию.",
    fallback: "Просроченных проверок нет.",
    actionLabel: "Обновить статью",
    actionHint: "Откройте статью в Studio, обновите содержимое и сохраните актуальную опубликованную версию.",
    fallbackActionUrl: "/app/admin/knowledge/studio",
  },
  {
    key: "indexing_failed",
    title: "Ошибки индексации",
    description: "Разберите сбои индексирования, чтобы поиск и RAG видели актуальные фрагменты.",
    fallback: "Ошибок индексации нет.",
    actionLabel: "Открыть индексацию",
    actionHint: "Откройте очередь индексации, проверьте ошибку провайдера и запустите повторную индексацию.",
    fallbackActionUrl: "/app/admin/knowledge/indexing",
  },
  {
    key: "low_quality",
    title: "Низкое качество",
    description: "Исправьте слабые статьи: владельца, обзор, полноту, безопасность или метаданные.",
    fallback: "Критичных замечаний качества нет.",
    actionLabel: "Улучшить качество",
    actionHint: "Откройте статью и устраните причину низкой оценки: полноту, владельца, безопасность или метаданные.",
    fallbackActionUrl: "/app/admin/knowledge/studio",
  },
  {
    key: "zero_result_searches",
    title: "Поиски без результата",
    description: "Разберите спрос, который не закрывается статьями, настройками поиска или новым импортом.",
    fallback: "Поисков без результата нет.",
    actionLabel: "Проверить поиск",
    actionHint: "Откройте настройки поиска, проверьте retrieval/RAG или создайте статью под незакрытый запрос.",
    fallbackActionUrl: "/app/admin/knowledge/search-settings",
  },
];

const quickFixLinks = [
  { href: "/app/admin/knowledge/sections", label: "Разделы", text: "Политики разделов, аудитория и RAG", hint: "Открыть разделы базы знаний для настройки аудитории, публикации и RAG." },
  { href: "/app/admin/knowledge/import", label: "Создать статью", text: "Импорт или черновик для незакрытого спроса", hint: "Открыть импорт или создание черновика для запроса без результата." },
  { href: "/app/admin/knowledge/indexing", label: "Индексация", text: "Очередь, сбои и reindex", hint: "Открыть диагностику индексации и повторную обработку статей." },
  { href: "/app/admin/knowledge/search-settings", label: "Настройки поиска", text: "Retrieval, RAG и explain preview", hint: "Открыть настройки поиска, RAG и explain preview." },
];

function itemTitle(item: ActionQueueItem, fallback: string) {
  return item.title ?? item.query ?? fallback;
}

function ActionQueueColumn({
  actionLabel,
  actionHint,
  fallback,
  fallbackActionUrl,
  queue,
  title,
  description,
}: {
  actionLabel: string;
  actionHint: string;
  fallback: string;
  fallbackActionUrl: string;
  queue?: KnowledgeOpsQueue;
  title: string;
  description: string;
}) {
  const items = queue?.items ?? [];
  return (
    <div className="min-w-0 rounded-md border border-slate-200 bg-white p-3" title={actionHint}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
        </div>
        <Badge tone={metricValue(queue) ? "warning" : "success"}>{metricValue(queue)}</Badge>
      </div>
      <div className="mt-3 space-y-3">
        {items.length ? (
          items.slice(0, 3).map((item, index) => (
            <div key={`${title}-${item.item_id ?? item.job_id ?? item.query ?? index}`} className="min-w-0 border-t border-slate-100 pt-3">
              <p className="truncate text-sm font-medium text-slate-900">{itemTitle(item, title)}</p>
              {item.reason ? <p className="mt-1 text-xs leading-5 text-slate-600">{item.reason}</p> : null}
              <a
                className="mt-2 inline-flex text-xs font-semibold text-brand-700 hover:text-brand-900"
                href={item.action_url ?? fallbackActionUrl}
                title={actionHint}
              >
                {actionLabel}
              </a>
            </div>
          ))
        ) : (
          <div className="border-t border-slate-100 pt-3">
            <p className="text-sm text-slate-500">{fallback}</p>
            <a
              className="mt-2 inline-flex text-xs font-semibold text-brand-700 hover:text-brand-900"
              href={fallbackActionUrl}
              title={actionHint}
            >
              Открыть рабочую область
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionQueuesPanel({ summary }: { summary: KnowledgeOpsSummary }) {
  const queues = summary.action_queues ?? {};
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ListChecks className="h-4 w-4" />
          Очереди действий
        </CardTitle>
        <CardDescription>Конкретные места, где нужно поправить аудиторию, привязку, качество, индекс или поисковый спрос.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {queueDefinitions.map((queue) => (
            <ActionQueueColumn
              actionLabel={queue.actionLabel}
              actionHint={queue.actionHint}
              description={queue.description}
              fallback={queue.fallback}
              fallbackActionUrl={queue.fallbackActionUrl}
              key={queue.key}
              queue={queues[queue.key]}
              title={queue.title}
            />
          ))}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {quickFixLinks.map((link) => (
            <a
              aria-label={link.label}
              className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm transition-colors hover:border-brand-200 hover:bg-brand-50"
              href={link.href}
              key={link.href}
              title={link.hint}
            >
              <span className="font-semibold text-brand-800">{link.label}</span>
              <span className="mt-1 block text-xs leading-5 text-slate-600">{link.text}</span>
            </a>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MetadataModelPanel({ metadata }: { metadata?: KnowledgeMetadataBundle }) {
  const activeModel = metadata?.quality_models?.find((model) => model.is_default && model.status === "active") ?? metadata?.quality_models?.find((model) => model.status === "active");
  const weights = activeModel?.weights ?? {};
  const weightEntries = Object.entries(weights).slice(0, 6);
  const activeTaxonomyTerms = metadata?.summary?.taxonomy_terms_active ?? metadata?.taxonomy_terms?.filter((row) => row.status === "active").length ?? 0;
  const activePropertyDefinitions = metadata?.summary?.property_definitions_active ?? metadata?.property_definitions?.filter((row) => row.status === "active").length ?? 0;
  const activeApplicabilityRules = metadata?.summary?.applicability_rules_active ?? metadata?.applicability_rules?.length ?? 0;
  const itemMetadataCount = metadata?.summary?.item_metadata_total ?? metadata?.item_metadata?.length ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Layers className="h-4 w-4" />
          Модель метаданных знаний
        </CardTitle>
        <CardDescription>Таксономия, типизированные свойства, правила применимости и покрытие модели качества.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase text-slate-500">Термины таксономии</p>
            <p className="text-2xl font-semibold text-slate-950">{activeTaxonomyTerms}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Свойства</p>
            <p className="text-2xl font-semibold text-slate-950">{activePropertyDefinitions}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Правила применимости</p>
            <p className="text-2xl font-semibold text-slate-950">{activeApplicabilityRules}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Метаданные статей</p>
            <p className="text-2xl font-semibold text-slate-950">{itemMetadataCount}</p>
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Активная модель качества:</span>
            <Badge tone={activeModel ? "success" : "warning"}>{activeModel?.code ?? "builtin-default"}</Badge>
            <span className="text-slate-500">{activeModel?.title ?? "Встроенная модель качества"}</span>
          </div>
          {weightEntries.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {weightEntries.map(([key, value]) => (
                <Badge key={key} tone="neutral">
                  {key}: {value}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-slate-500">Пользовательские веса качества не настроены.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function KnowledgeOpsDashboardPanel() {
  const summaryQuery = useQuery({ queryKey: ["knowledge-ops-summary"], queryFn: fetchKnowledgeOpsSummary });
  const metadataQuery = useQuery({ queryKey: ["knowledge-metadata"], queryFn: fetchKnowledgeMetadata });
  const summary = summaryQuery.data;

  if (summaryQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Центр операций базы знаний</CardTitle>
          <CardDescription>Загрузка операционного снимка...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (summaryQuery.isError || !summary) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardHeader>
          <CardTitle>Центр операций базы знаний</CardTitle>
          <CardDescription>Не удалось загрузить сводку операций базы знаний.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const degradations = summary.observer.degradations ?? [];
  const topQuery = summary.search.top_queries?.[0];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-brand-600" />
            <h2 className="text-xl font-semibold text-slate-950">Центр операций базы знаний</h2>
            <Badge tone={statusTone(summary.status)}>{summary.status === "degraded" ? "Деградация" : "OK"}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600">Снимок покрытия, качества, поиска, RAG, индексации и состояния Observer v2.</p>
        </div>
        <p className="text-sm text-slate-500">Обновлено {new Date(summary.generated_at).toLocaleString("ru-RU")}</p>
      </div>

      <SummaryGrid summary={summary} />

      <ActionQueuesPanel summary={summary} />

      <MetadataModelPanel metadata={metadataQuery.data} />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Search className="h-4 w-4" />
              Поиск и RAG
            </CardTitle>
            <CardDescription>Fallback, векторное использование и спрос по запросам.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Fallback: {metricValue(summary.search.fallback_count)}</p>
            <p>AI отключён: {metricValue(summary.search.ai_disabled_count)}</p>
            <p>Вектор/rerank: {metricValue(summary.search.vector_usage_count)} / {metricValue(summary.search.rerank_usage_count)}</p>
            <p>Главный запрос: {topQuery ? `${topQuery.query} (${topQuery.count})` : "нет данных"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="h-4 w-4" />
              Покрытие и проверка
            </CardTitle>
            <CardDescription>Пробелы базы знаний и нагрузка на проверки.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Пространства: {metricValue(summary.coverage.spaces)}</p>
            <p>Опубликованные статьи: {metricValue(summary.coverage.published_articles)}</p>
            <p>Сервисы без KB: {metricValue(summary.coverage.services_without_kb)}</p>
            <p>Просроченные проверки: {metricValue(summary.review.overdue)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-4 w-4" />
              AI, индексация и граф
            </CardTitle>
            <CardDescription>Сигналы провайдера, embedding и графа.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Состояние провайдера: {summary.ai.provider_health.status}</p>
            <p>Очередь индексации: {metricValue(summary.indexing.queued)}</p>
            <p>Устаревшие/отключённые embeddings: {metricValue(summary.indexing.stale_embeddings)} / {metricValue(summary.indexing.disabled)}</p>
            <p>Предложения графа: {metricValue(summary.graph.pending_proposals)}</p>
          </CardContent>
        </Card>
      </div>

      <Card className={degradations.length ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50"}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {degradations.length ? <ShieldAlert className="h-4 w-4 text-red-700" /> : <FileSearch className="h-4 w-4 text-emerald-700" />}
            Деградации из Observer
          </CardTitle>
          <CardDescription>Активные сигналы Observer v2 с источником знаний или типом события.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {degradations.length ? (
            degradations.map((item) => (
              <div key={`${item.code}-${item.source}-${item.message}`} className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-red-200 bg-white p-3">
                <div>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-red-700" />
                    <p className="font-medium text-slate-950">{item.code}</p>
                    <Badge tone="danger">{item.severity}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{item.message}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.source}</p>
                </div>
                <p className="text-sm font-semibold text-red-700">{item.count}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-emerald-800">Активных деградаций базы знаний нет.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GitBranch className="h-4 w-4" />
            Контур интеграции Phase 12
          </CardTitle>
          <CardDescription>Первый срез сохраняет элементы управления автора ниже и добавляет операционный снимок выше.</CardDescription>
        </CardHeader>
      </Card>
    </section>
  );
}
