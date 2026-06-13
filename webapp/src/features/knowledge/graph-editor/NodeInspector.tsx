import { Archive, Copy, ExternalLink, Link2, Save } from "lucide-react";

import { AdvancedDisclosure } from "../../../components/ui-page/advanced-disclosure";
import type { KnowledgeGraphNode } from "../api";
import {
  NODE_TYPE_OPTIONS,
  STATUS_OPTIONS,
  VISIBILITY_OPTIONS,
  fieldClass,
  generateStableKey,
  nodeTypeLabel,
  statusLabel,
  type NodeDraft,
  type SelectedNodeDraft,
  visibilityLabel,
} from "./graphTypes";

type NodeInspectorProps = {
  archiving: boolean;
  creating: boolean;
  mode: "select" | "add_node" | "connect" | "pan" | "lasso";
  nodeDraft: NodeDraft;
  onArchiveNode: () => void;
  onCreateNode: () => void;
  onDuplicateNode: () => void;
  onNodeDraftChange: (draft: NodeDraft) => void;
  onSaveNode: () => void;
  onSelectedDraftChange: (draft: SelectedNodeDraft) => void;
  onStartConnect: () => void;
  quickCreatePosition: { x: number; y: number } | null;
  selectedDraft: SelectedNodeDraft;
  selectedNode: KnowledgeGraphNode | null;
  updating: boolean;
};

export function NodeInspector({
  archiving,
  creating,
  mode,
  nodeDraft,
  onArchiveNode,
  onCreateNode,
  onDuplicateNode,
  onNodeDraftChange,
  onSaveNode,
  onSelectedDraftChange,
  onStartConnect,
  quickCreatePosition,
  selectedDraft,
  selectedNode,
  updating,
}: NodeInspectorProps) {
  if (mode === "add_node") {
    const generatedStableKey = generateStableKey(nodeDraft.node_type, nodeDraft.label);
    return (
      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-950">Быстрое создание узла</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">Основные поля задаются здесь, позиция берётся из клика по холсту или центра текущего вида.</p>
        </div>
        <label className="block text-sm font-semibold text-slate-800">
          Название нового узла
          <input className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, label: event.target.value })} value={nodeDraft.label} />
        </label>
        <label className="block text-sm font-semibold text-slate-800">
          Тип нового узла
          <select aria-label="Тип нового узла" className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, node_type: event.target.value })} value={nodeDraft.node_type}>
            {NODE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="mt-1 block text-xs text-slate-500">Код типа: {nodeDraft.node_type}</span>
        </label>
        <label className="block text-sm font-semibold text-slate-800">
          Видимость нового узла
          <select aria-label="Видимость нового узла" className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, visibility: event.target.value })} value={nodeDraft.visibility}>
            {VISIBILITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <AdvancedDisclosure description="Технические ссылки нужны для импорта, миграций и точной привязки к статье или каталогу." title="Дополнительно: технические ссылки">
          <label className="block text-sm font-semibold text-slate-800">
            ID статьи
            <input className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, linked_item_id: event.target.value })} value={nodeDraft.linked_item_id} />
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Код сервиса
            <input className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, service_code: event.target.value })} value={nodeDraft.service_code} />
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Код услуги
            <input className={fieldClass} onChange={(event) => onNodeDraftChange({ ...nodeDraft, offering_code: event.target.value })} value={nodeDraft.offering_code} />
          </label>
        </AdvancedDisclosure>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">
          <p className="font-semibold text-slate-800">Будет создан ключ: {generatedStableKey}</p>
          <p>{quickCreatePosition ? `Позиция на холсте: ${Math.round(quickCreatePosition.x)}, ${Math.round(quickCreatePosition.y)}` : "Позиция: центр холста"}</p>
        </div>
        <button
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          disabled={!nodeDraft.label.trim() || creating}
          onClick={onCreateNode}
          type="button"
        >
          <Save className="h-4 w-4" />
          Создать узел
        </button>
      </section>
    );
  }

  if (!selectedNode) {
    return (
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h3 className="text-lg font-semibold text-slate-950">Свойства узла</h3>
        <p className="mt-2 text-sm leading-6 text-slate-500">Выберите узел на холсте или в проводнике.</p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-950">Свойства узла</h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">Редактирование выбранного узла и переход к связанной статье.</p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <p className="text-base font-semibold text-slate-950">{selectedNode.label}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-pill bg-brand-50 px-3 py-1 font-semibold text-brand-800">{nodeTypeLabel(selectedNode.node_type)}</span>
          <span className="rounded-pill bg-slate-100 px-3 py-1 font-semibold text-slate-700">{visibilityLabel(selectedNode.visibility)}</span>
          <span className="rounded-pill bg-emerald-50 px-3 py-1 font-semibold text-emerald-700">{statusLabel(selectedNode.status)}</span>
        </div>
      </div>
      <label className="block text-sm font-semibold text-slate-800">
        Название узла
        <input className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, label: event.target.value })} value={selectedDraft.label} />
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Тип узла
        <select aria-label="Тип узла" className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, node_type: event.target.value })} value={selectedDraft.node_type}>
          {NODE_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-xs text-slate-500">Код типа: {selectedDraft.node_type}</span>
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Видимость узла
        <select aria-label="Видимость узла" className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, visibility: event.target.value })} value={selectedDraft.visibility}>
          {VISIBILITY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-semibold text-slate-800">
        Статус узла
        <select aria-label="Статус узла" className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, status: event.target.value })} value={selectedDraft.status}>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <AdvancedDisclosure description="Ключи и коды не являются основным способом работы, но доступны для точной диагностики." title="Дополнительно: технические ссылки">
        <label className="block text-sm font-semibold text-slate-800">
          Ключ узла
          <span className="mt-1 flex gap-2">
            <input className={fieldClass} readOnly value={selectedNode.stable_key} />
            <button className="mt-1 rounded-md border border-slate-200 px-3 text-xs font-semibold text-slate-700" onClick={() => void navigator.clipboard?.writeText(selectedNode.stable_key)} type="button">
              <Copy className="h-4 w-4" />
            </button>
          </span>
        </label>
        <label className="block text-sm font-semibold text-slate-800">
          ID статьи
          <input className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, linked_item_id: event.target.value })} value={selectedDraft.linked_item_id} />
        </label>
        <label className="block text-sm font-semibold text-slate-800">
          Код сервиса
          <input className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, service_code: event.target.value })} value={selectedDraft.service_code} />
        </label>
        <label className="block text-sm font-semibold text-slate-800">
          Код услуги
          <input className={fieldClass} onChange={(event) => onSelectedDraftChange({ ...selectedDraft, offering_code: event.target.value })} value={selectedDraft.offering_code} />
        </label>
      </AdvancedDisclosure>
      <div className="flex flex-col gap-2">
        {selectedNode.linked_item_id ? (
          <a
            className="inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-brand-200 bg-brand-50 px-4 text-sm font-semibold text-brand-800 hover:bg-brand-100"
            href={`/app/admin/knowledge/studio?item=${encodeURIComponent(selectedNode.linked_item_id)}`}
          >
            <ExternalLink className="h-4 w-4" />
            Открыть статью в Студии
          </a>
        ) : null}
        <button className="inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50" onClick={onStartConnect} type="button">
          <Link2 className="h-4 w-4" />
          Создать связь от узла
        </button>
        <button className="inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50" onClick={onDuplicateNode} type="button">
          <Copy className="h-4 w-4" />
          Дублировать как черновик
        </button>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          disabled={!selectedDraft.label.trim() || updating}
          onClick={onSaveNode}
          type="button"
        >
          <Save className="h-4 w-4" />
          Сохранить узел
        </button>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-pill border border-rose-200 bg-rose-50 px-4 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60"
          disabled={archiving}
          onClick={onArchiveNode}
          type="button"
        >
          <Archive className="h-4 w-4" />
          Архивировать узел
        </button>
      </div>
    </section>
  );
}
