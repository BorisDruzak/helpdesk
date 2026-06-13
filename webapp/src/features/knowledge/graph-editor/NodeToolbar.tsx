import { Archive, Copy, ExternalLink, Link2, Pencil } from "lucide-react";

type NodeToolbarProps = {
  canOpenArticle: boolean;
  onArchive: () => void;
  onConnect: () => void;
  onDuplicate: () => void;
  onEdit: () => void;
  onOpenArticle: () => void;
};

const actionClass = "inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800";

export function NodeInlineToolbar({ canOpenArticle, onArchive, onConnect, onDuplicate, onEdit, onOpenArticle }: NodeToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 shadow-soft">
      {canOpenArticle ? (
        <button className={actionClass} onClick={onOpenArticle} type="button">
          <ExternalLink className="h-3.5 w-3.5" />
          Открыть
        </button>
      ) : null}
      <button className={actionClass} onClick={onConnect} type="button">
        <Link2 className="h-3.5 w-3.5" />
        Связать от узла
      </button>
      <button className={actionClass} onClick={onDuplicate} type="button">
        <Copy className="h-3.5 w-3.5" />
        Копия
      </button>
      <button className={actionClass} onClick={onEdit} type="button">
        <Pencil className="h-3.5 w-3.5" />
        Править
      </button>
      <button className={`${actionClass} text-rose-700 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-800`} onClick={onArchive} type="button">
        <Archive className="h-3.5 w-3.5" />
        В архив
      </button>
    </div>
  );
}
