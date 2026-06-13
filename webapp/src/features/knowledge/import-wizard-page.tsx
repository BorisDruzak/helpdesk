import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, Sparkles, UploadCloud } from "lucide-react";

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
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const textareaClass = `${fieldClass} min-h-64 font-mono text-xs`;
const textSourceKinds = new Set(["text", "markdown", "html"]);
const fileSourceKinds = new Set(["docx", "pdf"]);

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
  visibility: string;
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
    space_code: "it-support",
    title: "",
    url: "",
    visibility: "support_internal",
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

export function KnowledgeImportWizardPage() {
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
  const canPreview =
    (textSource && draft.body.trim()) ||
    (fileSource && draft.file_content_base64) ||
    (draft.source_kind === "url" && draft.url.trim()) ||
    (draft.source_kind === "git" && draft.repo_url.trim());

  const payload = {
    ...draft,
    space_code: selectedSpace?.code ?? draft.space_code,
  };

  const previewMutation = useMutation({
    mutationFn: () => previewKnowledgeImport(payload),
    onSuccess: (nextPreview) => {
      setPreview(nextPreview);
      setResult(null);
      if (!draft.title && nextPreview.detected_title) {
        setDraft((current) => ({ ...current, title: nextPreview.detected_title }));
      }
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createKnowledgeImportDrafts({ ...payload, title: draft.title || preview?.detected_title }),
    onSuccess: (nextResult) => setResult(nextResult),
  });

  async function handleFileUpload(file: File | null) {
    setFileError(null);
    if (!file) {
      setDraft((current) => ({ ...current, file_content_base64: undefined }));
      return;
    }
    try {
      const content = await fileToBase64(file);
      setDraft((current) => ({
        ...current,
        body: "",
        file_content_base64: content,
        source_name: file.name,
        title: current.title || file.name.replace(/\.[^.]+$/, ""),
      }));
      setPreview(null);
      setResult(null);
    } catch (error) {
      setFileError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Import"
        title="Импорт знаний"
        description="Мастер импортирует text/markdown без AI по умолчанию, показывает preview структуры и создает review draft."
      />

      <div className="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
          {["1. Источник", "2. Preview", "3. Черновик"].map((step, index) => (
            <span className={`rounded-md px-3 py-1 ${index === 0 && !preview ? "bg-brand-600 text-white" : index === 1 && preview && !result ? "bg-brand-600 text-white" : index === 2 && result ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700"}`} key={step}>
              {step}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canPreview || previewMutation.isPending} onClick={() => previewMutation.mutate()}>
            Предпросмотр
          </Button>
          <Button disabled={!preview || createMutation.isPending} onClick={() => createMutation.mutate()} variant="secondary">
            Создать черновик
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
            <CardDescription>Источник может быть текстом, upload-файлом или внешней ссылкой, если серверная политика это разрешает.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-medium">
                Пространство
                <select className={fieldClass} value={selectedSpace?.code ?? draft.space_code} onChange={(event) => setDraft({ ...draft, space_code: event.target.value })}>
                  {spaces.map((space) => (
                    <option key={space.code} value={space.code}>
                      {space.title} ({space.code})
                    </option>
                  ))}
                  {!spaces.length ? <option value={draft.space_code}>{draft.space_code}</option> : null}
                </select>
              </label>
              <label className="text-sm font-medium">
                Формат
                <select
                  className={fieldClass}
                  value={draft.source_kind}
                  onChange={(event) => {
                    const nextKind = event.target.value;
                    setDraft({
                      ...draft,
                      source_kind: nextKind,
                      body: textSourceKinds.has(nextKind) ? draft.body || "# VPN Import\n\n## Steps\nReconnect VPN." : "",
                      file_content_base64: undefined,
                    });
                    setPreview(null);
                    setResult(null);
                    setFileError(null);
                  }}
                >
                  <option value="markdown">markdown</option>
                  <option value="text">text</option>
                  <option value="html">html</option>
                  <option value="docx">docx upload</option>
                  <option value="pdf">pdf upload</option>
                  <option value="url">external URL</option>
                  <option value="git">Git repository</option>
                </select>
              </label>
              <label className="text-sm font-medium">
                Источник
                <input className={fieldClass} value={draft.source_name} onChange={(event) => setDraft({ ...draft, source_name: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Название
                <input className={fieldClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Slug
                <input className={fieldClass} value={draft.slug} onChange={(event) => setDraft({ ...draft, slug: event.target.value })} />
              </label>
              <label className="text-sm font-medium">
                Видимость
                <select className={fieldClass} value={draft.visibility} onChange={(event) => setDraft({ ...draft, visibility: event.target.value })}>
                  <option value="requester">requester</option>
                  <option value="agent_requester_safe">agent_requester_safe</option>
                  <option value="support_internal">support_internal</option>
                  <option value="admin_internal">admin_internal</option>
                </select>
              </label>
            </div>
            {textSource ? (
              <label className="text-sm font-medium">
                Текст импорта
                <textarea className={textareaClass} value={draft.body} onChange={(event) => setDraft({ ...draft, body: event.target.value })} />
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
                {draft.file_content_base64 ? <p className="mt-2 text-xs text-emerald-700">Файл готов к preview: {draft.source_name}</p> : null}
                {fileError ? <p className="mt-2 text-xs text-rose-700">{fileError}</p> : null}
              </div>
            ) : null}
            {draft.source_kind === "url" ? (
              <label className="text-sm font-medium">
                URL источника
                <input className={fieldClass} value={draft.url} onChange={(event) => setDraft({ ...draft, url: event.target.value })} />
              </label>
            ) : null}
            {draft.source_kind === "git" ? (
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                <label className="text-sm font-medium">
                  Git repository URL
                  <input className={fieldClass} value={draft.repo_url} onChange={(event) => setDraft({ ...draft, repo_url: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Ref
                  <input className={fieldClass} placeholder="main" value={draft.ref} onChange={(event) => setDraft({ ...draft, ref: event.target.value })} />
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
                <input checked={draft.auto_segment_after_import} onChange={(event) => setDraft({ ...draft, auto_segment_after_import: event.target.checked })} type="checkbox" />
                Запустить авторазметку после создания draft
              </label>
              <label className="mt-3 block text-sm font-medium">
                Профиль разметки
                <select
                  className={fieldClass}
                  disabled={!draft.auto_segment_after_import}
                  value={draft.segmentation_profile_code}
                  onChange={(event) => setDraft({ ...draft, segmentation_profile_code: event.target.value })}
                >
                  {profiles.map((profile) => (
                    <option key={profile.code} value={profile.code}>
                      {profile.title} ({profile.code})
                    </option>
                  ))}
                  {!profiles.length ? <option value="default-auto">default-auto</option> : null}
                </select>
              </label>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input checked={draft.ai_enrichment_enabled} onChange={(event) => setDraft({ ...draft, ai_enrichment_enabled: event.target.checked })} type="checkbox" />
              Запросить AI enrichment после preview
            </label>
            {previewMutation.error ? <p className="text-sm text-rose-700">{String(previewMutation.error.message)}</p> : null}
            {createMutation.error ? <p className="text-sm text-rose-700">{String(createMutation.error.message)}</p> : null}
          </CardContent>
        </Card>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Preview
              </CardTitle>
              <CardDescription>Структура, которую сервер извлек перед созданием draft.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {preview ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="info">{preview.source_kind}</Badge>
                    <Badge tone="neutral">{preview.body_format}</Badge>
                    <Badge tone={preview.ai_enrichment.status === "disabled" ? "neutral" : "warning"}>{aiStatusLabel(preview.ai_enrichment.status)}</Badge>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-950">{preview.detected_title}</p>
                    <p className="text-xs text-slate-500">
                      {preview.section_count} секций, {preview.word_count ?? 0} слов
                    </p>
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
                <p className="text-sm text-slate-500">Preview появится после проверки источника.</p>
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
                    Открыть в студии
                  </a>
                </div>
              ) : (
                <p className="text-sm text-slate-500">После создания здесь появится ссылка на draft.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
