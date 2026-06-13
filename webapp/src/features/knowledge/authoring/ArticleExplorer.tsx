import { FileText, PlusCircle, Search } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import type { KnowledgeItem } from "../api";
import { fieldClass, statusFilterOptions, statusLabel, visibilityLabel } from "./knowledge-studio-model";

type ArticleExplorerProps = {
  isLoading: boolean;
  items: KnowledgeItem[];
  onOpenNewDraft: () => void;
  onSearchChange: (value: string) => void;
  onSelectItem: (itemId: string) => void;
  onStatusFilterChange: (value: string) => void;
  search: string;
  selectedItem: KnowledgeItem | null;
  statusFilter: string;
};

export function ArticleExplorer({
  isLoading,
  items,
  onOpenNewDraft,
  onSearchChange,
  onSelectItem,
  onStatusFilterChange,
  search,
  selectedItem,
  statusFilter,
}: ArticleExplorerProps) {
  return (
    <Card className="flex min-h-[calc(100vh-14rem)] flex-col overflow-hidden">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Черновики и статьи
        </CardTitle>
        <CardDescription>Выбор материала, фильтры и создание черновика.</CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        <label className="text-sm font-medium">
          <span className="flex items-center gap-2 text-slate-700">
            <Search className="h-4 w-4" />
            Поиск
          </span>
          <input
            className={fieldClass}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="принтер, vpn, категория"
            value={search}
          />
        </label>

        <div className="flex flex-wrap gap-2" aria-label="Фильтры статуса статей">
          {statusFilterOptions.map((filter) => (
            <button
              className={`rounded-pill border px-3 py-1 text-xs font-semibold transition-colors ${
                statusFilter === filter.value
                  ? "border-brand-200 bg-brand-50 text-brand-800"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
              key={filter.value}
              onClick={() => onStatusFilterChange(filter.value)}
              type="button"
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1" data-testid="knowledge-article-explorer">
          {isLoading ? <p className="text-sm text-slate-500">Загрузка статей...</p> : null}
          {items.map((item) => (
            <button
              key={item.item_id}
              className={`w-full rounded-lg border px-3 py-3 text-left text-sm transition-colors ${
                item.item_id === selectedItem?.item_id
                  ? "border-brand-300 bg-brand-50 shadow-soft"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
              onClick={() => onSelectItem(item.item_id)}
              type="button"
            >
              <span className="block truncate font-semibold text-slate-950">{item.title}</span>
              <span className="mt-1 block truncate text-xs text-slate-500">{item.slug}</span>
              <span className="mt-2 flex flex-wrap gap-2">
                <Badge tone={item.status === "published" ? "success" : item.status === "archived" ? "danger" : "warning"}>
                  {statusLabel(item.status)}
                </Badge>
                <Badge tone="neutral">{visibilityLabel(item.visibility)}</Badge>
              </span>
            </button>
          ))}
          {!isLoading && !items.length ? <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">Нет статей для выбранного фильтра.</p> : null}
        </div>

        <Button className="mt-2 w-full" onClick={onOpenNewDraft} variant="secondary" leadingIcon={<PlusCircle className="h-4 w-4" />}>
          Новый черновик
        </Button>
      </CardContent>
    </Card>
  );
}
