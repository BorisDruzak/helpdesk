import { useState } from "react";

import { ArticleHelpDeskBindingPanel } from "../article-helpdesk-binding-panel";
import { ArticleMetadataPanel } from "../article-metadata-panel";
import { ArticleVisibilityPanel } from "../article-visibility-panel";
import type { KnowledgeItem, KnowledgeSpace } from "../api";
import { aiRagPolicyOptions, fieldClass, itemTypeOptions, type EditorDraft, visibilityOptions } from "./knowledge-studio-model";

type EditorMetadataStepProps = {
  draft: EditorDraft;
  onDraftChange: (patch: Partial<EditorDraft>) => void;
  selectedItem: KnowledgeItem | null;
  spaces: KnowledgeSpace[];
};

const articleLengthRecommendationLabels: Record<string, string> = {
  short: "короткая статья до 2 экранов",
  standard: "стандартная статья на 3-5 экранов",
  detailed: "подробный runbook или регламент",
};

export function EditorMetadataStep({ draft, onDraftChange, selectedItem, spaces }: EditorMetadataStepProps) {
  const [showAdvancedMetadata, setShowAdvancedMetadata] = useState(false);
  const selectedSpace = spaces.find((space) => space.code === draft.space_code);
  const articleLengthRecommendation =
    typeof selectedSpace?.metadata?.article_length_recommendation === "string"
      ? articleLengthRecommendationLabels[selectedSpace.metadata.article_length_recommendation] ?? selectedSpace.metadata.article_length_recommendation
      : "";

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Основные настройки статьи</h3>
          <p className="mt-1 text-sm text-slate-500">Задайте раздел, тип материала и базовый доступ перед сохранением статьи.</p>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div>
            <label className="text-sm font-medium">
              Раздел базы знаний
              <select className={fieldClass} value={draft.space_code} onChange={(event) => onDraftChange({ space_code: event.target.value })}>
                {spaces.map((space) => (
                  <option key={space.space_id} value={space.code}>
                    {space.title}
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Раздел определяет, где хранится статья и какие политики применяются по умолчанию: видимость, аудитория, RAG, импорт и допустимые типы материалов.
              {articleLengthRecommendation ? ` Рекомендация раздела: ${articleLengthRecommendation}.` : ""}
            </p>
          </div>
          <div>
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
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Тип определяет шаблон и смысл статьи. Для обычной инструкции выбирайте «Инструкция / статья».
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">
              Кому доступна статья
              <select className={fieldClass} value={draft.visibility} onChange={(event) => onDraftChange({ visibility: event.target.value })}>
                {visibilityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Это базовый уровень доступа. Он ограничивает, кто вообще может получить статью: заявитель, агент, поддержка, администратор.
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">
              Использовать в AI/RAG
              <select className={fieldClass} value={draft.ai_rag_policy} onChange={(event) => onDraftChange({ ai_rag_policy: event.target.value })}>
                {aiRagPolicyOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Второй фильтр перед AI-ответами и цитатами. Он не расширяет видимость статьи; по умолчанию наследует раздел
              {selectedSpace ? ` (${selectedSpace.allow_rag ? "RAG включён" : "RAG отключён"})` : ""}.
            </p>
          </div>
        </div>
      </section>

      <ArticleVisibilityPanel canManage={Boolean(selectedItem)} coarseVisibility={draft.visibility} item={selectedItem} />

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-base font-semibold text-slate-950">Где показывать статью</h3>
        <p className="mt-1 text-sm text-slate-500">
          Определяет, в каких сценариях система будет предлагать статью: портал заявителя, форма обращения, карточка тикета, агент, AI/RAG.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-700">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">Портал заявителя</span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">Форма обращения</span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">Карточка тикета</span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
            {aiRagPolicyOptions.find((option) => option.value === draft.ai_rag_policy)?.label ?? "AI/RAG по политике раздела"}
          </span>
        </div>
      </section>

      <ArticleHelpDeskBindingPanel item={selectedItem} visibility={draft.visibility} />

      <details className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">Advanced / служебные поля</summary>
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
        </div>
      </details>
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">Расширенные метаданные</h3>
            <p className="mt-1 text-sm text-slate-500">Таксономия, свойства, применимость и качество доступны для тонкой настройки.</p>
          </div>
          <button
            className="rounded-pill border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
            onClick={() => setShowAdvancedMetadata((current) => !current)}
            type="button"
          >
            {showAdvancedMetadata ? "Скрыть advanced" : "Показать advanced"}
          </button>
        </div>
        {showAdvancedMetadata ? <div className="mt-4"><ArticleMetadataPanel embedded item={selectedItem} canManage={Boolean(selectedItem)} /></div> : null}
      </section>
    </div>
  );
}
