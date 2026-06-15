import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, GitBranch, Link2 } from "lucide-react";

import type { KnowledgeGraphEdge, KnowledgeGraphNode, KnowledgeItem } from "./api";
import { fetchKnowledgeGraphNeighborhood, searchKnowledgeGraph } from "./api";

type ArticleRelatedGraphPanelProps = {
  item: KnowledgeItem | null;
};

function graphSearchQuery(item: KnowledgeItem | null) {
  if (!item) {
    return "";
  }
  return item.slug || item.title || item.item_id;
}

function findCurrentArticleNode(nodes: KnowledgeGraphNode[], item: KnowledgeItem | null) {
  if (!item) {
    return null;
  }
  const expectedStableKey = item.slug ? `knowledge_item:${item.slug}` : "";
  const title = item.title.trim().toLowerCase();
  return (
    nodes.find((node) => node.linked_item_id === item.item_id) ??
    nodes.find((node) => expectedStableKey && node.stable_key === expectedStableKey) ??
    nodes.find((node) => node.node_type === "knowledge_item" && node.label.trim().toLowerCase() === title) ??
    null
  );
}

function adjacentNodeIds(currentNode: KnowledgeGraphNode | null, edges: KnowledgeGraphEdge[]) {
  if (!currentNode) {
    return new Set<string>();
  }
  const ids = new Set<string>();
  for (const edge of edges) {
    if (edge.source_node_id === currentNode.node_id) {
      ids.add(edge.target_node_id);
    }
    if (edge.target_node_id === currentNode.node_id) {
      ids.add(edge.source_node_id);
    }
  }
  return ids;
}

function relationSummary(nodes: KnowledgeGraphNode[], currentNode: KnowledgeGraphNode | null, edges: KnowledgeGraphEdge[], item: KnowledgeItem | null) {
  const connectedIds = adjacentNodeIds(currentNode, edges);
  return nodes
    .filter((node) => connectedIds.has(node.node_id))
    .filter((node) => node.node_type === "knowledge_item")
    .filter((node) => node.linked_item_id && node.linked_item_id !== item?.item_id)
    .slice(0, 4);
}

export function ArticleRelatedGraphPanel({ item }: ArticleRelatedGraphPanelProps) {
  const queryText = graphSearchQuery(item);
  const graphSearch = useQuery({
    queryKey: ["knowledge-related-graph-search", item?.item_id, queryText],
    queryFn: () => searchKnowledgeGraph(queryText),
    enabled: Boolean(item?.item_id && queryText),
  });
  const currentNode = useMemo(() => findCurrentArticleNode(graphSearch.data?.nodes ?? [], item), [graphSearch.data?.nodes, item]);
  const neighborhood = useQuery({
    queryKey: ["knowledge-related-graph-neighborhood", currentNode?.stable_key],
    queryFn: () => fetchKnowledgeGraphNeighborhood(currentNode?.stable_key ?? "", 1),
    enabled: Boolean(currentNode?.stable_key),
  });
  const relatedNodes = useMemo(
    () => relationSummary(neighborhood.data?.nodes ?? [], currentNode, neighborhood.data?.edges ?? [], item),
    [currentNode, item, neighborhood.data?.edges, neighborhood.data?.nodes],
  );
  const isLoading = graphSearch.isLoading || neighborhood.isLoading;
  const isError = graphSearch.isError || neighborhood.isError;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-semibold text-slate-950">
            <Link2 className="h-4 w-4" />
            Связанные статьи
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Лёгкий список из графа знаний для просмотра связей. Обычное сохранение статьи работает без графа.
          </p>
        </div>
        <a
          className="inline-flex h-9 items-center justify-center gap-2 rounded-pill border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
          href="/app/admin/knowledge/graph"
        >
          <GitBranch className="h-4 w-4" />
          Открыть advanced Graph
        </a>
      </div>

      <div className="mt-3 space-y-2">
        {!item ? <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">Выберите или создайте статью, чтобы увидеть связи графа.</p> : null}
        {isLoading ? <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">Ищем связи графа...</p> : null}
        {isError ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Не удалось загрузить связи графа. Авторинг и сохранение статьи не блокируются.
          </p>
        ) : null}
        {!isLoading && !isError && item && !currentNode ? (
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
            Для статьи ещё нет узла графа. Связи можно настроить в advanced Graph, если они нужны для discovery.
          </p>
        ) : null}
        {!isLoading && !isError && currentNode && relatedNodes.length === 0 ? (
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
            Связанные статьи пока не настроены. Обычное сохранение статьи работает без графа.
          </p>
        ) : null}
        {relatedNodes.map((node) => (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2" key={node.node_id}>
            <p className="text-sm font-semibold text-slate-950">{node.label}</p>
            <p className="mt-1 text-xs text-slate-500">Источник: graph relation · {node.visibility}</p>
            <a
              className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-brand-800 hover:text-brand-900"
              href={`/app/admin/knowledge/studio?item=${encodeURIComponent(node.linked_item_id ?? "")}`}
            >
              <ExternalLink className="h-4 w-4" />
              Открыть связанную статью
            </a>
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs leading-5 text-slate-500">
        Graph остаётся advanced workbench для related articles, duplicates, supersedes, known error/workaround и service/article связей.
      </p>
    </section>
  );
}
