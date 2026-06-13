import { Archive, Save } from "lucide-react";

import type { KnowledgeGraphEdge, KnowledgeGraphNode } from "../api";
import {
  RELATION_TYPE_OPTIONS,
  STATUS_OPTIONS,
  VISIBILITY_OPTIONS,
  fieldClass,
  nodeDisplayName,
  parseOptionalNumber,
  relationTypeLabel,
  type EdgeDraft,
  type SelectedEdgeDraft,
  visibilityLabel,
} from "./graphTypes";
import { edgeStableKeys } from "./graphValidation";

type EdgeInspectorProps = {
  archiving: boolean;
  connectionMessages: string[];
  creating: boolean;
  edgeDraft: EdgeDraft;
  edges: KnowledgeGraphEdge[];
  mode: "select" | "connect" | "add_node" | "pan" | "lasso";
  nodes: KnowledgeGraphNode[];
  nodesById: Map<string, KnowledgeGraphNode>;
  onArchiveEdge: () => void;
  onCreateEdge: () => void;
  onEdgeDraftChange: (draft: EdgeDraft) => void;
  onSaveEdge: () => void;
  onSelectedEdgeDraftChange: (draft: SelectedEdgeDraft) => void;
  selectedEdge: KnowledgeGraphEdge | null;
  selectedEdgeDraft: SelectedEdgeDraft;
  updating: boolean;
};

function nodeByStableKey(nodes: KnowledgeGraphNode[], stableKey: string) {
  return nodes.find((node) => node.stable_key === stableKey);
}

export function EdgeInspector({
  archiving,
  connectionMessages,
  creating,
  edgeDraft,
  mode,
  nodes,
  nodesById,
  onArchiveEdge,
  onCreateEdge,
  onEdgeDraftChange,
  onSaveEdge,
  onSelectedEdgeDraftChange,
  selectedEdge,
  selectedEdgeDraft,
  updating,
}: EdgeInspectorProps) {
  if (mode === "connect") {
    return (
      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-950">Черновик связи</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">Выберите источник, цель и тип связи. На холсте можно также протянуть связь между handles.</p>
        </div>
        <fieldset aria-label="Черновик связи" className="space-y-3">
          <label className="block text-sm font-semibold text-slate-800">
            Источник
            <select aria-label="Источник" className={fieldClass} onChange={(event) => onEdgeDraftChange({ ...edgeDraft, source_stable_key: event.target.value })} value={edgeDraft.source_stable_key}>
              <option value="">Выберите источник</option>
              {nodes.map((node) => (
                <option key={node.node_id} value={node.stable_key}>
                  {node.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Цель
            <select aria-label="Цель" className={fieldClass} onChange={(event) => onEdgeDraftChange({ ...edgeDraft, target_stable_key: event.target.value })} value={edgeDraft.target_stable_key}>
              <option value="">Выберите цель</option>
              {nodes.map((node) => (
                <option key={node.node_id} value={node.stable_key}>
                  {node.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Тип связи
            <select aria-label="Тип связи" className={fieldClass} onChange={(event) => onEdgeDraftChange({ ...edgeDraft, relation_type: event.target.value })} value={edgeDraft.relation_type}>
              {RELATION_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-xs text-slate-500">Код связи: {edgeDraft.relation_type}</span>
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Видимость связи
            <select aria-label="Видимость связи" className={fieldClass} onChange={(event) => onEdgeDraftChange({ ...edgeDraft, visibility: event.target.value })} value={edgeDraft.visibility}>
              {VISIBILITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">
            <p>
              Источник: <span className="font-semibold text-slate-900">{nodeDisplayName(nodeByStableKey(nodes, edgeDraft.source_stable_key))}</span>
            </p>
            <p>
              Цель: <span className="font-semibold text-slate-900">{nodeDisplayName(nodeByStableKey(nodes, edgeDraft.target_stable_key))}</span>
            </p>
            <p>
              Тип: <span className="font-semibold text-slate-900">{relationTypeLabel(edgeDraft.relation_type)}</span>
            </p>
          </div>
          {connectionMessages.length ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700">
              {connectionMessages.map((message) => (
                <p key={message}>{message}</p>
              ))}
            </div>
          ) : null}
          <button
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            disabled={!edgeDraft.source_stable_key || !edgeDraft.target_stable_key || creating}
            onClick={onCreateEdge}
            type="button"
          >
            <Save className="h-4 w-4" />
            Создать связь
          </button>
        </fieldset>
      </section>
    );
  }

  if (!selectedEdge) {
    return (
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h3 className="text-lg font-semibold text-slate-950">Свойства связи</h3>
        <p className="mt-2 text-sm leading-6 text-slate-500">Выберите связь на холсте, чтобы изменить тип, видимость или вес.</p>
      </section>
    );
  }

  const stableKeys = edgeStableKeys(selectedEdge, nodesById);
  const sourceNode = nodeByStableKey(nodes, stableKeys.sourceStableKey);
  const targetNode = nodeByStableKey(nodes, stableKeys.targetStableKey);
  const weightValue = parseOptionalNumber(selectedEdgeDraft.weight);

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-950">Свойства связи</h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">Редактирование выбранной связи сразу влияет на граф после сохранения.</p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6">
        <p>
          <span className="font-semibold text-slate-950">{nodeDisplayName(sourceNode)}</span> →{" "}
          <span className="font-semibold text-slate-950">{nodeDisplayName(targetNode)}</span>
        </p>
        <p className="text-slate-500">{relationTypeLabel(selectedEdge.relation_type)} · {visibilityLabel(selectedEdge.visibility)}</p>
      </div>
      <label className="block text-sm font-semibold text-slate-800">
        Тип выбранной связи
        <select aria-label="Тип выбранной связи" className={fieldClass} onChange={(event) => onSelectedEdgeDraftChange({ ...selectedEdgeDraft, relation_type: event.target.value })} value={selectedEdgeDraft.relation_type}>
          {RELATION_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-xs text-slate-500">Код связи: {selectedEdgeDraft.relation_type}</span>
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Видимость выбранной связи
        <select aria-label="Видимость выбранной связи" className={fieldClass} onChange={(event) => onSelectedEdgeDraftChange({ ...selectedEdgeDraft, visibility: event.target.value })} value={selectedEdgeDraft.visibility}>
          {VISIBILITY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Вес связи
        <input className={fieldClass} inputMode="decimal" onChange={(event) => onSelectedEdgeDraftChange({ ...selectedEdgeDraft, weight: event.target.value })} value={selectedEdgeDraft.weight} />
        {weightValue == null ? <span className="mt-1 block text-xs text-rose-600">Укажите число или оставьте поле пустым.</span> : null}
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Уверенность
        <input
          className={fieldClass}
          inputMode="decimal"
          onChange={(event) => onSelectedEdgeDraftChange({ ...selectedEdgeDraft, confidence_score: event.target.value })}
          placeholder="Например 0.8"
          value={selectedEdgeDraft.confidence_score}
        />
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Статус связи
        <select aria-label="Статус связи" className={fieldClass} onChange={(event) => onSelectedEdgeDraftChange({ ...selectedEdgeDraft, status: event.target.value })} value={selectedEdgeDraft.status}>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-500">
        <p>Связь сохраняется через API графа. При архивации она исчезает из активного маршрута, но история остаётся на backend.</p>
      </div>
      <div className="flex flex-col gap-2">
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          disabled={updating || weightValue == null}
          onClick={onSaveEdge}
          type="button"
        >
          <Save className="h-4 w-4" />
          Сохранить связь
        </button>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-rose-200 bg-rose-50 px-4 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60"
          disabled={archiving}
          onClick={onArchiveEdge}
          type="button"
        >
          <Archive className="h-4 w-4" />
          Архивировать связь
        </button>
      </div>
    </section>
  );
}
