import { Search } from "lucide-react";

import type { KnowledgeGraphNode } from "../api";
import { nodeTypeLabel, visibilityLabel } from "./graphTypes";

type GraphExplorerProps = {
  isError: boolean;
  isLoading: boolean;
  nodes: KnowledgeGraphNode[];
  onSearchChange: (value: string) => void;
  onSelectNode: (stableKey: string) => void;
  search: string;
  selectedStableKey: string;
};

export function GraphExplorer({ isError, isLoading, nodes, onSearchChange, onSelectNode, search, selectedStableKey }: GraphExplorerProps) {
  const needle = search.trim().toLowerCase();
  const filteredNodes = needle
    ? nodes.filter((node) =>
        [node.label, node.stable_key, node.node_type, node.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle)),
      )
    : nodes;
  const visibleNodes = filteredNodes.slice(0, 10);
  const counts = {
    all: nodes.length,
    articles: nodes.filter((node) => node.node_type === "knowledge_item").length,
    services: nodes.filter((node) => node.node_type === "service").length,
    relations: nodes.filter((node) => node.status === "proposed").length,
  };

  return (
    <section className="surface-panel space-y-4 p-5">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-slate-950">Проводник</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">Поиск, фильтры и выбор узла для текущего окружения.</p>
      </div>
      <label className="block text-sm font-semibold text-slate-800">
        Поиск узла
        <span className="mt-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-slate-950 outline-none placeholder:text-slate-400"
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Название, статья, сервис"
            value={search}
          />
        </span>
      </label>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <span className="rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 font-semibold text-brand-800">Все узлы: {counts.all}</span>
        <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-600">Статьи: {counts.articles}</span>
        <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-600">Сервисы: {counts.services}</span>
        <span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-600">Черновики: {counts.relations}</span>
      </div>
      <div className="max-h-[330px] space-y-2 overflow-y-auto pr-1">
        {isLoading ? <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">Загрузка узлов...</p> : null}
        {isError ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">Не удалось загрузить узлы графа.</p> : null}
        {!isLoading && !isError && visibleNodes.length === 0 ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">Узлы не найдены.</p>
        ) : null}
        {visibleNodes.map((node) => (
          <button
            className={`w-full rounded-lg border px-3 py-3 text-left transition-colors ${
              node.stable_key === selectedStableKey ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50"
            }`}
            key={node.node_id}
            onClick={() => onSelectNode(node.stable_key)}
            type="button"
          >
            <span className="block text-sm font-semibold text-slate-950">{node.label}</span>
            <span className="mt-1 block text-xs text-slate-500">
              {nodeTypeLabel(node.node_type)} · {visibilityLabel(node.visibility)}
            </span>
            <span className="mt-1 block break-all text-[11px] text-slate-400">{node.stable_key}</span>
          </button>
        ))}
      </div>
      {filteredNodes.length > 10 ? <p className="text-xs text-slate-500">Показаны первые 10 из {filteredNodes.length}. Уточните поиск, чтобы сузить список.</p> : null}
    </section>
  );
}
