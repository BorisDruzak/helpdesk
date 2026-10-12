import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioBlockPreview } from "./scenario-block-preview";

export function ScenarioPublicationSummary({ definition, offeringTitle }: { definition: ScenarioDraftDefinition; offeringTitle?: string }) {
  const blocks = definition.blocks ?? [];
  return <section aria-label="Итог сценария" className="min-w-0 space-y-3 break-words">
    <h2 className="text-lg font-semibold">Что увидит сотрудник</h2>
    <p className="font-medium">{definition.title}</p>
    {definition.description && <p>{definition.description}</p>}
    <p>Услуга: {offeringTitle || "Выбранная услуга"}</p>
    <p className="text-sm text-slate-500">Все шаги и возможные переходы. Фактическую ветвь выбирает сервер по ответам сотрудника; проверьте её на этапе «Тестирование».</p>
    <ol className="space-y-2">{blocks.map((block, index) => <li key={block.id}>
      <details className="min-w-0 rounded-xl border p-3"><summary className="cursor-pointer font-medium">{index + 1}. {block.title}</summary>
        <div className="mt-3"><ScenarioBlockPreview block={block} /></div>
        {!!block.transitions?.length && <p className="mt-2 text-sm">Далее: {block.transitions.map(transition => blocks.find(next => next.id === transition.to)?.title || "Шаг недоступен").join("; ")}</p>}
      </details>
    </li>)}</ol>
    {!blocks.length && <p>Шаги сценария ещё не добавлены.</p>}
  </section>;
}
