import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BookOpenCheck, CheckCircle2, FileText, GitCompare, MessageSquare, PlusCircle, RotateCcw, Send, ShieldCheck, Sparkles, Undo2 } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { ArticleSegmentationPanel } from "./article-segmentation-panel";
import {
  createKnowledgeItem,
  createKnowledgeVersion,
  fetchKnowledgeEditorHistory,
  fetchKnowledgeItemVersions,
  fetchKnowledgeItems,
  fetchKnowledgeSpaces,
  fetchKnowledgeTemplates,
  publishKnowledgeItem,
  submitKnowledgeReviewAction,
  type KnowledgeItem,
  type KnowledgeItemVersion,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const textareaClass = `${fieldClass} min-h-72 font-mono text-xs leading-6`;

const itemTypeOptions = [
  { label: "Статья", value: "article" },
  { label: "FAQ", value: "faq" },
  { label: "Пошаговая инструкция", value: "runbook" },
  { label: "Известная ошибка", value: "known_error" },
  { label: "Обходное решение", value: "workaround" },
];

const visibilityOptions = [
  { label: "Портал заявителя", value: "requester" },
  { label: "Безопасно для агента и заявителя", value: "agent_requester_safe" },
  { label: "Внутреннее для поддержки", value: "support_internal" },
  { label: "Только администраторы", value: "admin_internal" },
];

const statusLabels: Record<string, string> = {
  archived: "Архив",
  draft: "Черновик",
  in_review: "На ревью",
  published: "Опубликована",
  retired: "Выведена",
};

type EditorDraft = {
  body: string;
  body_format: string;
  change_summary: string;
  item_type: string;
  owner_actor_id: string;
  reviewer_actor_id: string;
  slug: string;
  space_code: string;
  summary: string;
  tags: string;
  title: string;
  visibility: string;
};

type NewItemDraft = {
  item_type: string;
  owner_actor_id: string;
  reviewer_actor_id: string;
  slug: string;
  space_code: string;
  summary: string;
  tags: string;
  title: string;
  visibility: string;
};

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function spaceCodeFor(item: KnowledgeItem | null, spaces: Array<{ code: string; space_id: string }>) {
  if (!item) {
    return spaces[0]?.code ?? "";
  }
  return spaces.find((space) => space.space_id === item.space_id)?.code ?? spaces[0]?.code ?? "";
}

function draftFrom(item: KnowledgeItem | null, version: KnowledgeItemVersion | null, spaces: Array<{ code: string; space_id: string }>): EditorDraft {
  return {
    body: version?.body ?? "",
    body_format: version?.body_format ?? "markdown",
    change_summary: "",
    item_type: item?.item_type ?? "article",
    owner_actor_id: item?.owner_actor_id ?? "",
    reviewer_actor_id: item?.reviewer_actor_id ?? "",
    slug: item?.slug ?? "",
    space_code: spaceCodeFor(item, spaces),
    summary: version?.summary ?? item?.summary ?? "",
    tags: (item?.tags ?? []).join(", "),
    title: version?.title ?? item?.title ?? "",
    visibility: item?.visibility ?? "requester",
  };
}

function normalizeList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function statusLabel(value: string | null | undefined) {
  if (!value) {
    return "Без статуса";
  }
  return statusLabels[value] ?? value;
}

function visibilityLabel(value: string | null | undefined) {
  return visibilityOptions.find((option) => option.value === value)?.label ?? value ?? "Без видимости";
}

function markdownPreview(markdown: string) {
  return markdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block, index) => {
      if (block.startsWith("# ")) {
        return (
          <h2 key={index} className="text-xl font-semibold text-slate-950">
            {block.slice(2).trim()}
          </h2>
        );
      }
      if (block.startsWith("## ")) {
        return (
          <h3 key={index} className="text-base font-semibold text-slate-900">
            {block.slice(3).trim()}
          </h3>
        );
      }
      if (block.startsWith("- ")) {
        return (
          <ul key={index} className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
            {block.split("\n").map((line) => (
              <li key={line}>{line.replace(/^- /, "")}</li>
            ))}
          </ul>
        );
      }
      return (
        <p key={index} className="text-sm leading-7 text-slate-700">
          {block}
        </p>
      );
    });
}

function diffSummary(originalBody: string, draftBody: string) {
  const originalLines = originalBody.split("\n").filter((line) => line.trim());
  const draftLines = draftBody.split("\n").filter((line) => line.trim());
  const added = draftLines.filter((line) => !originalLines.includes(line));
  const removed = originalLines.filter((line) => !draftLines.includes(line));
  return { added, removed };
}

export function KnowledgeAuthoringStudioPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [draft, setDraft] = useState<EditorDraft>(() => draftFrom(null, null, []));
  const [newDraft, setNewDraft] = useState<NewItemDraft>({
    item_type: "article",
    owner_actor_id: "",
    reviewer_actor_id: "",
    slug: "",
    space_code: "",
    summary: "",
    tags: "",
    title: "",
    visibility: "requester",
  });
  const [checklist, setChecklist] = useState({
    body: false,
    reviewer: false,
    summary: false,
    visibility: false,
  });
  const [publishNote, setPublishNote] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const templatesQuery = useQuery({ queryKey: ["knowledge-templates"], queryFn: fetchKnowledgeTemplates });

  const spaces = spacesQuery.data ?? [];
  const items = itemsQuery.data ?? [];
  const spacesKey = spaces.map((space) => `${space.space_id}:${space.code}`).join("|");
  const filteredItems = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) => [item.title, item.slug, item.status, item.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle)));
  }, [items, search]);
  const defaultItem = useMemo(() => {
    const activeItems = filteredItems.filter((item) => item.status !== "archived");
    return activeItems.find((item) => item.current_version_id) ?? activeItems[0] ?? filteredItems.find((item) => item.current_version_id) ?? filteredItems[0] ?? null;
  }, [filteredItems]);
  const selectedItem = items.find((item) => item.item_id === selectedItemId) ?? defaultItem;

  const versionsQuery = useQuery({
    queryKey: ["knowledge-item-versions", selectedItem?.item_id],
    queryFn: () => fetchKnowledgeItemVersions(selectedItem?.item_id ?? ""),
    enabled: Boolean(selectedItem?.item_id),
  });
  const versions = versionsQuery.data ?? [];
  const latestVersion = versions[0] ?? null;
  const selectedVersion = versions.find((version) => version.version_id === selectedVersionId) ?? latestVersion;
  const editorHistoryQuery = useQuery({
    queryKey: ["knowledge-editor-history", selectedItem?.item_id],
    queryFn: () => fetchKnowledgeEditorHistory(selectedItem?.item_id ?? ""),
    enabled: Boolean(selectedItem?.item_id),
  });
  const editorHistory = editorHistoryQuery.data;
  const latestDiffCache = editorHistory?.diff_cache?.[0] ?? null;

  useEffect(() => {
    if (!selectedItem?.item_id) {
      return;
    }
    const defaultVersion = versions.find((version) => version.version_id === selectedItem.current_version_id) ?? latestVersion;
    setSelectedItemId(selectedItem.item_id);
    setSelectedVersionId(defaultVersion?.version_id ?? "");
    setDraft(draftFrom(selectedItem, defaultVersion, spaces));
    setChecklist({ body: false, reviewer: false, summary: false, visibility: false });
    setPublishNote("");
    setReviewNote("");
  }, [latestVersion?.version_id, selectedItem?.current_version_id, selectedItem?.item_id, spacesKey]);

  useEffect(() => {
    if (!newDraft.space_code && spaces[0]?.code) {
      setNewDraft((current) => ({ ...current, space_code: spaces[0]?.code ?? "" }));
    }
  }, [newDraft.space_code, spacesKey]);

  const createItemMutation = useMutation({
    mutationFn: () =>
      createKnowledgeItem({
        item_type: newDraft.item_type,
        owner_actor_id: emptyToNull(newDraft.owner_actor_id),
        reviewer_actor_id: emptyToNull(newDraft.reviewer_actor_id),
        slug: newDraft.slug.trim(),
        space_code: newDraft.space_code || spaces[0]?.code || "",
        summary: newDraft.summary.trim(),
        tags: normalizeList(newDraft.tags),
        title: newDraft.title.trim(),
        visibility: newDraft.visibility,
      }),
    onSuccess: (result) => {
      setSelectedItemId(result.item.item_id);
      setNewDraft((current) => ({ ...current, slug: "", summary: "", tags: "", title: "" }));
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", result.item.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
    },
  });

  const createVersionMutation = useMutation({
    mutationFn: () =>
      createKnowledgeVersion(selectedItem?.item_id ?? "", {
        body: draft.body,
        body_format: draft.body_format,
        change_summary: draft.change_summary,
        summary: draft.summary,
        title: draft.title,
      }),
    onSuccess: (result) => {
      setSelectedVersionId(result.version.version_id);
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", selectedItem?.item_id] });
    },
  });

  const publishMutation = useMutation({
    mutationFn: () =>
      publishKnowledgeItem(selectedItem?.item_id ?? "", selectedVersionId || selectedVersion?.version_id || "", {
        review_note: publishNote.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", selectedItem?.item_id] });
    },
  });

  const reviewActionMutation = useMutation({
    mutationFn: (action: string) =>
      submitKnowledgeReviewAction(selectedItem?.item_id ?? "", {
        action,
        note: reviewNote.trim() || null,
      }),
    onSuccess: (_result, action) => {
      if (action === "archive" || action === "retire") {
        setSelectedItemId("");
      }
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
  });

  const checklistComplete = Object.values(checklist).every(Boolean);
  const currentDiff = diffSummary(selectedVersion?.body ?? "", draft.body);

  function updateDraft<K extends keyof EditorDraft>(key: K, value: EditorDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function insertTemplate(sections: string[]) {
    const block = sections.map((section) => `## ${section}\n\n`).join("\n");
    setDraft((current) => ({ ...current, body: `${current.body.trim()}\n\n${block}`.trim() }));
  }

  function insertMarkdownBlock(block: string) {
    setDraft((current) => ({ ...current, body: `${current.body.trim()}\n\n${block}`.trim() }));
  }

  function selectVersion(versionId: string) {
    const nextVersion = versions.find((version) => version.version_id === versionId) ?? null;
    setSelectedVersionId(versionId);
    setDraft(draftFrom(selectedItem, nextVersion ?? latestVersion, spaces));
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Редактор базы знаний"
        title="Студия статей"
        description="Редактор статей, версий, разметки и публикации для продуктовой базы знаний."
      />

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Черновики и статьи
              </CardTitle>
              <CardDescription>Быстрый выбор материала для редактирования.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Поиск
                <input className={fieldClass} value={search} onChange={(event) => setSearch(event.target.value)} />
              </label>
              <div className="max-h-[560px] space-y-2 overflow-auto pr-1">
                {filteredItems.map((item) => (
                  <button
                    key={item.item_id}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                      item.item_id === selectedItem?.item_id ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                    onClick={() => setSelectedItemId(item.item_id)}
                    type="button"
                  >
                    <span className="block font-semibold text-slate-950">{item.title}</span>
                    <span className="block text-xs text-slate-500">{item.slug}</span>
                    <span className="mt-2 flex flex-wrap gap-2">
                      <Badge>{statusLabel(item.status)}</Badge>
                      <Badge>{visibilityLabel(item.visibility)}</Badge>
                    </span>
                  </button>
                ))}
                {!filteredItems.length ? <p className="text-sm text-slate-500">Нет статей для выбранного фильтра.</p> : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PlusCircle className="h-5 w-5" />
                Новый черновик
              </CardTitle>
              <CardDescription>Быстрое создание статьи без перехода в старую административную форму.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Новый заголовок
                <input className={fieldClass} value={newDraft.title} onChange={(event) => setNewDraft({ ...newDraft, title: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Новый slug
                <input className={fieldClass} value={newDraft.slug} onChange={(event) => setNewDraft({ ...newDraft, slug: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Краткое описание нового черновика
                <textarea className={`${fieldClass} min-h-24`} value={newDraft.summary} onChange={(event) => setNewDraft({ ...newDraft, summary: event.target.value })} />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm font-medium">
                  Пространство нового черновика
                  <select className={fieldClass} value={newDraft.space_code} onChange={(event) => setNewDraft({ ...newDraft, space_code: event.target.value })}>
                    {spaces.map((space) => (
                      <option key={space.space_id} value={space.code}>
                        {space.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Тип нового черновика
                  <select className={fieldClass} value={newDraft.item_type} onChange={(event) => setNewDraft({ ...newDraft, item_type: event.target.value })}>
                    {itemTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="text-sm font-medium">
                Видимость нового черновика
                <select className={fieldClass} value={newDraft.visibility} onChange={(event) => setNewDraft({ ...newDraft, visibility: event.target.value })}>
                  {visibilityOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm font-medium">
                  Владелец нового черновика
                  <input className={fieldClass} value={newDraft.owner_actor_id} onChange={(event) => setNewDraft({ ...newDraft, owner_actor_id: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Ревьюер нового черновика
                  <input className={fieldClass} value={newDraft.reviewer_actor_id} onChange={(event) => setNewDraft({ ...newDraft, reviewer_actor_id: event.target.value })} />
                </label>
              </div>
              <label className="text-sm font-medium">
                Теги нового черновика
                <input className={fieldClass} value={newDraft.tags} onChange={(event) => setNewDraft({ ...newDraft, tags: event.target.value })} />
              </label>
              <Button disabled={!newDraft.title.trim() || !newDraft.slug.trim() || createItemMutation.isPending} onClick={() => createItemMutation.mutate()}>
                Создать новый черновик
              </Button>
            </CardContent>
          </Card>
        </aside>

        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <Card>
              <CardHeader>
                <CardTitle>Метаданные статьи</CardTitle>
                <CardDescription>Студия использует существующие API статей и версий без новых таблиц.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <label className="text-sm font-medium">
                  Заголовок
                  <input className={fieldClass} value={draft.title} onChange={(event) => updateDraft("title", event.target.value)} />
                </label>
                <label className="text-sm font-medium">
                  Slug
                  <input className={fieldClass} value={draft.slug} onChange={(event) => updateDraft("slug", event.target.value)} />
                </label>
                <label className="text-sm font-medium">
                  Пространство
                  <select className={fieldClass} value={draft.space_code} onChange={(event) => updateDraft("space_code", event.target.value)}>
                    {spaces.map((space) => (
                      <option key={space.space_id} value={space.code}>
                        {space.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Тип
                  <select className={fieldClass} value={draft.item_type} onChange={(event) => updateDraft("item_type", event.target.value)}>
                    {itemTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Видимость
                  <select className={fieldClass} value={draft.visibility} onChange={(event) => updateDraft("visibility", event.target.value)}>
                    {visibilityOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Теги
                  <input className={fieldClass} value={draft.tags} onChange={(event) => updateDraft("tags", event.target.value)} />
                </label>
                <label className="text-sm font-medium">
                  Владелец
                  <input className={fieldClass} value={draft.owner_actor_id} onChange={(event) => updateDraft("owner_actor_id", event.target.value)} />
                </label>
                <label className="text-sm font-medium">
                  Ревьюер
                  <input className={fieldClass} value={draft.reviewer_actor_id} onChange={(event) => updateDraft("reviewer_actor_id", event.target.value)} />
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpenCheck className="h-5 w-5" />
                  Проверка публикации
                </CardTitle>
                <CardDescription>Локальный checklist перед вызовом существующего publish API.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="text-sm font-medium">
                  Версия для сравнения
                  <select className={fieldClass} value={selectedVersionId} onChange={(event) => selectVersion(event.target.value)}>
                    {versions.map((version) => (
                      <option key={version.version_id} value={version.version_id}>
                        v{version.version_number}: {version.title}
                      </option>
                    ))}
                  </select>
                </label>
                <fieldset aria-label="Проверка публикации" className="grid gap-2">
                  {[
                    ["body", "Markdown заполнен"],
                    ["summary", "Есть краткое описание"],
                    ["visibility", "Выбрана безопасная видимость для портала"],
                    ["reviewer", "Назначен ревьюер"],
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm">
                      <input
                        checked={checklist[key as keyof typeof checklist]}
                        onChange={(event) => setChecklist((current) => ({ ...current, [key]: event.target.checked }))}
                        type="checkbox"
                      />
                      {label}
                    </label>
                  ))}
                </fieldset>
                <label className="text-sm font-medium">
                  Комментарий к публикации
                  <input className={fieldClass} value={publishNote} onChange={(event) => setPublishNote(event.target.value)} />
                </label>
                <Button disabled={!selectedItem || !checklistComplete || publishMutation.isPending} onClick={() => publishMutation.mutate()}>
                  Опубликовать версию
                </Button>
                <Button
                  disabled={!selectedItem || !selectedVersionId || publishMutation.isPending}
                  onClick={() => publishMutation.mutate()}
                  variant="outline"
                >
                  <RotateCcw className="h-4 w-4" />
                  Откатить к выбранной версии
                </Button>
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
                  Теги для портала заявителя: {normalizeList(draft.tags).slice(0, 5).join(", ") || "нет"}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Ревью и жизненный цикл
              </CardTitle>
              <CardDescription>Статусные действия используют существующий API ревью и пишут событие истории статьи.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="text-sm font-medium">
                Комментарий ревью
                <input className={fieldClass} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!selectedItem || reviewActionMutation.isPending} onClick={() => reviewActionMutation.mutate("submit_review")} variant="outline">
                  <Send className="h-4 w-4" />
                  Отправить на ревью
                </Button>
                <Button disabled={!selectedItem || reviewActionMutation.isPending} onClick={() => reviewActionMutation.mutate("comment")} variant="outline">
                  <MessageSquare className="h-4 w-4" />
                  Добавить комментарий
                </Button>
                <Button disabled={!selectedItem || reviewActionMutation.isPending} onClick={() => reviewActionMutation.mutate("approve")} variant="outline">
                  <CheckCircle2 className="h-4 w-4" />
                  Одобрить
                </Button>
                <Button disabled={!selectedItem || reviewActionMutation.isPending} onClick={() => reviewActionMutation.mutate("request_changes")} variant="outline">
                  <Undo2 className="h-4 w-4" />
                  Запросить правки
                </Button>
                <Button disabled={!selectedItem || reviewActionMutation.isPending} onClick={() => reviewActionMutation.mutate("archive")} variant="outline">
                  <Archive className="h-4 w-4" />
                  Архивировать / заменить
                </Button>
              </div>
              <p className="text-xs leading-5 text-slate-500">
                Замена статьи оформляется как архивирование старого материала с комментарием ревью и созданием нового черновика через студию.
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.7fr)]">
            <Card>
              <CardHeader>
                <CardTitle>Редактор</CardTitle>
                <CardDescription>Markdown, шаблоны и новая версия без AI-зависимости.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {(templatesQuery.data ?? []).map((template) => (
                    <Button key={template.type} variant="outline" onClick={() => insertTemplate(template.sections)}>
                      Вставить шаблон: {template.title}
                    </Button>
                  ))}
                  <Button variant="outline" onClick={() => insertMarkdownBlock("> [!NOTE]\n> Важное уточнение для читателя.")}>
                    <PlusCircle className="h-4 w-4" />
                    Вставить callout
                  </Button>
                  <Button variant="outline" onClick={() => insertMarkdownBlock("| Шаг | Действие |\n| --- | --- |\n| 1 | Описать проверку |")}>
                    <PlusCircle className="h-4 w-4" />
                    Вставить таблицу
                  </Button>
                  <Button variant="outline" onClick={() => insertMarkdownBlock("```text\nКоманда или лог\n```")}>
                    <PlusCircle className="h-4 w-4" />
                    Вставить код
                  </Button>
                  <Button variant="outline" onClick={() => insertMarkdownBlock("- [ ] Проверить результат\n- [ ] Обновить статью после проверки")}>
                    <PlusCircle className="h-4 w-4" />
                    Вставить checklist
                  </Button>
                </div>
                <label className="text-sm font-medium">
                  Markdown
                  <textarea className={textareaClass} value={draft.body} onChange={(event) => updateDraft("body", event.target.value)} />
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="text-sm font-medium">
                    Краткое описание версии
                    <input className={fieldClass} value={draft.summary} onChange={(event) => updateDraft("summary", event.target.value)} />
                  </label>
                  <label className="text-sm font-medium">
                    Описание изменения
                    <input className={fieldClass} value={draft.change_summary} onChange={(event) => updateDraft("change_summary", event.target.value)} />
                  </label>
                </div>
                <Button disabled={!selectedItem || createVersionMutation.isPending} onClick={() => createVersionMutation.mutate()}>
                  Создать версию
                </Button>
              </CardContent>
            </Card>

            <div className="space-y-5">
              <Card>
                <CardHeader>
                  <CardTitle>Предпросмотр</CardTitle>
                  <CardDescription>Как статья будет читаться без перехода в портал.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">{markdownPreview(draft.body)}</CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitCompare className="h-5 w-5" />
                    Diff версии
                  </CardTitle>
                  <CardDescription>Лёгкая проверка отличий draft от выбранной версии.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="font-medium text-emerald-700">Добавлено: {currentDiff.added.length}</p>
                  <p className="font-medium text-red-700">Удалено: {currentDiff.removed.length}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>История редактора</CardTitle>
                  <CardDescription>События студии и сохраненный кэш различий для выбранной статьи.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {latestDiffCache ? (
                    <p className="font-medium text-slate-700">
                      Кэш различий: +{latestDiffCache.added_lines} / -{latestDiffCache.removed_lines}
                    </p>
                  ) : (
                    <p className="text-slate-500">Кэш различий еще не создан.</p>
                  )}
                  <div className="space-y-2">
                    {(editorHistory?.events ?? []).slice(0, 6).map((event) => (
                      <div key={event.event_id} className="rounded-md border border-slate-200 px-3 py-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge>{event.event_type}</Badge>
                          {event.actor_id ? <span className="text-xs text-slate-500">{event.actor_id}</span> : null}
                        </div>
                        {event.summary ? <p className="mt-1 text-slate-700">{event.summary}</p> : null}
                      </div>
                    ))}
                    {!editorHistoryQuery.isLoading && !(editorHistory?.events ?? []).length ? (
                      <p className="text-slate-500">История появится после создания версии, ревью или публикации.</p>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5" />
                    AI-инструменты отключены
                  </CardTitle>
                  <CardDescription>Переписывание, резюме и генерация FAQ появятся только после отдельного AI-среза с политиками доступа.</CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>

          <ArticleSegmentationPanel item={selectedItem} version={selectedVersion ?? null} canManage={Boolean(selectedItem)} />
        </div>
      </div>
    </section>
  );
}
