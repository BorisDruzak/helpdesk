type ExpandedWorkspaceHeaderProps = {
  title: string;
  onReturnToTicket: () => void;
};

export function ExpandedWorkspaceHeader({ title, onReturnToTicket }: ExpandedWorkspaceHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/10 px-5 py-4">
      <h2 className="text-xl font-semibold text-white">{title}</h2>
      <button
        className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-200 hover:text-white"
        onClick={onReturnToTicket}
        type="button"
      >
        Вернуться к чату
      </button>
    </div>
  );
}
