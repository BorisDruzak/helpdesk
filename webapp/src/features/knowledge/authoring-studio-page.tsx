import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { PageHeading } from "../../components/ui/page-heading";
import { ArticleExplorer } from "./authoring/ArticleExplorer";
import { ArticleInspector } from "./authoring/ArticleInspector";
import { NewDraftDrawer } from "./authoring/NewDraftDrawer";
import { UnifiedArticleEditor } from "./authoring/UnifiedArticleEditor";
import {
  diffSummary,
  draftFrom,
  emptyToNull,
  normalizeList,
  validationChecksFor,
  type EditorDraft,
  type EditorSelectionSnapshot,
  type NewItemDraft,
} from "./authoring/knowledge-studio-model";
import {
  createKnowledgeItem,
  createKnowledgeVersion,
  fetchKnowledgeEditorHistory,
  fetchKnowledgeItemVersions,
  fetchKnowledgeItems,
  fetchKnowledgeSegments,
  fetchKnowledgeSpaces,
  fetchKnowledgeTemplates,
  publishKnowledgeItem,
  updateKnowledgeItemSettings,
} from "./api";

const domainTabs = [
  { active: false, href: "/app/admin/knowledge/sections", label: "Разделы" },
  { active: true, href: "/app/admin/knowledge/studio", label: "Содержание" },
  { active: false, href: "/app/admin/knowledge/import", label: "Импорт" },
  { active: false, href: "/app/admin/knowledge/graph", label: "Граф" },
  { active: false, href: "/app/admin/knowledge/search-settings", label: "Поиск" },
  { active: false, href: "/app/admin/knowledge/ai", label: "AI" },
  { active: false, href: "/app/admin/knowledge/indexing", label: "Индексация" },
];

function emptyNewDraft(): NewItemDraft {
  return {
    item_type: "article",
    owner_actor_id: "",
    reviewer_actor_id: "",
    slug: "",
    space_code: "",
    summary: "",
    tags: "",
    title: "",
    visibility: "requester",
  };
}

export function KnowledgeAuthoringStudioPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const requestedItemParam = searchParams.get("item") ?? "";
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [draft, setDraft] = useState<EditorDraft>(() => draftFrom(null, null, []));
  const [newDraft, setNewDraft] = useState<NewItemDraft>(() => emptyNewDraft());
  const [newDraftOpen, setNewDraftOpen] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [editorSelection, setEditorSelection] = useState<EditorSelectionSnapshot>({ from: 0, text: "", to: 0 });

  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const templatesQuery = useQuery({ queryKey: ["knowledge-templates"], queryFn: fetchKnowledgeTemplates });

  const spaces = spacesQuery.data ?? [];
  const items = itemsQuery.data ?? [];
  const spacesKey = spaces.map((space) => `${space.space_id}:${space.code}`).join("|");

  const filteredItems = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return items.filter((item) => {
      const statusMatches = statusFilter === "all" || item.status === statusFilter;
      const searchMatches =
        !needle || [item.title, item.slug, item.status, item.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle));
      return statusMatches && searchMatches;
    });
  }, [items, search, statusFilter]);

  const defaultItem = useMemo(() => {
    const activeItems = filteredItems.filter((item) => item.status !== "archived");
    return activeItems.find((item) => item.current_version_id) ?? activeItems[0] ?? filteredItems.find((item) => item.current_version_id) ?? filteredItems[0] ?? null;
  }, [filteredItems]);
  const requestedItem = useMemo(
    () => items.find((item) => item.item_id === requestedItemParam || item.slug === requestedItemParam) ?? null,
    [items, requestedItemParam],
  );
  const selectedItem = items.find((item) => item.item_id === selectedItemId) ?? requestedItem ?? defaultItem;

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

  const segmentsQuery = useQuery({
    queryKey: ["knowledge-segments", selectedItem?.item_id ?? ""],
    queryFn: () => fetchKnowledgeSegments(selectedItem?.item_id ?? ""),
    enabled: Boolean(selectedItem?.item_id),
  });

  const activeSegmentsCount = useMemo(
    () => (segmentsQuery.data ?? []).filter((segment) => segment.version_id === selectedVersion?.version_id && segment.status !== "archived").length,
    [segmentsQuery.data, selectedVersion?.version_id],
  );
  const validationChecks = useMemo(() => validationChecksFor(draft, activeSegmentsCount), [activeSegmentsCount, draft]);
  const checklistComplete = validationChecks.every((check) => check.ok);
  const currentDiff = diffSummary(selectedVersion?.body ?? "", draft.body);

  useEffect(() => {
    if (requestedItem?.item_id) {
      setSelectedItemId(requestedItem.item_id);
    }
  }, [requestedItem?.item_id]);

  useEffect(() => {
    if (!selectedItem?.item_id) {
      setDraft(draftFrom(null, null, spaces));
      return;
    }
    const defaultVersion = versions.find((version) => version.version_id === selectedItem.current_version_id) ?? latestVersion;
    setSelectedItemId(selectedItem.item_id);
    setSelectedVersionId(defaultVersion?.version_id ?? "");
    setDraft(draftFrom(selectedItem, defaultVersion, spaces));
    setSaveMessage("");
    setEditorSelection({ from: 0, text: "", to: 0 });
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
      setNewDraftOpen(false);
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", result.item.item_id] });
    },
  });

  const saveArticleMutation = useMutation({
    mutationFn: async () => {
      if (!selectedItem?.item_id) {
        throw new Error("Выберите статью перед сохранением");
      }
      await updateKnowledgeItemSettings(selectedItem.item_id, {
        item_type: draft.item_type,
        metadata: { ...(selectedItem.metadata ?? {}), ai_rag_policy: draft.ai_rag_policy },
        space_code: draft.space_code,
        summary: draft.summary,
        tags: normalizeList(draft.tags),
        title: draft.title,
        visibility: draft.visibility,
      });
      const versionResult = await createKnowledgeVersion(selectedItem.item_id, {
        body: draft.body,
        body_format: draft.body_format,
        change_summary: draft.change_summary.trim() || "Сохранено из упрощённой Studio",
        summary: draft.summary,
        title: draft.title,
      });
      const publishResult = await publishKnowledgeItem(selectedItem.item_id, versionResult.version.version_id);
      return { item: publishResult.item, version: versionResult.version };
    },
    onSuccess: (result) => {
      setSelectedVersionId(result.version.version_id);
      setSaveMessage(`Статья сохранена и опубликована. Текущая версия: v${result.version.version_number}.`);
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-segments", selectedItem?.item_id ?? ""] });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: () =>
      publishKnowledgeItem(selectedItem?.item_id ?? "", selectedVersionId || selectedVersion?.version_id || ""),
    onSuccess: () => {
      setSaveMessage("");
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-editor-history", selectedItem?.item_id] });
    },
  });

  function updateDraft(patch: Partial<EditorDraft>) {
    setSaveMessage("");
    setDraft((current) => ({ ...current, ...patch }));
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
    setEditorSelection({ from: 0, text: "", to: 0 });
  }

  return (
    <section className="space-y-4 overflow-x-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeading
          eyebrow="Редактор базы знаний"
          title="Студия знаний"
          description="Напишите статью, выберите раздел, аудиторию и места показа, затем сохраните её одним действием."
        />
        <nav className="flex flex-wrap gap-2" aria-label="Разделы базы знаний">
          {domainTabs.map((tab) => (
            <a
              className={`rounded-pill px-4 py-2 text-sm font-semibold transition-colors ${
                tab.active ? "bg-brand-50 text-brand-800" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              }`}
              href={tab.href}
              key={tab.href}
            >
              {tab.label}
            </a>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Badge tone="brand">Студия</Badge>
        <span>Первый экран: список статей, редактор и одно основное сохранение.</span>
      </div>

      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_340px] 2xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <ArticleExplorer
          isLoading={itemsQuery.isLoading}
          items={filteredItems}
          onOpenNewDraft={() => setNewDraftOpen(true)}
          onSearchChange={setSearch}
          onSelectItem={setSelectedItemId}
          onStatusFilterChange={setStatusFilter}
          search={search}
          selectedItem={selectedItem ?? null}
          statusFilter={statusFilter}
        />

        <div className="min-w-0">
          <UnifiedArticleEditor
            activeSegmentsCount={activeSegmentsCount}
            currentDiff={currentDiff}
            draft={draft}
            editorHistory={editorHistory}
            editorSelection={editorSelection}
            latestDiffCache={latestDiffCache}
            onDraftChange={updateDraft}
            onInsertBlock={insertMarkdownBlock}
            onInsertTemplate={insertTemplate}
            onSelectionChange={setEditorSelection}
            selectedItem={selectedItem ?? null}
            selectedVersion={selectedVersion ?? null}
            spaces={spaces}
            templates={templatesQuery.data ?? []}
            validationChecks={validationChecks}
          />
        </div>

        <ArticleInspector
          checklistComplete={checklistComplete}
          currentDiff={currentDiff}
          draftVisibility={draft.visibility}
          editorHistory={editorHistory}
          isPublishing={saveArticleMutation.isPending || rollbackMutation.isPending}
          latestDiffCache={latestDiffCache}
          onPublish={() => saveArticleMutation.mutate()}
          onRollback={() => rollbackMutation.mutate()}
          onSelectVersion={selectVersion}
          saveMessage={saveMessage}
          selectedItem={selectedItem ?? null}
          selectedVersion={selectedVersion ?? null}
          selectedVersionId={selectedVersionId}
          validationChecks={validationChecks}
          versions={versions}
        />
      </div>

      <p className="text-sm text-slate-500">
        Важно: версии, публикация и поисковые фрагменты создаются автоматически при сохранении; advanced-инструменты не мешают обычному сценарию.
      </p>

      <NewDraftDrawer
        draft={newDraft}
        isCreating={createItemMutation.isPending}
        isOpen={newDraftOpen}
        onChange={setNewDraft}
        onClose={() => setNewDraftOpen(false)}
        onCreate={() => createItemMutation.mutate()}
        spaces={spaces}
      />
    </section>
  );
}
