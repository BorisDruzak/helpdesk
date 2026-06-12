import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, Sparkles, UploadCloud } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  createKnowledgeImportDrafts,
  fetchKnowledgeSpaces,
  previewKnowledgeImport,
  type KnowledgeImportDraftResult,
  type KnowledgeImportPreview,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const textareaClass = `${fieldClass} min-h-64 font-mono text-xs`;

type DraftState = {
  ai_enrichment_enabled: boolean;
  body: string;
  item_type: string;
  slug: string;
  source_kind: string;
  source_name: string;
  space_code: string;
  title: string;
  visibility: string;
};

function defaultDraft(): DraftState {
  return {
    ai_enrichment_enabled: false,
    body: "# VPN Import\n\n## Steps\nReconnect VPN.",
    item_type: "article",
    slug: "",
    source_kind: "markdown",
    source_name: "vpn-import.md",
    space_code: "it-support",
    title: "",
    visibility: "support_internal",
  };
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

  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const spaces = spacesQuery.data ?? [];
  const selectedSpace = useMemo(() => spaces.find((space) => space.code === draft.space_code) ?? spaces[0] ?? null, [draft.space_code, spaces]);

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

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Import"
        title="Импорт знаний"
        description="Мастер импортирует text/markdown без AI по умолчанию, показывает preview структуры и создает review draft."
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UploadCloud className="h-5 w-5" />
              Источник
            </CardTitle>
            <CardDescription>Первый slice поддерживает text, markdown и HTML preview. PDF/DOCX/URL остаются следующими подэтапами.</CardDescription>
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
                <select className={fieldClass} value={draft.source_kind} onChange={(event) => setDraft({ ...draft, source_kind: event.target.value })}>
                  <option value="markdown">markdown</option>
                  <option value="text">text</option>
                  <option value="html">html</option>
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
            <label className="text-sm font-medium">
              Текст импорта
              <textarea className={textareaClass} value={draft.body} onChange={(event) => setDraft({ ...draft, body: event.target.value })} />
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input checked={draft.ai_enrichment_enabled} onChange={(event) => setDraft({ ...draft, ai_enrichment_enabled: event.target.checked })} type="checkbox" />
              Запросить AI enrichment после preview
            </label>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!draft.body.trim() || previewMutation.isPending} onClick={() => previewMutation.mutate()}>
                Предпросмотр
              </Button>
              <Button disabled={!preview || createMutation.isPending} onClick={() => createMutation.mutate()} variant="secondary">
                Создать черновик
              </Button>
            </div>
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
