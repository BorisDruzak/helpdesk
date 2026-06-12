import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { saveKnowledgePropertyDefinition, type KnowledgeMetadataBundle, type KnowledgePropertyDefinition } from "./api";
import { fieldClass, splitLines, statusOptions, valueTypeOptions } from "./metadata-editor-common";

type PropertyDraft = {
  allowed_values: string;
  applies_to_item_types: string;
  code: string;
  description: string;
  quality_weight: string;
  required: boolean;
  status: string;
  title: string;
  value_type: string;
};

function emptyDraft(): PropertyDraft {
  return {
    allowed_values: "",
    applies_to_item_types: "article\nfaq\nrunbook",
    code: "",
    description: "",
    quality_weight: "0",
    required: false,
    status: "active",
    title: "",
    value_type: "text",
  };
}

function draftFromProperty(row: KnowledgePropertyDefinition): PropertyDraft {
  return {
    allowed_values: (row.allowed_values ?? []).join("\n"),
    applies_to_item_types: (row.applies_to_item_types ?? []).join("\n"),
    code: row.code,
    description: row.description ?? "",
    quality_weight: String(row.quality_weight ?? 0),
    required: row.required,
    status: row.status,
    title: row.title,
    value_type: row.value_type,
  };
}

export function MetadataPropertyPanel({ metadata, onChanged }: { metadata?: KnowledgeMetadataBundle; onChanged: () => void }) {
  const spaces = metadata?.spaces ?? [];
  const [spaceId, setSpaceId] = useState("");
  const [selectedPropertyId, setSelectedPropertyId] = useState("");
  const [draft, setDraft] = useState<PropertyDraft>(() => emptyDraft());
  const selectedProperty = (metadata?.property_definitions ?? []).find((row) => row.property_id === selectedPropertyId);
  const effectiveSpaceId = spaceId || spaces[0]?.space_id || "";
  const properties = useMemo(
    () => (metadata?.property_definitions ?? []).filter((row) => row.space_id === effectiveSpaceId).sort((a, b) => a.code.localeCompare(b.code)),
    [metadata, effectiveSpaceId],
  );

  useEffect(() => {
    if (!spaceId && spaces[0]?.space_id) {
      setSpaceId(spaces[0].space_id);
    }
  }, [spaceId, spaces]);

  useEffect(() => {
    if (selectedProperty) {
      setDraft(draftFromProperty(selectedProperty));
    }
  }, [selectedProperty?.property_id]);

  const saveMutation = useMutation({
    mutationFn: (statusOverride?: string) =>
      saveKnowledgePropertyDefinition({
        ...(selectedProperty ? { property_id: selectedProperty.property_id } : {}),
        space_id: effectiveSpaceId,
        code: draft.code.trim(),
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        value_type: draft.value_type,
        required: draft.required,
        allowed_values: splitLines(draft.allowed_values),
        applies_to_item_types: splitLines(draft.applies_to_item_types),
        quality_weight: Number(draft.quality_weight || 0),
        status: statusOverride ?? draft.status,
      }),
    onSuccess: () => {
      setSelectedPropertyId("");
      setDraft(emptyDraft());
      onChanged();
    },
  });

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>Определения свойств</CardTitle>
          <CardDescription>Типизированные свойства участвуют в валидации и расчёте качества статьи.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Пространство свойств
            <select className={fieldClass} value={effectiveSpaceId} onChange={(event) => setSpaceId(event.target.value)}>
              {spaces.map((space) => (
                <option key={space.space_id} value={space.space_id}>
                  {space.title}
                </option>
              ))}
            </select>
          </label>
          <div className="space-y-2">
            {properties.map((row) => (
              <button
                key={row.property_id}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${row.property_id === selectedPropertyId ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white"}`}
                onClick={() => setSelectedPropertyId(row.property_id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="font-medium">{row.title}</span>
                  <Badge>{row.status}</Badge>
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {row.code} · {row.value_type} · вес {row.quality_weight ?? 0}
                </span>
              </button>
            ))}
            {!properties.length ? <p className="text-sm text-slate-500">Свойства пока не настроены.</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selectedProperty ? "Редактировать свойство" : "Новое свойство"}</CardTitle>
          <CardDescription>Разрешённые значения указываются построчно; raw JSON для обычного сценария не нужен.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Код свойства
            <input className={fieldClass} value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Название свойства
            <input className={fieldClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Тип значения
            <select className={fieldClass} value={draft.value_type} onChange={(event) => setDraft({ ...draft, value_type: event.target.value })}>
              {valueTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input checked={draft.required} onChange={(event) => setDraft({ ...draft, required: event.target.checked })} type="checkbox" />
            Обязательное свойство
          </label>
          <label className="text-sm font-medium">
            Разрешённые значения
            <textarea className={fieldClass} value={draft.allowed_values} onChange={(event) => setDraft({ ...draft, allowed_values: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Типы статей
            <textarea className={fieldClass} value={draft.applies_to_item_types} onChange={(event) => setDraft({ ...draft, applies_to_item_types: event.target.value })} />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Вес качества
              <input className={fieldClass} min={0} type="number" value={draft.quality_weight} onChange={(event) => setDraft({ ...draft, quality_weight: event.target.value })} />
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
            Описание свойства
            <textarea className={fieldClass} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!effectiveSpaceId || !draft.code.trim() || !draft.title.trim() || saveMutation.isPending} onClick={() => saveMutation.mutate(undefined)}>
              Сохранить свойство
            </Button>
            {selectedProperty ? (
              <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate("archived")} variant="outline">
                Архивировать свойство
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
