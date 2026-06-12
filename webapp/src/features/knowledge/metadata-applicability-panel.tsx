import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { saveKnowledgeApplicabilityRules, type KnowledgeApplicabilityRule, type KnowledgeItem, type KnowledgeMetadataBundle } from "./api";
import { fieldClass, includeModeOptions, scopeTypeOptions, termsForSpace } from "./metadata-editor-common";

type RuleDraft = {
  include_mode: "include" | "exclude";
  priority: string;
  scope_ref: string;
  scope_type: string;
};

function emptyRule(): RuleDraft {
  return { include_mode: "include", priority: "100", scope_ref: "", scope_type: "service" };
}

export function MetadataApplicabilityPanel({
  items,
  metadata,
  onChanged,
}: {
  items: KnowledgeItem[];
  metadata?: KnowledgeMetadataBundle;
  onChanged: () => void;
}) {
  const [itemId, setItemId] = useState("");
  const [draft, setDraft] = useState<RuleDraft>(() => emptyRule());
  const selectedItem = items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const currentMetadata = (metadata?.item_metadata ?? []).find((row) => row.item_id === selectedItem?.item_id);
  const [rules, setRules] = useState<Array<Partial<KnowledgeApplicabilityRule>>>([]);
  const taxonomyTerms = useMemo(() => termsForSpace(metadata, selectedItem?.space_id ?? ""), [metadata, selectedItem?.space_id]);

  useEffect(() => {
    if (!itemId && items[0]?.item_id) {
      setItemId(items[0].item_id);
    }
  }, [itemId, items]);

  useEffect(() => {
    setRules(currentMetadata?.applicability_rules ?? []);
  }, [currentMetadata?.item_id]);

  const saveMutation = useMutation({
    mutationFn: () => saveKnowledgeApplicabilityRules(selectedItem?.item_id ?? "", rules),
    onSuccess: () => onChanged(),
  });

  function addRule() {
    if (!draft.scope_ref.trim()) {
      return;
    }
    setRules((current) => [
      ...current,
      {
        scope_type: draft.scope_type,
        scope_ref: draft.scope_ref.trim(),
        include_mode: draft.include_mode,
        priority: Number(draft.priority || 100),
      },
    ]);
    setDraft(emptyRule());
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>Правила применимости</CardTitle>
          <CardDescription>Правила описывают, где статья должна включаться или исключаться из рекомендаций.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Статья
            <select className={fieldClass} value={selectedItem?.item_id ?? ""} onChange={(event) => setItemId(event.target.value)}>
              {items.map((item) => (
                <option key={item.item_id} value={item.item_id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <div className="space-y-2">
            {rules.map((rule, index) => (
              <div key={`${rule.scope_type}-${rule.scope_ref}-${index}`} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">
                    {rule.scope_type}: {rule.scope_ref}
                  </span>
                  <Badge>{rule.include_mode === "exclude" ? "Исключить" : "Включить"}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">Приоритет {rule.priority ?? 100}</p>
              </div>
            ))}
            {!rules.length ? <p className="text-sm text-slate-500">Для выбранной статьи правил пока нет.</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Добавить правило</CardTitle>
          <CardDescription>Для taxonomy_term можно выбрать термин; для service/offering укажите код из Service Catalog.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Тип области
            <select className={fieldClass} value={draft.scope_type} onChange={(event) => setDraft({ ...draft, scope_type: event.target.value, scope_ref: "" })}>
              {scopeTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {draft.scope_type === "taxonomy_term" ? (
            <label className="text-sm font-medium">
              Значение области
              <select className={fieldClass} value={draft.scope_ref} onChange={(event) => setDraft({ ...draft, scope_ref: event.target.value })}>
                <option value="">Выберите термин</option>
                {taxonomyTerms.map((term) => (
                  <option key={term.term_id} value={term.term_id}>
                    {term.title}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="text-sm font-medium">
              Значение области
              <input className={fieldClass} value={draft.scope_ref} onChange={(event) => setDraft({ ...draft, scope_ref: event.target.value })} />
            </label>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Режим
              <select className={fieldClass} value={draft.include_mode} onChange={(event) => setDraft({ ...draft, include_mode: event.target.value as "include" | "exclude" })}>
                {includeModeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Приоритет
              <input className={fieldClass} type="number" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })} />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!draft.scope_ref.trim()} onClick={addRule} variant="outline">
              Добавить правило
            </Button>
            <Button disabled={!selectedItem || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
              Сохранить применимость
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
