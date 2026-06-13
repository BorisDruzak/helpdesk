import { X } from "lucide-react";

import { Button } from "../../../components/ui/button";
import type { KnowledgeSpace } from "../api";
import { fieldClass, itemTypeOptions, textareaClass, type NewItemDraft, visibilityOptions } from "./knowledge-studio-model";

type NewDraftDrawerProps = {
  draft: NewItemDraft;
  isCreating: boolean;
  isOpen: boolean;
  onChange: (draft: NewItemDraft) => void;
  onClose: () => void;
  onCreate: () => void;
  spaces: KnowledgeSpace[];
};

export function NewDraftDrawer({ draft, isCreating, isOpen, onChange, onClose, onCreate, spaces }: NewDraftDrawerProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30" role="presentation">
      <div
        aria-modal="true"
        className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-200 bg-white p-6 shadow-xl"
        role="dialog"
        aria-label="Новый черновик"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">Новый черновик</h2>
            <p className="mt-1 text-sm text-slate-500">Минимальные поля для создания материала. Служебные значения скрыты в Advanced.</p>
          </div>
          <Button aria-label="Закрыть новый черновик" onClick={onClose} size="icon" variant="ghost">
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="mt-6 space-y-4">
          <label className="text-sm font-medium">
            Новый заголовок
            <input className={fieldClass} value={draft.title} onChange={(event) => onChange({ ...draft, title: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Новый slug
            <input className={fieldClass} value={draft.slug} onChange={(event) => onChange({ ...draft, slug: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Краткое описание нового черновика
            <textarea className={textareaClass} value={draft.summary} onChange={(event) => onChange({ ...draft, summary: event.target.value })} />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Пространство нового черновика
              <select className={fieldClass} value={draft.space_code} onChange={(event) => onChange({ ...draft, space_code: event.target.value })}>
                {spaces.map((space) => (
                  <option key={space.space_id} value={space.code}>
                    {space.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Тип нового черновика
              <select className={fieldClass} value={draft.item_type} onChange={(event) => onChange({ ...draft, item_type: event.target.value })}>
                {itemTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="text-sm font-medium">
            Видимость нового черновика
            <select className={fieldClass} value={draft.visibility} onChange={(event) => onChange({ ...draft, visibility: event.target.value })}>
              {visibilityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <summary className="cursor-pointer text-sm font-semibold text-slate-800">Advanced / служебные поля</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Владелец нового черновика
                <input className={fieldClass} value={draft.owner_actor_id} onChange={(event) => onChange({ ...draft, owner_actor_id: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Ревьюер нового черновика
                <input className={fieldClass} value={draft.reviewer_actor_id} onChange={(event) => onChange({ ...draft, reviewer_actor_id: event.target.value })} />
              </label>
              <label className="text-sm font-medium sm:col-span-2">
                Теги нового черновика
                <input className={fieldClass} value={draft.tags} onChange={(event) => onChange({ ...draft, tags: event.target.value })} />
              </label>
              <p className="sm:col-span-2 text-xs leading-5 text-slate-500">
                Эти поля временно вводятся вручную, пока для actor picker не подключён отдельный API.
              </p>
            </div>
          </details>

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <Button onClick={onClose} variant="outline">
              Отмена
            </Button>
            <Button disabled={!draft.title.trim() || !draft.slug.trim() || isCreating} onClick={onCreate}>
              Создать новый черновик
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
