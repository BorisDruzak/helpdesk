type EdgeToolbarProps = {
  label: string;
  onSelect: () => void;
  selected: boolean;
};

export function EdgeToolbar({ label, onSelect, selected }: EdgeToolbarProps) {
  return (
    <button
      aria-label={`Выбрать подпись связи ${label}`}
      className={`nodrag nopan rounded-md border px-3 py-1.5 text-xs font-semibold shadow-sm transition-colors ${
        selected ? "border-brand-400 bg-brand-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:border-brand-200 hover:bg-brand-50"
      }`}
      onClick={onSelect}
      type="button"
    >
      {label}
    </button>
  );
}
