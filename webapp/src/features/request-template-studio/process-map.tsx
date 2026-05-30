import type { ProcessBlock, ProcessBlockKey } from "./studio-model";
import { ProcessBlockCard } from "./process-block-card";

export function ProcessMap({
  blocks,
  selectedBlockKey,
  onSelectBlock,
}: {
  blocks: ProcessBlock[];
  selectedBlockKey: ProcessBlockKey;
  onSelectBlock: (key: ProcessBlockKey) => void;
}) {
  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Карта настройки обращения</h2>
          <p className="mt-1 text-sm text-slate-600">Фиксированные блоки ведут от формы пользователя до проверки и публикации.</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {blocks.map((block) => (
          <ProcessBlockCard
            block={block}
            key={block.key}
            onSelect={() => onSelectBlock(block.key)}
            selected={block.key === selectedBlockKey}
          />
        ))}
      </div>
    </section>
  );
}
