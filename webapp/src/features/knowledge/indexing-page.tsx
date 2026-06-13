import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, RefreshCw } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { fetchKnowledgeIndexingStatus, fetchKnowledgeIndexJobs, fetchKnowledgeItems, reindexKnowledgeItem } from "./api";

const inputClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

function countOf(values: Record<string, number> | undefined, key: string) {
  return Number(values?.[key] ?? 0);
}

function statusTone(status: string) {
  if (status === "indexed" || status === "completed") {
    return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  }
  if (status === "failed") {
    return "bg-rose-50 text-rose-700 ring-rose-200";
  }
  if (status === "disabled" || status === "canceled") {
    return "bg-slate-100 text-slate-700 ring-slate-200";
  }
  return "bg-amber-50 text-amber-700 ring-amber-200";
}

export function KnowledgeIndexingPage() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({ queryKey: ["knowledge-indexing-status"], queryFn: fetchKnowledgeIndexingStatus });
  const jobsQuery = useQuery({ queryKey: ["knowledge-indexing-jobs"], queryFn: fetchKnowledgeIndexJobs });
  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const [itemId, setItemId] = useState("");
  const [itemSearch, setItemSearch] = useState("");
  const [versionId, setVersionId] = useState("");
  const [message, setMessage] = useState("");

  const reindexMutation = useMutation({
    mutationFn: () => reindexKnowledgeItem({ item_id: itemId.trim(), version_id: versionId.trim() || undefined }),
    onSuccess: (result) => {
      setMessage(result.display_message ?? "Индексация embeddings выполнена");
      queryClient.invalidateQueries({ queryKey: ["knowledge-indexing-status"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-indexing-jobs"] });
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : "Индексация embeddings завершилась ошибкой");
    },
  });

  const indexing = statusQuery.data;
  const embeddings = indexing?.embeddings ?? {};
  const jobs = jobsQuery.data ?? [];
  const vectorDisabled = indexing ? !indexing.vector_enabled : false;
  const filteredItems = (itemsQuery.data ?? [])
    .filter((item) => {
      const needle = itemSearch.trim().toLowerCase();
      if (!needle) {
        return true;
      }
      return [item.title, item.slug, item.status, item.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle));
    })
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <PageHeading
        eyebrow="Knowledge vNext"
        title="Индексация знаний"
        description="Embeddings и vector index остаются опциональными: при выключенном AI поиск продолжает работать через keyword/full-text."
      />

      <div className="grid gap-3 md:grid-cols-4">
        {[
          ["indexed", "Индексировано", countOf(embeddings, "indexed")],
          ["pending", "Ожидают", countOf(embeddings, "pending")],
          ["failed", "Ошибки", countOf(embeddings, "failed")],
          ["disabled", "Отключено", countOf(embeddings, "disabled")],
        ].map(([key, label, value]) => (
          <Card key={key}>
            <CardHeader className="pb-2">
              <CardDescription>{label}</CardDescription>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">{value}</CardContent>
          </Card>
        ))}
      </div>

      {vectorDisabled ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-amber-900">Vector поиск выключен</CardTitle>
            <CardDescription className="text-amber-800">
              Новые задания пометят embeddings как disabled, пока в настройках поиска не включён vector режим и AI policy не разрешает embeddings.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DatabaseZap className="h-5 w-5" />
              Reindex статьи
            </CardTitle>
            <CardDescription>Выберите статью из реестра. Raw item id доступен только в Advanced.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="block text-sm font-medium text-slate-700">
              Поиск статьи
              <input className={inputClass} value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} placeholder="Название, slug, статус" />
            </label>
            <div className="max-h-56 space-y-2 overflow-auto pr-1">
              {filteredItems.map((item) => (
                <button
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${itemId === item.item_id ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-brand-200"}`}
                  key={item.item_id}
                  onClick={() => {
                    setItemId(item.item_id);
                    setItemSearch(item.title);
                  }}
                  type="button"
                >
                  <span className="block font-semibold text-slate-950">{item.title}</span>
                  <span className="block text-xs text-slate-500">{item.slug}</span>
                </button>
              ))}
              {!itemsQuery.isLoading && !filteredItems.length ? <p className="text-sm text-slate-500">Статьи не найдены.</p> : null}
            </div>
            <AdvancedDisclosure description="Используйте только для диагностики, миграций или когда статья ещё не попала в picker." title="Advanced: raw ids">
              <label className="block text-sm font-medium text-slate-700">
                Raw item id or slug
                <input className={inputClass} value={itemId} onChange={(event) => setItemId(event.target.value)} placeholder="knowledge item id или slug" />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Raw version id
                <input className={inputClass} value={versionId} onChange={(event) => setVersionId(event.target.value)} placeholder="опционально" />
              </label>
            </AdvancedDisclosure>
            <Button type="button" onClick={() => reindexMutation.mutate()} disabled={!itemId.trim() || reindexMutation.isPending}>
              <RefreshCw className="h-4 w-4" />
              Запустить reindex
            </Button>
            {message ? <p className="text-sm text-slate-600">{message}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Состояние очереди</CardTitle>
            <CardDescription>
              Модель: {indexing?.embedding_model || "не настроена"}. Raw vectors не показываются в web response.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Задание</th>
                  <th className="py-2 pr-3">Scope</th>
                  <th className="py-2 pr-3">Статус</th>
                  <th className="py-2 pr-3">Индексировано</th>
                  <th className="py-2 pr-3">Ошибки</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} className="border-t border-slate-100">
                    <td className="py-2 pr-3 font-mono text-xs">{job.job_id.slice(0, 8)}</td>
                    <td className="py-2 pr-3">{job.scope_type}</td>
                    <td className="py-2 pr-3">
                      <Badge className={statusTone(job.status)}>{job.status}</Badge>
                    </td>
                    <td className="py-2 pr-3">{job.stats_json?.indexed_embeddings ?? 0}</td>
                    <td className="py-2 pr-3">{job.error_redacted || job.stats_json?.failed_embeddings || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!jobs.length ? <p className="py-6 text-sm text-slate-500">Заданий индексации пока нет.</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
