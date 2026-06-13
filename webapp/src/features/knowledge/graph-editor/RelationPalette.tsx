import { RELATION_TYPE_OPTIONS } from "./graphTypes";

type RelationPaletteProps = {
  activeRelationType: string;
  onChooseRelation: (relationType: string) => void;
};

export function RelationPalette({ activeRelationType, onChooseRelation }: RelationPaletteProps) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-950">Палитра связей</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">Тип выбирается до протягивания связи или перед подтверждением.</p>
      </div>
      <div className="space-y-2">
        {RELATION_TYPE_OPTIONS.map((option) => (
          <button
            className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
              activeRelationType === option.value ? "border-brand-300 bg-brand-50 text-brand-900" : "border-slate-200 bg-white text-slate-700 hover:border-brand-200 hover:bg-brand-50"
            }`}
            key={option.value}
            onClick={() => onChooseRelation(option.value)}
            type="button"
          >
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{option.description}</span>
            <span className="mt-1 block text-[11px] text-slate-400">{option.value}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
