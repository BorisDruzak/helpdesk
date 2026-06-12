import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Tabs } from "../../components/ui/tabs";
import {
  fetchKnowledgeApplicabilityRules,
  fetchKnowledgeItemMetadata,
  fetchKnowledgeMetadata,
  saveKnowledgeApplicabilityRules,
  saveKnowledgeItemMetadata,
  type KnowledgeApplicabilityRule,
  type KnowledgeItem,
} from "./api";
import {
  activeQualityScore,
  fieldClass,
  includeModeOptions,
  propertiesForItem,
  propertyInputToValue,
  propertyValueToInput,
  scopeTypeOptions,
  termsForSpace,
} from "./metadata-editor-common";

const tabs = [
  { label: "Таксономия", value: "taxonomy" },
  { label: "Свойства", value: "properties" },
  { label: "Применимость", value: "applicability" },
  { label: "Качество", value: "quality" },
];

type RuleDraft = {
  include_mode: "include" | "exclude";
  priority: string;
  scope_ref: string;
  scope_type: string;
};

function emptyRule(): RuleDraft {
  return { include_mode: "include", priority: "100", scope_ref: "", scope_type: "service" };
}

export function ArticleMetadataPanel({ canManage, item }: { canManage: boolean; item: KnowledgeItem | null }) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("taxonomy");
  const [selectedTermIds, setSelectedTermIds] = useState<string[]>([]);
  const [propertyValues, setPropertyValues] = useState<Record<string, string>>({});
  const [rules, setRules] = useState<Array<Partial<KnowledgeApplicabilityRule>>>([]);
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>(() => emptyRule());

  const metadataQuery = useQuery({ queryKey: ["knowledge-metadata"], queryFn: fetchKnowledgeMetadata, enabled: Boolean(item?.item_id) });
  const itemMetadataQuery = useQuery({
    queryKey: ["knowledge-item-metadata", item?.item_id],
    queryFn: () => fetchKnowledgeItemMetadata(item?.item_id ?? ""),
    enabled: Boolean(item?.item_id),
  });
  const applicabilityQuery = useQuery({
    queryKey: ["knowledge-item-applicability", item?.item_id],
    queryFn: () => fetchKnowledgeApplicabilityRules(item?.item_id ?? ""),
    enabled: Boolean(item?.item_id),
  });

  const metadata = metadataQuery.data;
  const taxonomyTerms = useMemo(() => termsForSpace(metadata, item?.space_id ?? "").filter((term) => term.status === "active"), [metadata, item?.space_id]);
  const propertyDefinitions = useMemo(() => propertiesForItem(metadata, item?.space_id ?? "", item?.item_type ?? ""), [metadata, item?.space_id, item?.item_type]);
  const activeModel = metadata?.quality_models?.find((model) => model.space_id === item?.space_id && model.is_default && model.status === "active") ?? metadata?.quality_models?.find((model) => model.is_default && model.status === "active");
  const missingRequired = propertyDefinitions.filter((definition) => definition.required && !String(propertyValues[definition.code] ?? "").trim());
  const previewScore = activeQualityScore(selectedTermIds, propertyValues, rules as KnowledgeApplicabilityRule[], propertyDefinitions);

  useEffect(() => {
    const itemMetadata = itemMetadataQuery.data;
    if (!itemMetadata) {
      return;
    }
    setSelectedTermIds(itemMetadata.taxonomy_terms?.map((term) => term.term_id) ?? []);
    setPropertyValues(
      Object.fromEntries(
        propertyDefinitions.map((definition) => [definition.code, propertyValueToInput(definition, itemMetadata.properties?.[definition.code])]),
      ),
    );
  }, [itemMetadataQuery.data?.item_id, propertyDefinitions.length]);

  useEffect(() => {
    setRules(applicabilityQuery.data ?? itemMetadataQuery.data?.applicability_rules ?? []);
  }, [applicabilityQuery.data, itemMetadataQuery.data?.item_id]);

  const saveMetadataMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeItemMetadata(item?.item_id ?? "", {
        taxonomy_term_ids: selectedTermIds,
        properties: Object.fromEntries(
          propertyDefinitions
            .filter((definition) => propertyValues[definition.code] != null)
            .map((definition) => [definition.code, propertyInputToValue(definition, propertyValues[definition.code] ?? "")]),
        ),
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(["knowledge-item-metadata", item?.item_id], result.item_metadata);
      queryClient.invalidateQueries({ queryKey: ["knowledge-metadata"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
  });

  const saveRulesMutation = useMutation({
    mutationFn: () => saveKnowledgeApplicabilityRules(item?.item_id ?? "", rules),
    onSuccess: (result) => {
      setRules(result.rules);
      queryClient.setQueryData(["knowledge-item-applicability", item?.item_id], result.rules);
      queryClient.invalidateQueries({ queryKey: ["knowledge-metadata"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
  });

  function toggleTerm(termId: string) {
    setSelectedTermIds((current) => (current.includes(termId) ? current.filter((value) => value !== termId) : [...current, termId]));
  }

  function addRule() {
    if (!ruleDraft.scope_ref.trim()) {
      return;
    }
    setRules((current) => [
      ...current,
      {
        scope_type: ruleDraft.scope_type,
        scope_ref: ruleDraft.scope_ref.trim(),
        include_mode: ruleDraft.include_mode,
        priority: Number(ruleDraft.priority || 100),
      },
    ]);
    setRuleDraft(emptyRule());
  }

  if (!item) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Метаданные статьи</CardTitle>
          <CardDescription>Выберите статью для редактирования таксономии, свойств и применимости.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Метаданные статьи</CardTitle>
        <CardDescription>Таксономия, свойства, применимость и качество выбранного материала.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs items={tabs} onValueChange={setActiveTab} value={activeTab} />
        {metadataQuery.isLoading || itemMetadataQuery.isLoading ? <p className="text-sm text-slate-500">Загрузка метаданных статьи...</p> : null}

        {activeTab === "taxonomy" ? (
          <div className="space-y-3" data-testid="article-metadata-taxonomy">
            {taxonomyTerms.map((term) => (
              <label key={term.term_id} className="flex items-start gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm">
                <input aria-label={`Термин ${term.title}`} checked={selectedTermIds.includes(term.term_id)} disabled={!canManage} onChange={() => toggleTerm(term.term_id)} type="checkbox" />
                <span>
                  <span className="block font-medium">Термин {term.title}</span>
                  <span className="text-xs text-slate-500">
                    {term.term_type} · {term.code} · {term.visibility}
                  </span>
                </span>
              </label>
            ))}
            {!taxonomyTerms.length ? <p className="text-sm text-slate-500">Для пространства статьи нет активных терминов.</p> : null}
          </div>
        ) : null}

        {activeTab === "properties" ? (
          <div className="space-y-3">
            {missingRequired.map((definition) => (
              <p key={definition.property_id} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Не заполнено обязательное свойство: {definition.title}
              </p>
            ))}
            {propertyDefinitions.map((definition) => (
              <label key={definition.property_id} className="text-sm font-medium">
                Свойство {definition.title}
                {definition.value_type === "select" || definition.value_type === "multi_select" ? (
                  <select
                    className={fieldClass}
                    disabled={!canManage}
                    multiple={definition.value_type === "multi_select"}
                    value={propertyValues[definition.code] ?? ""}
                    onChange={(event) => setPropertyValues({ ...propertyValues, [definition.code]: event.target.value })}
                  >
                    <option value="">Не выбрано</option>
                    {(definition.allowed_values ?? []).map((value) => (
                      <option key={String(value)} value={String(value)}>
                        {String(value)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className={fieldClass}
                    disabled={!canManage}
                    value={propertyValues[definition.code] ?? ""}
                    onChange={(event) => setPropertyValues({ ...propertyValues, [definition.code]: event.target.value })}
                  />
                )}
              </label>
            ))}
            <Button disabled={!canManage || saveMetadataMutation.isPending} onClick={() => saveMetadataMutation.mutate()}>
              Сохранить метаданные статьи
            </Button>
          </div>
        ) : null}

        {activeTab === "applicability" ? (
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-2">
              {rules.map((rule, index) => (
                <div key={`${rule.scope_type}-${rule.scope_ref}-${index}`} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                  {rule.include_mode === "exclude" ? "Исключить" : "Включить"} · {rule.scope_type}: {rule.scope_ref}
                </div>
              ))}
              {!rules.length ? <p className="text-sm text-slate-500">Правил применимости пока нет.</p> : null}
            </div>
            <div className="space-y-3">
              <label className="text-sm font-medium">
                Тип области статьи
                <select className={fieldClass} value={ruleDraft.scope_type} onChange={(event) => setRuleDraft({ ...ruleDraft, scope_type: event.target.value })}>
                  {scopeTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium">
                Значение области статьи
                <input className={fieldClass} value={ruleDraft.scope_ref} onChange={(event) => setRuleDraft({ ...ruleDraft, scope_ref: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Режим правила статьи
                <select className={fieldClass} value={ruleDraft.include_mode} onChange={(event) => setRuleDraft({ ...ruleDraft, include_mode: event.target.value as "include" | "exclude" })}>
                  {includeModeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!canManage || !ruleDraft.scope_ref.trim()} onClick={addRule} variant="outline">
                  Добавить правило статьи
                </Button>
                <Button disabled={!canManage || saveRulesMutation.isPending} onClick={() => saveRulesMutation.mutate()}>
                  Сохранить правила статьи
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {activeTab === "quality" ? (
          <div className="space-y-2 text-sm text-slate-700">
            <p>Модель: {activeModel?.code ?? "builtin-default"}</p>
            <p>Предварительная оценка: {previewScore}</p>
            <p>Термины: {selectedTermIds.length}; свойства: {propertyDefinitions.length - missingRequired.length}/{propertyDefinitions.length}; правила: {rules.length}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
