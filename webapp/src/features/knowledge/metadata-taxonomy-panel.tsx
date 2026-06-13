import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { saveKnowledgeTaxonomyTerm, type KnowledgeMetadataBundle, type KnowledgeTaxonomyTerm } from "./api";
import { fieldClass, linkedItemCount, statusLabel, statusOptions, termTypeLabel, termTypeOptions, termsForSpace, visibilityOptions } from "./metadata-editor-common";

type TaxonomyDraft = {
  code: string;
  description: string;
  parent_term_id: string;
  sort_order: string;
  status: string;
  term_type: string;
  title: string;
  visibility: string;
};

function emptyDraft(): TaxonomyDraft {
  return {
    code: "",
    description: "",
    parent_term_id: "",
    sort_order: "0",
    status: "active",
    term_type: "category",
    title: "",
    visibility: "requester",
  };
}

function draftFromTerm(term: KnowledgeTaxonomyTerm): TaxonomyDraft {
  return {
    code: term.code,
    description: term.description ?? "",
    parent_term_id: term.parent_term_id ?? "",
    sort_order: String(term.sort_order ?? 0),
    status: term.status,
    term_type: term.term_type,
    title: term.title,
    visibility: term.visibility,
  };
}

export function MetadataTaxonomyPanel({ metadata, onChanged }: { metadata?: KnowledgeMetadataBundle; onChanged: () => void }) {
  const spaces = metadata?.spaces ?? [];
  const [spaceId, setSpaceId] = useState("");
  const [selectedTermId, setSelectedTermId] = useState("");
  const [draft, setDraft] = useState<TaxonomyDraft>(() => emptyDraft());
  const selectedTerm = (metadata?.taxonomy_terms ?? []).find((term) => term.term_id === selectedTermId);
  const effectiveSpaceId = spaceId || spaces[0]?.space_id || "";
  const terms = useMemo(() => termsForSpace(metadata, effectiveSpaceId), [metadata, effectiveSpaceId]);

  useEffect(() => {
    if (!spaceId && spaces[0]?.space_id) {
      setSpaceId(spaces[0].space_id);
    }
  }, [spaceId, spaces]);

  useEffect(() => {
    if (selectedTerm) {
      setDraft(draftFromTerm(selectedTerm));
    }
  }, [selectedTerm?.term_id]);

  const saveMutation = useMutation({
    mutationFn: (statusOverride?: string) =>
      saveKnowledgeTaxonomyTerm({
        ...(selectedTerm ? { term_id: selectedTerm.term_id } : {}),
        space_id: effectiveSpaceId,
        term_type: draft.term_type,
        code: draft.code.trim(),
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        parent_term_id: draft.parent_term_id || null,
        visibility: draft.visibility,
        status: statusOverride ?? draft.status,
        sort_order: Number(draft.sort_order || 0),
      }),
    onSuccess: () => {
      setSelectedTermId("");
      setDraft(emptyDraft());
      onChanged();
    },
  });

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]" data-testid="knowledge-metadata-taxonomy">
      <Card>
        <CardHeader>
          <CardTitle>Категории и термины</CardTitle>
          <CardDescription>Дерево терминов строится из API и остаётся редактируемым справочником.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Пространство таксономии
            <select className={fieldClass} value={effectiveSpaceId} onChange={(event) => setSpaceId(event.target.value)}>
              {spaces.map((space) => (
                <option key={space.space_id} value={space.space_id}>
                  {space.title}
                </option>
              ))}
            </select>
          </label>
          <div className="space-y-2">
            {terms.map((term) => (
              <button
                key={term.term_id}
                aria-label={`Термин ${term.title}`}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${term.term_id === selectedTermId ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white"}`}
                onClick={() => setSelectedTermId(term.term_id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className={term.parent_term_id ? "pl-5" : ""}>{term.title}</span>
                  <Badge>{statusLabel(term.status)}</Badge>
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {termTypeLabel(term.term_type)} · {term.code} · Связанные статьи: {linkedItemCount(metadata, term.term_id)}
                </span>
              </button>
            ))}
            {!terms.length ? <p className="text-sm text-slate-500">Терминов пока нет.</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selectedTerm ? "Редактировать термин" : "Новый термин"}</CardTitle>
          <CardDescription>Support сможет сохранить только разрешённую ему видимость; backend повторно проверит ACL.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Тип термина
            <select className={fieldClass} value={draft.term_type} onChange={(event) => setDraft({ ...draft, term_type: event.target.value })}>
              {termTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Код термина
            <input className={fieldClass} value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Название термина
            <input className={fieldClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Родительский термин
            <select className={fieldClass} value={draft.parent_term_id} onChange={(event) => setDraft({ ...draft, parent_term_id: event.target.value })}>
              <option value="">Без родителя</option>
              {terms
                .filter((term) => term.term_id !== selectedTermId)
                .map((term) => (
                  <option key={term.term_id} value={term.term_id}>
                    {term.title}
                  </option>
                ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Описание термина
            <textarea className={fieldClass} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Видимость
              <select className={fieldClass} value={draft.visibility} onChange={(event) => setDraft({ ...draft, visibility: event.target.value })}>
                {visibilityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Статус
              <select className={fieldClass} value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="text-sm font-medium">
            Порядок сортировки
            <input className={fieldClass} type="number" value={draft.sort_order} onChange={(event) => setDraft({ ...draft, sort_order: event.target.value })} />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!effectiveSpaceId || !draft.code.trim() || !draft.title.trim() || saveMutation.isPending} onClick={() => saveMutation.mutate(undefined)}>
              Сохранить термин
            </Button>
            {selectedTerm ? (
              <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate("archived")} variant="outline">
                Архивировать выбранный термин
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
