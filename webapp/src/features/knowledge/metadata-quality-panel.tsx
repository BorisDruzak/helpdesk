import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { saveKnowledgeQualityModel, type KnowledgeMetadataBundle, type KnowledgeQualityModel } from "./api";
import { fieldClass, statusOptions } from "./metadata-editor-common";

type QualityDraft = {
  applicability: string;
  code: string;
  excellent: string;
  good: string;
  is_default: boolean;
  properties: string;
  review: string;
  space_id: string;
  status: string;
  taxonomy: string;
  title: string;
};

function emptyDraft(spaceId = ""): QualityDraft {
  return {
    applicability: "5",
    code: "",
    excellent: "90",
    good: "80",
    is_default: true,
    properties: "12",
    review: "60",
    space_id: spaceId,
    status: "active",
    taxonomy: "8",
    title: "",
  };
}

function draftFromModel(model: KnowledgeQualityModel): QualityDraft {
  return {
    applicability: String(model.weights?.applicability ?? 0),
    code: model.code,
    excellent: String(model.thresholds?.excellent ?? 90),
    good: String(model.thresholds?.good ?? 80),
    is_default: model.is_default,
    properties: String(model.weights?.properties ?? 0),
    review: String(model.thresholds?.review ?? 60),
    space_id: model.space_id ?? "",
    status: model.status,
    taxonomy: String(model.weights?.taxonomy ?? 0),
    title: model.title,
  };
}

export function MetadataQualityPanel({ metadata, onChanged }: { metadata?: KnowledgeMetadataBundle; onChanged: () => void }) {
  const spaces = metadata?.spaces ?? [];
  const [selectedModelId, setSelectedModelId] = useState("");
  const [draft, setDraft] = useState<QualityDraft>(() => emptyDraft(spaces[0]?.space_id ?? ""));
  const selectedModel = (metadata?.quality_models ?? []).find((model) => model.model_id === selectedModelId);

  useEffect(() => {
    if (!draft.space_id && spaces[0]?.space_id) {
      setDraft((current) => ({ ...current, space_id: spaces[0].space_id }));
    }
  }, [draft.space_id, spaces]);

  useEffect(() => {
    if (selectedModel) {
      setDraft(draftFromModel(selectedModel));
    }
  }, [selectedModel?.model_id]);

  const saveMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeQualityModel({
        ...(selectedModel?.model_id ? { model_id: selectedModel.model_id } : {}),
        space_id: draft.space_id || null,
        code: draft.code.trim(),
        title: draft.title.trim(),
        is_default: draft.is_default,
        status: draft.status,
        weights: {
          properties: Number(draft.properties || 0),
          taxonomy: Number(draft.taxonomy || 0),
          applicability: Number(draft.applicability || 0),
        },
        thresholds: {
          excellent: Number(draft.excellent || 0),
          good: Number(draft.good || 0),
          review: Number(draft.review || 0),
        },
      }),
    onSuccess: () => {
      setSelectedModelId("");
      setDraft(emptyDraft(spaces[0]?.space_id ?? ""));
      onChanged();
    },
  });

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>Активные модели качества</CardTitle>
          <CardDescription>Глобальные и scoped модели управляют explainable score без изменения кода.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {(metadata?.quality_models ?? []).map((model) => (
            <button
              key={model.model_id ?? `${model.space_id}-${model.code}`}
              className={`w-full rounded-md border px-3 py-2 text-left text-sm ${model.model_id === selectedModelId ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white"}`}
              onClick={() => setSelectedModelId(model.model_id ?? "")}
              type="button"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-medium">{model.title}</span>
                <Badge>{model.is_default ? "По умолчанию" : model.status}</Badge>
              </span>
              <span className="mt-1 block text-xs text-slate-500">
                {model.code} · свойства {model.weights?.properties ?? 0} · таксономия {model.weights?.taxonomy ?? 0}
              </span>
            </button>
          ))}
          {!(metadata?.quality_models ?? []).length ? <p className="text-sm text-slate-500">Модели качества пока не настроены.</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selectedModel ? "Редактировать модель" : "Новая модель"}</CardTitle>
          <CardDescription>Порог и вес задаются числами; backend сохраняет их как governed JSON-модель.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-sm font-medium">
            Пространство модели
            <select className={fieldClass} value={draft.space_id} onChange={(event) => setDraft({ ...draft, space_id: event.target.value })}>
              <option value="">Глобальная модель</option>
              {spaces.map((space) => (
                <option key={space.space_id} value={space.space_id}>
                  {space.title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Код модели
            <input className={fieldClass} value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} />
          </label>
          <label className="text-sm font-medium">
            Название модели
            <input className={fieldClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm font-medium">
              Вес свойств
              <input className={fieldClass} min={0} type="number" value={draft.properties} onChange={(event) => setDraft({ ...draft, properties: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Вес таксономии
              <input className={fieldClass} min={0} type="number" value={draft.taxonomy} onChange={(event) => setDraft({ ...draft, taxonomy: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Вес применимости
              <input className={fieldClass} min={0} type="number" value={draft.applicability} onChange={(event) => setDraft({ ...draft, applicability: event.target.value })} />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm font-medium">
              Порог отлично
              <input className={fieldClass} min={0} type="number" value={draft.excellent} onChange={(event) => setDraft({ ...draft, excellent: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Порог хорошо
              <input className={fieldClass} min={0} type="number" value={draft.good} onChange={(event) => setDraft({ ...draft, good: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Порог проверки
              <input className={fieldClass} min={0} type="number" value={draft.review} onChange={(event) => setDraft({ ...draft, review: event.target.value })} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input checked={draft.is_default} onChange={(event) => setDraft({ ...draft, is_default: event.target.checked })} type="checkbox" />
            Активная модель по умолчанию
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
          <Button disabled={!draft.code.trim() || !draft.title.trim() || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            Сохранить модель качества
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
