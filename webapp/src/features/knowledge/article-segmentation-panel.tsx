import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, SplitSquareHorizontal, Trash2 } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import {
  archiveKnowledgeSegment,
  autoSegmentKnowledgeItem,
  createKnowledgeSegment,
  fetchKnowledgeSegments,
  fetchKnowledgeSegmentationProfiles,
  type KnowledgeItem,
  type KnowledgeItemVersion,
  type KnowledgeSegment,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

const visibilityOptions = [
  { label: "Портал заявителя", value: "requester" },
  { label: "Безопасно для агента и заявителя", value: "agent_requester_safe" },
  { label: "Внутреннее для поддержки", value: "support_internal" },
  { label: "Только администраторы", value: "admin_internal" },
];

const segmentStatusLabels: Record<string, string> = {
  active: "Активный",
  archived: "Архив",
  draft: "Черновик",
  rejected: "Отклонён",
  stale: "Устарел",
};

const segmentTypeLabels: Record<string, string> = {
  ai_proposed: "AI-предложение",
  auto: "Авто",
  manual: "Ручной",
};

const segmentSourceLabels: Record<string, string> = {
  ai_markup: "AI-разметка",
  editor_selection: "Выделение редактора",
  heading_split: "По заголовкам",
  length_split: "По длине",
  manual: "Ручной ввод",
  paragraph_split: "По абзацам",
};

function tone(status: string) {
  if (status === "active") {
    return "success" as const;
  }
  if (["draft", "stale"].includes(status)) {
    return "warning" as const;
  }
  if (["archived", "rejected"].includes(status)) {
    return "danger" as const;
  }
  return "neutral" as const;
}

function segmentLabel(labels: Record<string, string>, value: string | null | undefined, fallback: string) {
  if (!value) {
    return fallback;
  }
  return labels[value] ?? value;
}

function keywordsFromInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 50);
}

function firstMeaningfulLine(value: string): string {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^#+\s*/, ""))
    .find(Boolean) ?? "Сегмент знаний";
}

type SegmentDraft = {
  title: string;
  summary: string;
  text: string;
  start_offset: number | null;
  end_offset: number | null;
  keywords: string;
  boost: number;
  visibility: string;
  embedding_enabled: boolean;
  full_text_enabled: boolean;
};

type ArticleSegmentationPanelProps = {
  canManage: boolean;
  editorSelection?: {
    from: number;
    text: string;
    to: number;
  };
  embedded?: boolean;
  item: KnowledgeItem | null;
  sourceBody?: string;
  version: KnowledgeItemVersion | null;
};

export function ArticleSegmentationPanel({ canManage, editorSelection, embedded = false, item, sourceBody, version }: ArticleSegmentationPanelProps) {
  const queryClient = useQueryClient();
  const sourceRef = useRef<HTMLTextAreaElement | null>(null);
  const [message, setMessage] = useState("");
  const [profileCode, setProfileCode] = useState("default-auto");
  const [draft, setDraft] = useState<SegmentDraft>({
    title: "",
    summary: "",
    text: "",
    start_offset: null,
    end_offset: null,
    keywords: "",
    boost: 1,
    visibility: item?.visibility ?? "requester",
    embedding_enabled: true,
    full_text_enabled: true,
  });

  useEffect(() => {
    setDraft((current) => ({ ...current, visibility: item?.visibility ?? "requester" }));
  }, [item?.visibility]);

  const itemId = item?.item_id ?? "";
  const versionId = version?.version_id ?? "";
  const versionBody = sourceBody ?? version?.body ?? "";
  const segmentsQuery = useQuery({
    queryKey: ["knowledge-segments", itemId],
    queryFn: () => fetchKnowledgeSegments(itemId),
    enabled: Boolean(itemId),
  });
  const profilesQuery = useQuery({
    queryKey: ["knowledge-segmentation-profiles"],
    queryFn: fetchKnowledgeSegmentationProfiles,
    enabled: canManage,
  });

  const activeSegments = useMemo(
    () => (segmentsQuery.data ?? []).filter((segment) => segment.version_id === versionId && segment.status !== "archived"),
    [segmentsQuery.data, versionId],
  );

  const createMutation = useMutation({
    mutationFn: () =>
      createKnowledgeSegment(itemId, {
        version_id: versionId,
        segment_type: "manual",
        title: draft.title || firstMeaningfulLine(draft.text),
        summary: draft.summary || null,
        text: draft.text,
        start_offset: draft.start_offset,
        end_offset: draft.end_offset,
        keywords: keywordsFromInput(draft.keywords),
        boost: draft.boost,
        visibility: draft.visibility,
        embedding_enabled: draft.embedding_enabled,
        full_text_enabled: draft.full_text_enabled,
      }),
    onSuccess: (result) => {
      setMessage(result.display_message ?? "Сегмент знаний сохранён");
      setDraft((current) => ({ ...current, title: "", summary: "", text: "", start_offset: null, end_offset: null, keywords: "" }));
      queryClient.invalidateQueries({ queryKey: ["knowledge-segments", itemId] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Не удалось создать сегмент"),
  });

  const autoMutation = useMutation({
    mutationFn: () => autoSegmentKnowledgeItem(itemId, { version_id: versionId, profile_code: profileCode }),
    onSuccess: (result) => {
      setMessage(result.display_message ?? "Авторазметка выполнена без AI");
      queryClient.invalidateQueries({ queryKey: ["knowledge-segments", itemId] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Не удалось выполнить авторазметку"),
  });

  const archiveMutation = useMutation({
    mutationFn: archiveKnowledgeSegment,
    onSuccess: (result) => {
      setMessage(result.display_message ?? "Сегмент знаний архивирован");
      queryClient.invalidateQueries({ queryKey: ["knowledge-segments", itemId] });
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "Не удалось архивировать сегмент"),
  });

  function takeSelection() {
    const source = sourceRef.current;
    if (!source) {
      return;
    }
    const start = source.selectionStart;
    const end = source.selectionEnd;
    const selectedText = source.value.slice(start, end).trim();
    if (!selectedText) {
      setMessage("Выделите текст версии перед созданием сегмента");
      return;
    }
    const offsetShift = source.value.slice(start, end).indexOf(selectedText);
    const normalizedStart = offsetShift >= 0 ? start + offsetShift : start;
    setDraft((current) => ({
      ...current,
      title: current.title || firstMeaningfulLine(selectedText),
      text: selectedText,
      start_offset: normalizedStart,
      end_offset: normalizedStart + selectedText.length,
    }));
    setMessage(`Выделено ${selectedText.length} символов`);
  }

  function takeEditorSelection() {
    const selectedText = editorSelection?.text.trim() ?? "";
    if (!selectedText) {
      setMessage("Выделите текст в редакторе статьи перед созданием сегмента");
      return;
    }
    const normalizedStart = versionBody.indexOf(selectedText);
    setDraft((current) => ({
      ...current,
      title: current.title || firstMeaningfulLine(selectedText),
      text: selectedText,
      start_offset: normalizedStart >= 0 ? normalizedStart : null,
      end_offset: normalizedStart >= 0 ? normalizedStart + selectedText.length : null,
    }));
    setMessage(`Выделение редактора перенесено в сегмент: ${selectedText.length} символов`);
  }

  if (!item || !version) {
    if (embedded) {
      return (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
            <Blocks className="h-5 w-5" />
            Разметка статьи
          </p>
          <p className="mt-1 text-sm text-slate-500">Выберите статью и версию для разметки.</p>
        </div>
      );
    }
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Blocks className="h-5 w-5" />
            Разметка статьи
          </CardTitle>
          <CardDescription>Выберите статью и версию для разметки.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const content = (
    <>
      {embedded ? (
        <div className="mb-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
            <Blocks className="h-5 w-5" />
            Разметка статьи
          </p>
          <p className="mt-1 text-sm text-slate-500">Ручные и автоматические сегменты встроены в единый редактор.</p>
        </div>
      ) : (
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Blocks className="h-5 w-5" />
            Разметка статьи
          </CardTitle>
          <CardDescription>Ручные и автоматические сегменты поиска без AI и будущих эмбеддингов.</CardDescription>
        </CardHeader>
      )}
      <div className={`space-y-4 ${embedded ? "" : "px-6 pb-6"}`}>
        <div className="rounded-md border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-900">
          {editorSelection?.text ? `В редакторе выделено ${editorSelection.text.length} символов.` : "Выделите текст в редакторе статьи, затем создайте сегмент из выделения."}
        </div>
        <Button variant="outline" size="sm" onClick={takeEditorSelection} disabled={!canManage || !editorSelection?.text}>
          Создать сегмент из выделения редактора
        </Button>
        <label className="text-sm font-medium">
          Текст версии для fallback-выделения
          <textarea
            ref={sourceRef}
            aria-label="Текст версии для выделения"
            className={`${fieldClass} min-h-40 font-mono text-xs`}
            readOnly
            value={versionBody}
          />
        </label>
        <Button variant="outline" size="sm" onClick={takeSelection} disabled={!canManage || !versionBody}>
          Взять выделенный текст
        </Button>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="space-y-3">
            <label className="text-sm font-medium">
              Заголовок сегмента
              <input className={fieldClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Текст сегмента
              <textarea className={`${fieldClass} min-h-28`} value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} />
            </label>
            <label className="text-sm font-medium">
              Ключевые слова
              <input className={fieldClass} value={draft.keywords} onChange={(event) => setDraft({ ...draft, keywords: event.target.value })} />
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
                Вес поиска
                <input
                  className={fieldClass}
                  type="number"
                  min={0}
                  max={10}
                  step={0.5}
                  value={draft.boost}
                  onChange={(event) => setDraft({ ...draft, boost: Number(event.target.value) })}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.full_text_enabled}
                  onChange={(event) => setDraft({ ...draft, full_text_enabled: event.target.checked })}
                />
                Полнотекстовый поиск
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.embedding_enabled}
                  onChange={(event) => setDraft({ ...draft, embedding_enabled: event.target.checked })}
                />
                Эмбеддинги
              </label>
            </div>
            <Button onClick={() => createMutation.mutate()} disabled={!canManage || !versionId || !draft.text || createMutation.isPending}>
              Создать сегмент
            </Button>
          </div>

          <div className="space-y-3">
            <div className="rounded-md border border-slate-200 p-3">
              <div className="flex flex-wrap items-end gap-3">
                <label className="min-w-0 flex-1 text-sm font-medium">
                  Профиль авторазметки
                  <select className={fieldClass} value={profileCode} onChange={(event) => setProfileCode(event.target.value)}>
                    {(profilesQuery.data ?? []).map((profile) => (
                      <option key={profile.code} value={profile.code}>
                        {profile.title}
                      </option>
                    ))}
                    {!profilesQuery.data?.length ? <option value="default-auto">Авторазметка по заголовкам</option> : null}
                  </select>
                </label>
                <Button
                  variant="outline"
                  onClick={() => autoMutation.mutate()}
                  disabled={!canManage || !versionId || autoMutation.isPending}
                  leadingIcon={<SplitSquareHorizontal className="h-4 w-4" />}
                >
                  Запустить авторазметку
                </Button>
              </div>
            </div>

            {message ? <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</p> : null}

            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase text-slate-500">Сегменты версии</div>
              {activeSegments.map((segment: KnowledgeSegment) => (
                <div key={segment.segment_id} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900">{segment.title}</p>
                      <p className="mt-1 line-clamp-3 text-xs text-slate-600">{segment.text}</p>
                    </div>
                    <Badge tone={tone(segment.status)}>{segmentLabel(segmentStatusLabels, segment.status, "Без статуса")}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge tone="neutral">{segmentLabel(segmentTypeLabels, segment.segment_type, "Сегмент")}</Badge>
                    <Badge tone="info">{segmentLabel(segmentSourceLabels, segment.source, "Ручной ввод")}</Badge>
                    <Badge tone="brand">вес {segment.boost ?? 1}</Badge>
                    {(segment.keywords ?? []).map((keyword) => (
                      <Badge key={keyword} tone="neutral">
                        {keyword}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-3 flex justify-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => archiveMutation.mutate(segment.segment_id)}
                      disabled={!canManage || archiveMutation.isPending}
                      leadingIcon={<Trash2 className="h-4 w-4" />}
                    >
                      Архивировать
                    </Button>
                  </div>
                </div>
              ))}
              {!segmentsQuery.isLoading && !activeSegments.length ? <p className="text-sm text-slate-500">Для выбранной версии сегменты ещё не созданы.</p> : null}
            </div>
          </div>
        </div>
      </div>
    </>
  );

  if (embedded) {
    return <div className="rounded-lg border border-slate-200 bg-white p-4">{content}</div>;
  }

  return (
    <Card>
      {content}
    </Card>
  );
}
