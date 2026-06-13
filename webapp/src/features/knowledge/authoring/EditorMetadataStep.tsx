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
      <div className="grid gap-3 lg:grid-cols-2">
        <label className="text-sm font-medium">
          Slug
          <input className={fieldClass} value={draft.slug} onChange={(event) => onDraftChange({ slug: event.target.value })} />
        </label>
        <label className="text-sm font-medium">
          Пространство
          <select className={fieldClass} value={draft.space_code} onChange={(event) => onDraftChange({ space_code: event.target.value })}>
            {spaces.map((space) => (
              <option key={space.space_id} value={space.code}>
                {space.title}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Тип
          <select className={fieldClass} value={draft.item_type} onChange={(event) => onDraftChange({ item_type: event.target.value })}>
            {itemTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Видимость
          <select className={fieldClass} value={draft.visibility} onChange={(event) => onDraftChange({ visibility: event.target.value })}>
            {visibilityOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Теги
          <input className={fieldClass} value={draft.tags} onChange={(event) => onDraftChange({ tags: event.target.value })} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Владелец
            <input className={fieldClass} value={draft.owner_actor_id} onChange={(event) => onDraftChange({ owner_actor_id: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Ревьюер
            <input className={fieldClass} value={draft.reviewer_actor_id} onChange={(event) => onDraftChange({ reviewer_actor_id: event.target.value })} />
          </label>
        </div>
      </div>
      <ArticleMetadataPanel embedded item={selectedItem} canManage={Boolean(selectedItem)} />
    </div>
  );
}
