import { useEffect, useId, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {
  fetchKnowledgeServiceCatalogOptions,
  type KnowledgeApplicabilityRule,
  type KnowledgeServiceCatalogOption,
  type KnowledgeTaxonomyTerm,
} from "./api";
import { fieldClass, includeModeLabel, includeModeOptions, scopeTypeLabel, scopeTypeOptions, taxonomyLabel } from "./metadata-editor-common";

type RuleDraft = {
  include_mode: "include" | "exclude";
  priority: string;
  scope_ref: string;
  scope_type: string;
};

export function emptyApplicabilityRuleDraft(): RuleDraft {
  return { include_mode: "include", priority: "100", scope_ref: "", scope_type: "service" };
}

type MetadataApplicabilityEditorProps = {
  addButtonLabel: string;
  canManage?: boolean;
  emptyMessage: string;
  onRulesChange: (rules: Array<Partial<KnowledgeApplicabilityRule>>) => void;
  onSave: () => void;
  rules: Array<Partial<KnowledgeApplicabilityRule>>;
  saveButtonLabel: string;
  saveDisabled?: boolean;
  saveMessage?: string;
  savePending?: boolean;
  scopeTypeLabelText: string;
  taxonomyTerms: KnowledgeTaxonomyTerm[];
  updateButtonLabel: string;
};

function scopeRefLabel(rule: Partial<KnowledgeApplicabilityRule>, taxonomyTerms: KnowledgeTaxonomyTerm[], serviceOptions: KnowledgeServiceCatalogOption[]) {
  if (rule.scope_type === "taxonomy_term") {
    const term = taxonomyTerms.find((candidate) => candidate.term_id === rule.scope_ref);
    return term ? taxonomyLabel(term) : rule.scope_ref || "Не задано";
  }
  const serviceOption = serviceOptions.find((candidate) => candidate.value === rule.scope_ref);
  return serviceOption?.value ?? rule.scope_ref ?? "Не задано";
}

function ruleDisplayLabel(rule: Partial<KnowledgeApplicabilityRule>, taxonomyTerms: KnowledgeTaxonomyTerm[], serviceOptions: KnowledgeServiceCatalogOption[]) {
  return `${scopeTypeLabel(rule.scope_type)}: ${scopeRefLabel(rule, taxonomyTerms, serviceOptions)}`;
}

function serviceOptionsForScope(options: KnowledgeServiceCatalogOption[], scopeType: string) {
  if (scopeType === "service") {
    return options.filter((option) => option.type === "service");
  }
  if (scopeType === "offering") {
    return options.filter((option) => option.type === "offering");
  }
  return [];
}

export function MetadataApplicabilityEditor({
  addButtonLabel,
  canManage = true,
  emptyMessage,
  onRulesChange,
  onSave,
  rules,
  saveButtonLabel,
  saveDisabled = false,
  saveMessage,
  savePending = false,
  scopeTypeLabelText,
  taxonomyTerms,
  updateButtonLabel,
}: MetadataApplicabilityEditorProps) {
  const serviceScopeInputId = useId();
  const serviceScopeListId = useId();
  const [draft, setDraft] = useState<RuleDraft>(() => emptyApplicabilityRuleDraft());
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const serviceCatalogQuery = useQuery({
    queryKey: ["knowledge-service-catalog-options"],
    queryFn: fetchKnowledgeServiceCatalogOptions,
  });
  const serviceOptions = serviceCatalogQuery.data ?? [];
  const scopeServiceOptions = useMemo(() => serviceOptionsForScope(serviceOptions, draft.scope_type), [serviceOptions, draft.scope_type]);
  const showServicePicker = draft.scope_type === "service" || draft.scope_type === "offering";

  useEffect(() => {
    setDraft(emptyApplicabilityRuleDraft());
    setEditingIndex(null);
  }, [taxonomyTerms]);

  function upsertRule() {
    if (!draft.scope_ref.trim()) {
      return;
    }
    const nextRule: Partial<KnowledgeApplicabilityRule> = {
      scope_type: draft.scope_type,
      scope_ref: draft.scope_ref.trim(),
      include_mode: draft.include_mode,
      priority: Number(draft.priority || 100),
    };
    if (editingIndex == null) {
      onRulesChange([...rules, nextRule]);
    } else {
      onRulesChange(rules.map((rule, index) => (index === editingIndex ? { ...rule, ...nextRule } : rule)));
    }
    setDraft(emptyApplicabilityRuleDraft());
    setEditingIndex(null);
  }

  function editRule(rule: Partial<KnowledgeApplicabilityRule>, index: number) {
    setDraft({
      include_mode: rule.include_mode === "exclude" ? "exclude" : "include",
      priority: String(rule.priority ?? 100),
      scope_ref: rule.scope_ref ?? "",
      scope_type: rule.scope_type ?? "service",
    });
    setEditingIndex(index);
  }

  function deleteRule(indexToDelete: number) {
    onRulesChange(rules.filter((_, index) => index !== indexToDelete));
    if (editingIndex === indexToDelete) {
      setDraft(emptyApplicabilityRuleDraft());
      setEditingIndex(null);
    } else if (editingIndex != null && indexToDelete < editingIndex) {
      setEditingIndex(editingIndex - 1);
    }
  }

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-2">
        {rules.map((rule, index) => {
          const displayLabel = ruleDisplayLabel(rule, taxonomyTerms, serviceOptions);
          return (
            <div key={`${rule.scope_type}-${rule.scope_ref}-${index}`} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{displayLabel}</span>
                <Badge>{includeModeLabel(rule.include_mode)}</Badge>
              </div>
              <p className="mt-1 text-xs text-slate-500">Приоритет {rule.priority ?? 100}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button disabled={!canManage} onClick={() => editRule(rule, index)} size="sm" type="button" variant="outline">
                  Редактировать правило {displayLabel}
                </Button>
                <Button disabled={!canManage} onClick={() => deleteRule(index)} size="sm" type="button" variant="outline">
                  Удалить правило {displayLabel}
                </Button>
              </div>
            </div>
          );
        })}
        {!rules.length ? <p className="text-sm text-slate-500">{emptyMessage}</p> : null}
      </div>

      <div className="space-y-3">
        <p className="rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          Выберите сервис или услугу из каталога, когда это возможно.
        </p>
        <label className="text-sm font-medium">
          {scopeTypeLabelText}
          <select
            className={fieldClass}
            disabled={!canManage}
            value={draft.scope_type}
            onChange={(event) => setDraft({ ...draft, scope_type: event.target.value, scope_ref: "" })}
          >
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
            <select className={fieldClass} disabled={!canManage} value={draft.scope_ref} onChange={(event) => setDraft({ ...draft, scope_ref: event.target.value })}>
              <option value="">Выберите термин</option>
              {taxonomyTerms.map((term) => (
                <option key={term.term_id} value={term.term_id}>
                  {taxonomyLabel(term)}
                </option>
              ))}
            </select>
          </label>
        ) : showServicePicker ? (
          <>
          <label className="text-sm font-medium" htmlFor={serviceScopeInputId}>
            Сервис или услуга
            <input
              className={fieldClass}
              disabled={!canManage}
              id={serviceScopeInputId}
              list={serviceScopeListId}
              value={draft.scope_ref}
              onChange={(event) => setDraft({ ...draft, scope_ref: event.target.value })}
            />
          </label>
            <datalist id={serviceScopeListId}>
              {scopeServiceOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </datalist>
          </>
        ) : (
          <label className="text-sm font-medium">
            Значение области
            <input className={fieldClass} disabled={!canManage} value={draft.scope_ref} onChange={(event) => setDraft({ ...draft, scope_ref: event.target.value })} />
          </label>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Режим
            <select
              className={fieldClass}
              disabled={!canManage}
              value={draft.include_mode}
              onChange={(event) => setDraft({ ...draft, include_mode: event.target.value as "include" | "exclude" })}
            >
              {includeModeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Приоритет
            <input className={fieldClass} disabled={!canManage} type="number" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })} />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canManage || !draft.scope_ref.trim()} onClick={upsertRule} type="button" variant="outline">
            {editingIndex == null ? addButtonLabel : updateButtonLabel}
          </Button>
          <Button disabled={!canManage || savePending || saveDisabled} onClick={onSave} type="button">
            {saveButtonLabel}
          </Button>
        </div>
        {saveMessage ? <p className="text-sm font-medium text-emerald-700">{saveMessage}</p> : null}
      </div>
    </div>
  );
}
