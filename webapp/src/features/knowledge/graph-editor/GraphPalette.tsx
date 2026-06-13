import { NODE_TYPE_OPTIONS, nodeTypeClassName } from "./graphTypes";

type GraphPaletteProps = {
  activeNodeType: string;
  onChooseNodeType: (nodeType: string) => void;
};

export function GraphPalette({ activeNodeType, onChooseNodeType }: GraphPaletteProps) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-950">Палитра узлов</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">Выберите тип и добавьте узел на холст.</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {NODE_TYPE_OPTIONS.map((option) => (
          <button
            className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold transition-colors ${nodeTypeClassName(option.value)} ${
              activeNodeType === option.value ? "ring-2 ring-brand-300" : ""
            }`}
            key={option.value}
            onClick={() => onChooseNodeType(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}
