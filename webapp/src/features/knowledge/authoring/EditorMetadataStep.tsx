import { ArticleMetadataPanel } from "../article-metadata-panel";
import type { KnowledgeItem, KnowledgeSpace } from "../api";
import { fieldClass, itemTypeOptions, type EditorDraft, visibilityOptions } from "./knowledge-studio-model";

type EditorMetadataStepProps = {
  draft: EditorDraft;
  onDraftChange: (patch: Partial<EditorDraft>) => void;
  selectedItem: KnowledgeItem | null;
  spaces: KnowledgeSpace[];
};

export function EditorMetadataStep({ draft, onDraftChange, selectedItem, spaces }: EditorMetadataStepProps) {
  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Куда попадёт статья</h3>
          <p className="mt-1 text-sm text-slate-500">Задайте пространство, тип материала и аудиторию до настройки таксономии и свойств.</p>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <label className="text-sm font-medium">
            Пространство статьи
            <select className={fieldClass} value={draft.space_code} onChange={(event) => onDraftChange({ space_code: event.target.value })}>
              {spaces.map((space) => (
                <option key={space.space_id} value={space.code}>
                  {space.title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Тип материала
            <select className={fieldClass} value={draft.item_type} onChange={(event) => onDraftChange({ item_type: event.target.value })}>
              {itemTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Кому видна статья
            <select className={fieldClass} value={draft.visibility} onChange={(event) => onDraftChange({ visibility: event.target.value })}>
              {visibilityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <details className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">Advanced / служебные поля статьи</summary>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <label className="text-sm font-medium">
            Адрес статьи
            <input className={fieldClass} value={draft.slug} onChange={(event) => onDraftChange({ slug: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Теги
            <input className={fieldClass} value={draft.tags} onChange={(event) => onDraftChange({ tags: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Владелец
            <input className={fieldClass} value={draft.owner_actor_id} onChange={(event) => onDraftChange({ owner_actor_id: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Ревьюер
            <input className={fieldClass} value={draft.reviewer_actor_id} onChange={(event) => onDraftChange({ reviewer_actor_id: event.target.value })} />
          </label>
        </div>
      </details>
      <ArticleMetadataPanel embedded item={selectedItem} canManage={Boolean(selectedItem)} />
    </div>
  );
}
