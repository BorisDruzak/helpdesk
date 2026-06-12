import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bot, FileSearch, Gauge, GitBranch, Layers, Search, ShieldAlert } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { fetchKnowledgeMetadata, fetchKnowledgeOpsSummary, type KnowledgeMetadataBundle, type KnowledgeOpsMetric, type KnowledgeOpsSummary } from "./api";

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
      <OpsCard description="Published requester/public/agent-safe items" title="Requester-safe coverage" value={metricValue(summary.coverage.requester_safe)} />
      <OpsCard description="Searches that returned no usable article" title="Zero-result searches" value={metricValue(summary.search.zero_result_searches)} />
      <OpsCard description="Ask/RAG attempts without enough evidence" title="RAG no-answer" value={metricValue(summary.rag.no_answer_count)} />
      <OpsCard description="Index jobs requiring attention" title="Failed indexing jobs" value={metricValue(summary.indexing.failed)} />
      <OpsCard description="Average explainable content score" title="Average quality" value={summary.quality.average_score.toFixed(1)} />
      <OpsCard description="Open tasks assigned to curators" title="Assigned review tasks" value={metricValue(summary.review.assigned_open)} />
      <OpsCard description="Graph nodes without linked article context" title="Graph orphan nodes" value={metricValue(summary.graph.orphan_nodes)} />
      <OpsCard description="Search/RAG/indexing policy blocks" title="AI policy blocks" value={metricValue(summary.ai.policy_blocks)} />
    </div>
  );
}

function MetadataModelPanel({ metadata }: { metadata?: KnowledgeMetadataBundle }) {
  const activeModel = metadata?.quality_models?.find((model) => model.is_default && model.status === "active") ?? metadata?.quality_models?.find((model) => model.status === "active");
  const weights = activeModel?.weights ?? {};
  const weightEntries = Object.entries(weights).slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Layers className="h-4 w-4" />
          Knowledge metadata model
        </CardTitle>
        <CardDescription>Taxonomy, typed properties, applicability rules and quality model coverage.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase text-slate-500">Taxonomy terms</p>
            <p className="text-2xl font-semibold text-slate-950">{metadata?.taxonomy_terms?.length ?? 0}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Properties</p>
            <p className="text-2xl font-semibold text-slate-950">{metadata?.property_definitions?.length ?? 0}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Applicability rules</p>
            <p className="text-2xl font-semibold text-slate-950">{metadata?.applicability_rules?.length ?? 0}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Item metadata</p>
            <p className="text-2xl font-semibold text-slate-950">{metadata?.item_metadata?.length ?? 0}</p>
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">Active quality model:</span>
            <Badge tone={activeModel ? "success" : "warning"}>{activeModel?.code ?? "builtin-default"}</Badge>
            <span className="text-slate-500">{activeModel?.title ?? "Built-in quality model"}</span>
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
            <p className="mt-2 text-xs text-slate-500">No custom quality weights configured.</p>
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
          <CardTitle>Knowledge Operations Center</CardTitle>
          <CardDescription>Загрузка operational snapshot...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (summaryQuery.isError || !summary) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardHeader>
          <CardTitle>Knowledge Operations Center</CardTitle>
          <CardDescription>Не удалось загрузить Knowledge Ops summary.</CardDescription>
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
            <h2 className="text-xl font-semibold text-slate-950">Knowledge Operations Center</h2>
            <Badge tone={statusTone(summary.status)}>{summary.status === "degraded" ? "Degraded" : "OK"}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600">Coverage, quality, search, RAG, indexing and Observer v2 health snapshot.</p>
        </div>
        <p className="text-sm text-slate-500">Updated {new Date(summary.generated_at).toLocaleString("ru-RU")}</p>
      </div>

      <SummaryGrid summary={summary} />

      <MetadataModelPanel metadata={metadataQuery.data} />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Search className="h-4 w-4" />
              Search and RAG
            </CardTitle>
            <CardDescription>Fallbacks, vector usage and query demand.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Fallback count: {metricValue(summary.search.fallback_count)}</p>
            <p>AI disabled count: {metricValue(summary.search.ai_disabled_count)}</p>
            <p>Vector/rerank usage: {metricValue(summary.search.vector_usage_count)} / {metricValue(summary.search.rerank_usage_count)}</p>
            <p>Top query: {topQuery ? `${topQuery.query} (${topQuery.count})` : "нет данных"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="h-4 w-4" />
              Coverage and Review
            </CardTitle>
            <CardDescription>Knowledge gaps and review workload.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Spaces: {metricValue(summary.coverage.spaces)}</p>
            <p>Published articles: {metricValue(summary.coverage.published_articles)}</p>
            <p>Services without KB: {metricValue(summary.coverage.services_without_kb)}</p>
            <p>Overdue reviews: {metricValue(summary.review.overdue)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-4 w-4" />
              AI, Indexing and Graph
            </CardTitle>
            <CardDescription>Provider, embedding and graph signal.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-700">
            <p>Provider health: {summary.ai.provider_health.status}</p>
            <p>Queued indexing jobs: {metricValue(summary.indexing.queued)}</p>
            <p>Stale/disabled embeddings: {metricValue(summary.indexing.stale_embeddings)} / {metricValue(summary.indexing.disabled)}</p>
            <p>Graph proposals: {metricValue(summary.graph.pending_proposals)}</p>
          </CardContent>
        </Card>
      </div>

      <Card className={degradations.length ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50"}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {degradations.length ? <ShieldAlert className="h-4 w-4 text-red-700" /> : <FileSearch className="h-4 w-4 text-emerald-700" />}
            Observer-backed degradation
          </CardTitle>
          <CardDescription>Active Observer v2 signals with knowledge source or event type.</CardDescription>
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
            <p className="text-sm text-emerald-800">Active knowledge degradations are not present.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GitBranch className="h-4 w-4" />
            Phase 12 integration scope
          </CardTitle>
          <CardDescription>First slice keeps authoring controls below and adds an operations snapshot above them.</CardDescription>
        </CardHeader>
      </Card>
    </section>
  );
}
