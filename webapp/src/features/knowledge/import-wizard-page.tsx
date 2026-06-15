import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, ShieldCheck, Sparkles, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  createKnowledgeImportDrafts,
  fetchKnowledgeSegmentationProfiles,
  fetchKnowledgeSpaces,
  previewKnowledgeImport,
  type KnowledgeImportDraftResult,
  type KnowledgeImportPreview,
  type KnowledgeSpace,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const textareaClass = `${fieldClass} min-h-64 font-mono text-xs`;
const textSourceKinds = new Set(["text", "markdown", "html"]);
const fileSourceKinds = new Set(["docx", "pdf"]);
const safeImportVisibility = "support_internal";
const defaultRagPolicy = "inherit";
const longImportAutoSegmentWords = 800;

type DraftState = {
  ai_enrichment_enabled: boolean;
  auto_segment_after_import: boolean;
  body: string;
  file_content_base64?: string;
  item_type: string;
  ref: string;
  repo_url: string;
  segmentation_profile_code: string;
  slug: string;
  source_kind: string;
  source_name: string;
  space_code: string;
  title: string;
  url: string;
};

function defaultDraft(): DraftState {
  return {
    ai_enrichment_enabled: false,
    auto_segment_after_import: false,
    body: "# VPN Import\n\n## Steps\nReconnect VPN.",
    item_type: "article",
    ref: "",
    repo_url: "",
    segmentation_profile_code: "default-auto",
    slug: "",
    source_kind: "markdown",
    source_name: "vpn-import.md",
    space_code: "",
    title: "",
    url: "",
  };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Не удалось прочитать файл импорта"));
    reader.onload = () => {
      const value = String(reader.result ?? "");
      resolve(value.includes(",") ? value.split(",").pop() ?? "" : value);
    };
    reader.readAsDataURL(file);
  });
}

function aiStatusLabel(status?: string) {
  if (status === "disabled") {
    return "AI выключен";
  }
  if (status === "blocked_pending_policy") {
    return "AI требует политики";
  }
  return status ?? "нет данных";
}

function sectionLabel(space: KnowledgeSpace | null) {
  return space ? `${space.title} (${space.code})` : "раздел не выбран";
}

function previewWordCount(preview: KnowledgeImportPreview | null) {
  return preview?.word_count ?? 0;
}

function shouldAutoSegmentLongImport(preview: KnowledgeImportPreview | null) {
  return previewWordCount(preview) >= longImportAutoSegmentWords;
}

function autoSegmentationPreviewLabel(preview: KnowledgeImportPreview | null, enabledByUser: boolean) {
  if (shouldAutoSegmentLongImport(preview)) {
    return "Авторазметка: будет запущена (длинный документ)";
  }
  if (enabledByUser) {
    return "Авторазметка: будет запущена вручную";
  }
  return "Авторазметка: не будет запущена";
}

function safeImportMetadata() {
  return {
    ai_rag_policy: defaultRagPolicy,
    import_mode: "safe_draft",
  };
}

export function KnowledgeImportWizardPage() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<DraftState>(() => defaultDraft());
  const [preview, setPreview] = useState<KnowledgeImportPreview | null>(null);
  const [result, setResult] = useState<KnowledgeImportDraftResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const profilesQuery = useQuery({ queryKey: ["knowledge-segmentation-profiles"], queryFn: fetchKnowledgeSegmentationProfiles });
  const spaces = spacesQuery.data ?? [];
  const profiles = profilesQuery.data ?? [];
  const selectedSpace = useMemo(() => spaces.find((space) => space.code === draft.space_code) ?? spaces[0] ?? null, [draft.space_code, spaces]);
  const textSource = textSourceKinds.has(draft.source_kind);
  const fileSource = fileSourceKinds.has(draft.source_kind);
  const remoteSource = draft.source_kind === "url" || draft.source_kind === "git";
  const hasImportSource =
    (textSource && Boolean(draft.body.trim())) ||
    (fileSource && Boolean(draft.file_content_base64)) ||
    (draft.source_kind === "url" && Boolean(draft.url.trim())) ||
    (draft.source_kind === "git" && Boolean(draft.repo_url.trim()));
  const autoSegmentWillRun = draft.auto_segment_after_import || shouldAutoSegmentLongImport(preview);
  const canPreview = Boolean(selectedSpace) && hasImportSource;
  const canCreate = Boolean(selectedSpace && preview);

  function buildPayload(forceAutoSegmentation: boolean) {
    return {
      ...draft,
      auto_segment_after_import: forceAutoSegmentation,
      metadata: safeImportMetadata(),
      space_code: selectedSpace?.code ?? "",
      visibility: safeImportVisibility,
    };
  }

  const previewPayload = buildPayload(draft.auto_segment_after_import);
  const createPayload = buildPayload(autoSegmentWillRun);

  const previewMutation = useMutation({
    mutationFn: () => previewKnowledgeImport(previewPayload),
    onSuccess: (nextPreview) => {
      setPreview(nextPreview);
      setResult(null);
      if (!draft.title && nextPreview.detected_title) {
        setDraft((current) => ({ ...current, title: nextPreview.detected_title }));
      }
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createKnowledgeImportDrafts({ ...createPayload, title: draft.title || preview?.detected_title }),
    onSuccess: (nextResult) => {
      setResult(nextResult);
      navigate(`/app/admin/knowledge/studio?item=${encodeURIComponent(nextResult.item.item_id)}`);
    },
  });

  function updateDraft(patch: Partial<DraftState>, resetPreview = true) {
    setDraft((current) => ({ ...current, ...patch }));
    if (resetPreview) {
      setPreview(null);
      setResult(null);
    }
  }

  async function handleFileUpload(file: File | null) {
    setFileError(null);
    if (!file) {
      updateDraft({ file_content_base64: undefined });
      return;
    }
    try {
      const content = await fileToBase64(file);
      updateDraft({
        body: "",
        file_content_base64: content,
        source_name: file.name,
        title: draft.title || file.name.replace(/\.[^.]+$/, ""),
      });
    } catch (error) {
      setFileError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Import"
        title="Импорт знаний"
        description="Импорт создает безопасный внутренний черновик, наследует аудиторию и RAG-политику выбранного раздела базы знаний, а затем открывает статью в упрощенной Studio."
      />

      <div className="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
          {["1. Источник", "2. Предпросмотр", "3. Studio"].map((step, index) => (
            <span className={`rounded-md px-3 py-1 ${index === 0 && !preview ? "bg-brand-600 text-white" : index === 1 && preview && !result ? "bg-brand-600 text-white" : index === 2 && result ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700"}`} key={step}>
              {step}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canPreview || previewMutation.isPending} onClick={() => previewMutation.mutate()}>
            Предпросмотр
          </Button>
          <Button disabled={!canCreate || createMutation.isPending} onClick={() => createMutation.mutate()} variant="secondary">
            Создать черновик и открыть Studio
          </Button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UploadCloud className="h-5 w-5" />
              Источник
            </CardTitle>
            <CardDescription>Выберите раздел, источник и параметры безопасного черновика. Публикация не выполняется из импорта.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-medium">
                Раздел базы знаний
                <select
                  className={fieldClass}
                  disabled={spacesQuery.isLoading || !spaces.length}
                  value={selectedSpace?.code ?? ""}
                  onChange={(event) => updateDraft({ space_code: event.target.value })}
                >
                  {spaces.map((space) => (
                    <option key={space.code} value={space.code}>
                      {space.title} ({space.code})
                    </option>
                  ))}
                  {!spaces.length ? <option value="">Разделы не загружены</option> : null}
                </select>
              </label>
              <label className="text-sm font-medium">
                Формат
                <select
                  className={fieldClass}
                  value={draft.source_kind}
                  onChange={(event) => {
                    const nextKind = event.target.value;
                    updateDraft({
                      source_kind: nextKind,
                      body: textSourceKinds.has(nextKind) ? draft.body || "# VPN Import\n\n## Steps\nReconnect VPN." : "",
                      file_content_base64: undefined,
                    });
                    setFileError(null);
                  }}
                >
                  <option value="markdown">Markdown</option>
                  <option value="text">Текст</option>
                  <option value="html">HTML</option>
                  <option value="docx">DOCX файл</option>
                  <option value="pdf">PDF файл</option>
                  <option value="url">Внешний URL</option>
                  <option value="git">Git repository</option>
                </select>
              </label>
              <label className="text-sm font-medium">
                Источник
                <input className={fieldClass} value={draft.source_name} onChange={(event) => updateDraft({ source_name: event.target.value }, false)} />
              </label>
              <label className="text-sm font-medium">
                Название
                <input className={fieldClass} value={draft.title} onChange={(event) => updateDraft({ title: event.target.value }, false)} />
              </label>
              <label className="text-sm font-medium">
                Slug
                <input className={fieldClass} value={draft.slug} onChange={(event) => updateDraft({ slug: event.target.value }, false)} />
              </label>
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                <p className="font-semibold">Безопасный режим: внутренний черновик для поддержки</p>
                <p className="mt-1 text-xs leading-5">Импорт не создает requester-visible материал и не публикует статью автоматически.</p>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <div className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 text-brand-700" />
                <div className="space-y-1">
                  <p className="font-semibold text-slate-900">Политики черновика</p>
                  <p>Аудитория будет наследоваться от выбранного раздела.</p>
                  <p>AI/RAG будет работать только по политике выбранного раздела.</p>
                  <p className="text-xs text-slate-500">
                    {selectedSpace ? `Выбран раздел: ${sectionLabel(selectedSpace)}. RAG в разделе ${selectedSpace.allow_rag ? "включен" : "отключен"}.` : "Выберите раздел, чтобы увидеть политики импорта."}
                  </p>
                </div>
              </div>
            </div>

            {textSource ? (
              <label className="text-sm font-medium">
                Текст импорта
                <textarea className={textareaClass} value={draft.body} onChange={(event) => updateDraft({ body: event.target.value })} />
              </label>
            ) : null}
            {fileSource ? (
              <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-3">
                <label className="text-sm font-medium">
                  Файл импорта
                  <input
                    accept={draft.source_kind === "docx" ? ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" : ".pdf,application/pdf"}
                    className={fieldClass}
                    onChange={(event) => void handleFileUpload(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                </label>
                {draft.file_content_base64 ? <p className="mt-2 text-xs text-emerald-700">Файл готов к предпросмотру: {draft.source_name}</p> : null}
                {fileError ? <p className="mt-2 text-xs text-rose-700">{fileError}</p> : null}
              </div>
            ) : null}
            {draft.source_kind === "url" ? (
              <label className="text-sm font-medium">
                URL источника
                <input className={fieldClass} value={draft.url} onChange={(event) => updateDraft({ url: event.target.value })} />
              </label>
            ) : null}
            {draft.source_kind === "git" ? (
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                <label className="text-sm font-medium">
                  Git repository URL
                  <input className={fieldClass} value={draft.repo_url} onChange={(event) => updateDraft({ repo_url: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Ref
                  <input className={fieldClass} placeholder="main" value={draft.ref} onChange={(event) => updateDraft({ ref: event.target.value })} />
                </label>
              </div>
            ) : null}
            {remoteSource ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Внешний импорт по умолчанию заблокирован. Сервер выполнит загрузку только при включенной политике `KNOWLEDGE_REMOTE_IMPORT_ENABLED` и host allowlist; ответы не показывают токены, пароли и query string.
              </div>
            ) : null}
            <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input checked={draft.auto_segment_after_import} onChange={(event) => updateDraft({ auto_segment_after_import: event.target.checked }, false)} type="checkbox" />
                Запустить авторазметку после создания черновика
              </label>
              <label className="mt-3 block text-sm font-medium">
                Профиль авторазметки
                <select
                  className={fieldClass}
                  disabled={!draft.auto_segment_after_import && !shouldAutoSegmentLongImport(preview)}
                  value={draft.segmentation_profile_code}
                  onChange={(event) => updateDraft({ segmentation_profile_code: event.target.value }, false)}
                >
                  {profiles.map((profile) => (
                    <option key={profile.code} value={profile.code}>
                      {profile.title} ({profile.code})
                    </option>
                  ))}
                  {!profiles.length ? <option value="default-auto">default-auto</option> : null}
                </select>
              </label>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Документы от {longImportAutoSegmentWords} слов автоматически отправляются в авторазметку, чтобы не требовать ручной сегментации.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input checked={draft.ai_enrichment_enabled} onChange={(event) => updateDraft({ ai_enrichment_enabled: event.target.checked })} type="checkbox" />
              Запросить AI enrichment после предпросмотра
            </label>
            {spacesQuery.isError ? <p className="text-sm text-rose-700">Не удалось загрузить разделы базы знаний.</p> : null}
            {!spacesQuery.isLoading && !spaces.length ? <p className="text-sm text-rose-700">Перед импортом нужен хотя бы один активный раздел базы знаний.</p> : null}
            {previewMutation.error ? <p className="text-sm text-rose-700">{String(previewMutation.error.message)}</p> : null}
            {createMutation.error ? <p className="text-sm text-rose-700">{String(createMutation.error.message)}</p> : null}
          </CardContent>
        </Card>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Предпросмотр
              </CardTitle>
              <CardDescription>Проверьте структуру и политики до создания черновика.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {preview ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="info">{preview.source_kind}</Badge>
                    <Badge tone="neutral">{preview.body_format}</Badge>
                    <Badge tone={preview.ai_enrichment.status === "disabled" ? "neutral" : "warning"}>{aiStatusLabel(preview.ai_enrichment.status)}</Badge>
                  </div>
                  <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs font-semibold uppercase text-slate-500">Обнаруженное название</p>
                    <p className="mt-1 text-sm font-semibold text-slate-950">{preview.detected_title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {preview.section_count} секций, {preview.word_count ?? 0} слов
                    </p>
                  </div>
                  <div className="space-y-1 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">
                    <p>Раздел: {sectionLabel(selectedSpace)}</p>
                    <p>Видимость: внутренний черновик для поддержки</p>
                    <p>Аудитория: наследуется от раздела</p>
                    <p>AI/RAG: по политике раздела</p>
                    <p>{autoSegmentationPreviewLabel(preview, draft.auto_segment_after_import)}</p>
                  </div>
                  <div className="space-y-2">
                    {preview.sections.map((section) => (
                      <div className="rounded-md border border-slate-200 px-3 py-2" key={section.heading}>
                        <p className="text-sm font-semibold text-slate-900">{section.heading}</p>
                        <p className="mt-1 text-xs text-slate-500">{section.preview}</p>
                      </div>
                    ))}
                  </div>
                  {preview.remote_source ? (
                    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <p className="font-semibold text-slate-800">Remote source</p>
                      <p>host: {preview.remote_source.host ?? "n/a"}</p>
                      {preview.remote_source.path ? <p>path: {preview.remote_source.path}</p> : null}
                      {preview.remote_source.repo ? <p>repo: {preview.remote_source.repo}</p> : null}
                      {preview.remote_source.ref ? <p>ref: {preview.remote_source.ref}</p> : null}
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="text-sm text-slate-500">Предпросмотр появится после проверки источника.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                Результат
              </CardTitle>
            </CardHeader>
            <CardContent>
              {result ? (
                <div className="space-y-2">
                  <Badge tone="success">Черновик создан</Badge>
                  <p className="text-sm font-semibold text-slate-950">{result.item.title}</p>
                  <p className="break-all text-xs text-slate-500">slug: {result.item.slug}</p>
                  {result.segmentation?.enabled ? (
                    <p className="text-xs text-slate-600">
                      Разметка: {result.segmentation.status} / {result.segmentation.profile_code}
                    </p>
                  ) : null}
                  <a className="text-sm font-medium text-brand-700 hover:underline" href={`/app/admin/knowledge/studio?item=${encodeURIComponent(result.item.item_id)}`}>
                    Открыть в Studio
                  </a>
                </div>
              ) : (
                <p className="text-sm text-slate-500">После создания черновика откроется упрощенная Studio с импортированной статьей.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
