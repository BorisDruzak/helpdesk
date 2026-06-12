import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpen, Bot, ClipboardCheck, FileText, Link2, Search, ShieldCheck, TriangleAlert } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  fetchKnowledgeItems,
  fetchKnowledgeItemVersions,
  linkKnowledgeArticleToTicket,
  previewKnowledgeAsk,
  recordKnowledgeSupportFeedback,
  type KnowledgeAskResult,
  type KnowledgeItem,
} from "./api";

const requesterSafeVisibilities = new Set(["public", "requester", "agent_requester_safe"]);
const supportVisibilities = new Set(["public", "requester", "agent_requester_safe", "support_internal"]);
const supportTypes = ["all", "article", "runbook", "known_error", "workaround"] as const;

function typeLabel(type: string) {
  const labels: Record<string, string> = {
    all: "Все",
    article: "Articles",
    runbook: "Runbooks",
    known_error: "Known errors",
    workaround: "Workarounds",
  };
  return labels[type] ?? type;
}

function visibilityTone(visibility: string) {
  if (requesterSafeVisibilities.has(visibility)) {
    return "success" as const;
  }
  if (visibility === "support_internal") {
    return "warning" as const;
  }
  return "neutral" as const;
}

function itemTypeTone(type: string) {
  if (type === "known_error") {
    return "danger" as const;
  }
  if (type === "runbook" || type === "workaround") {
    return "info" as const;
  }
  return "neutral" as const;
}

function buildSafeAnswer(item: KnowledgeItem, body?: string | null) {
  return [item.title, item.summary, body].filter(Boolean).join("\n\n").trim();
}

function scorePartEntries(scoreParts?: Record<string, number>) {
  return Object.entries(scoreParts ?? {}).map(([key, value]) => `${key}: ${value}`);
}

function citationValue(value: unknown) {
  return value == null || value === "" ? "нет" : String(value);
}

export function KnowledgeSupportWorkspacePage() {
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [typeFilter, setTypeFilter] = useState<(typeof supportTypes)[number]>("all");
  const [visibilityFilter, setVisibilityFilter] = useState<"all" | "requester_safe" | "support_internal">("all");
  const [copyMessage, setCopyMessage] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [askDebugQuery, setAskDebugQuery] = useState(searchParams.get("query") ?? "");
  const ticketId = searchParams.get("ticket_id") ?? "";
  const ticketQuerySuffix = ticketId ? `?ticket_id=${encodeURIComponent(ticketId)}` : "";

  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const items = useMemo(() => (itemsQuery.data ?? []).filter((item) => supportVisibilities.has(item.visibility)), [itemsQuery.data]);
  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesType = typeFilter === "all" || item.item_type === typeFilter;
      const matchesVisibility =
        visibilityFilter === "all" ||
        (visibilityFilter === "requester_safe" && requesterSafeVisibilities.has(item.visibility)) ||
        (visibilityFilter === "support_internal" && item.visibility === "support_internal");
      const matchesQuery =
        !needle ||
        [item.title, item.slug, item.summary, item.item_type, item.visibility].some((value) => String(value ?? "").toLowerCase().includes(needle));
      return matchesType && matchesVisibility && matchesQuery;
    });
  }, [items, query, typeFilter, visibilityFilter]);

  const selectedItem =
    items.find((item) => item.item_id === params.itemId || item.slug === params.itemId) ??
    filteredItems[0] ??
    items[0] ??
    null;
  const selectedItemId = selectedItem?.item_id ?? "";
  const versionsQuery = useQuery({
    queryKey: ["knowledge-item-versions", selectedItemId],
    queryFn: () => fetchKnowledgeItemVersions(selectedItemId),
    enabled: Boolean(selectedItemId),
  });
  const selectedVersion =
    versionsQuery.data?.find((version) => version.version_id === selectedItem?.current_version_id) ??
    versionsQuery.data?.[0] ??
    selectedItem?.current_version ??
    null;

  const requesterSafeCount = items.filter((item) => requesterSafeVisibilities.has(item.visibility)).length;
  const supportInternalCount = items.filter((item) => item.visibility === "support_internal").length;
  const runbookCount = items.filter((item) => item.item_type === "runbook").length;
  const knownErrorCount = items.filter((item) => item.item_type === "known_error").length;
  const askDebugMutation = useMutation<KnowledgeAskResult>({
    mutationFn: () =>
      previewKnowledgeAsk({
        query: askDebugQuery.trim(),
        surface: "support_ask_debug",
        limit: 5,
      }),
  });
  const linkMutation = useMutation({
    mutationFn: () => {
      if (!ticketId || !selectedItem) {
        throw new Error("ticket context is required");
      }
      return linkKnowledgeArticleToTicket(ticketId, {
        article_ref: selectedItem.item_id,
        title: selectedItem.title,
        source: "knowledge_support_workspace",
      });
    },
    onSuccess: () => setActionMessage("Статья связана с тикетом."),
    onError: () => setActionMessage("Не удалось связать статью с тикетом."),
  });
  const supportUsedMutation = useMutation({
    mutationFn: () => {
      if (!selectedItem) {
        throw new Error("article is required");
      }
      return recordKnowledgeSupportFeedback({
        item_id: selectedItem.item_id,
        version_id: selectedVersion?.version_id,
        event_type: "support_used",
        ticket_id: ticketId || undefined,
        surface: "support_workspace",
        metadata: { source: "support_workspace" },
      });
    },
    onSuccess: () => setActionMessage("Использование статьи записано."),
    onError: () => setActionMessage("Не удалось записать использование статьи."),
  });
  const weakArticleMutation = useMutation({
    mutationFn: () => {
      if (!selectedItem) {
        throw new Error("article is required");
      }
      return recordKnowledgeSupportFeedback({
        item_id: selectedItem.item_id,
        version_id: selectedVersion?.version_id,
        event_type: "not_helpful",
        result: "weak_article_reported",
        ticket_id: ticketId || undefined,
        surface: "support_workspace",
        metadata: { source: "support_workspace" },
      });
    },
    onSuccess: () => setActionMessage("Слабая статья отмечена для улучшения."),
    onError: () => setActionMessage("Не удалось отметить слабую статью."),
  });

  async function copySafeAnswer() {
    if (!selectedItem || !requesterSafeVisibilities.has(selectedItem.visibility)) {
      setCopyMessage("Только requester-safe материалы можно копировать как ответ пользователю.");
      return;
    }
    await navigator.clipboard?.writeText(buildSafeAnswer(selectedItem, selectedVersion?.body));
    setCopyMessage("Requester-safe ответ скопирован.");
  }

  function selectItem(item: KnowledgeItem) {
    setCopyMessage("");
    setActionMessage("");
    navigate(`/app/knowledge/articles/${encodeURIComponent(item.item_id)}${ticketQuerySuffix}`);
  }

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Support Knowledge"
        title="База знаний поддержки"
        description="Быстрый поиск по requester-safe статьям, support runbook, known error и workaround без админских операций публикации."
      />

      {ticketId ? (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Ticket context</p>
              <p className="font-medium text-slate-900">{ticketId}</p>
            </div>
            <Badge tone="info">support workspace</Badge>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Requester-safe</CardTitle>
            <CardDescription>Можно использовать в ответе</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{requesterSafeCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Internal</CardTitle>
            <CardDescription>Только для поддержки</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{supportInternalCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Runbooks</CardTitle>
            <CardDescription>Операционные шаги</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{runbookCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Known errors</CardTitle>
            <CardDescription>Ошибки и обходы</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{knownErrorCount}</CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_460px]">
        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-4 p-4">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input
                  className="w-full rounded-md border border-slate-200 py-2 pl-9 pr-3 text-sm"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Поиск по статье, runbook, known error"
                  value={query}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                {supportTypes.map((type) => (
                  <Button key={type} onClick={() => setTypeFilter(type)} size="sm" variant={typeFilter === type ? "primary" : "outline"}>
                    {typeLabel(type)}
                  </Button>
                ))}
                <Button onClick={() => setVisibilityFilter("requester_safe")} size="sm" variant={visibilityFilter === "requester_safe" ? "primary" : "outline"}>
                  Requester-safe
                </Button>
                <Button onClick={() => setVisibilityFilter("support_internal")} size="sm" variant={visibilityFilter === "support_internal" ? "primary" : "outline"}>
                  Support internal
                </Button>
                <Button onClick={() => setVisibilityFilter("all")} size="sm" variant={visibilityFilter === "all" ? "primary" : "outline"}>
                  Сброс
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-3" data-testid="support-knowledge-results">
            {filteredItems.map((item) => (
              <button
                className={`w-full rounded-md border p-4 text-left transition hover:border-brand-300 hover:bg-slate-50 ${
                  selectedItem?.item_id === item.item_id ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"
                }`}
                key={item.item_id}
                onClick={() => selectItem(item)}
                type="button"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950">{item.title}</p>
                    <p className="mt-1 text-sm text-slate-600">{item.summary || item.slug}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={itemTypeTone(item.item_type)}>{typeLabel(item.item_type)}</Badge>
                    <Badge tone={visibilityTone(item.visibility)}>{item.visibility}</Badge>
                  </div>
                </div>
              </button>
            ))}
            {!filteredItems.length ? (
              <Card>
                <CardContent className="p-4 text-sm text-slate-500">Ничего не найдено. Проверьте фильтры или запрос.</CardContent>
              </Card>
            ) : null}
          </div>
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                {selectedItem?.title ?? "Статья не выбрана"}
              </CardTitle>
              <CardDescription>{selectedItem?.summary ?? "Выберите материал из списка."}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedItem ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={itemTypeTone(selectedItem.item_type)}>{typeLabel(selectedItem.item_type)}</Badge>
                    <Badge tone={visibilityTone(selectedItem.visibility)}>{selectedItem.visibility}</Badge>
                    <Badge tone="neutral">{selectedItem.status}</Badge>
                  </div>
                  <div className="rounded-md border border-slate-200 p-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Текущая версия</p>
                    <p className="mt-1 text-sm text-slate-700">v{selectedVersion?.version_number ?? selectedItem.current_version?.version_number ?? "draft"}</p>
                    <p className="mt-3 whitespace-pre-wrap text-sm text-slate-800">{selectedVersion?.body || selectedItem.summary || "Текст версии не загружен."}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={copySafeAnswer} size="sm">
                      <ClipboardCheck className="mr-2 h-4 w-4" />
                      Copy-safe answer
                    </Button>
                    <Button
                      disabled={!ticketId || linkMutation.isPending}
                      onClick={() => linkMutation.mutate()}
                      size="sm"
                      title={ticketId ? "Связать статью с текущим тикетом" : "Добавьте ticket_id в URL"}
                      variant="outline"
                    >
                      <Link2 className="mr-2 h-4 w-4" />
                      Связать с тикетом
                    </Button>
                    <Button disabled={supportUsedMutation.isPending} onClick={() => supportUsedMutation.mutate()} size="sm" variant="outline">
                      <ShieldCheck className="mr-2 h-4 w-4" />
                      Отметить использование
                    </Button>
                    <Button disabled={weakArticleMutation.isPending} onClick={() => weakArticleMutation.mutate()} size="sm" variant="outline">
                      <TriangleAlert className="mr-2 h-4 w-4" />
                      Сообщить о слабой статье
                    </Button>
                  </div>
                  {copyMessage ? <p className="text-sm text-slate-600">{copyMessage}</p> : null}
                  {actionMessage ? <p className="text-sm text-slate-600">{actionMessage}</p> : null}
                  <Link className="inline-flex text-sm font-medium text-brand-700 hover:underline" to={`/app/knowledge/articles/${encodeURIComponent(selectedItem.item_id)}${ticketQuerySuffix}`}>
                    Открыть постоянную карточку
                  </Link>
                </>
              ) : (
                <p className="text-sm text-slate-500">Материалы поддержки пока не загрузились.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                Ask debug
              </CardTitle>
              <CardDescription>Preview RAG/Ask policy, retrieval score and source chunks before replying.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="block text-sm font-medium text-slate-700">
                Ask debug query
                <textarea
                  aria-label="Ask debug query"
                  className="mt-1 min-h-24 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  onChange={(event) => setAskDebugQuery(event.target.value)}
                  placeholder="VPN error, MFA token, known error"
                  value={askDebugQuery}
                />
              </label>
              <Button
                disabled={!askDebugQuery.trim() || askDebugMutation.isPending}
                leadingIcon={<Bot className="h-4 w-4" />}
                onClick={() => askDebugMutation.mutate()}
                size="sm"
                variant="outline"
              >
                Проверить Ask
              </Button>

              {askDebugMutation.isError ? <p className="text-sm text-red-700">Не удалось выполнить Ask preview.</p> : null}

              {askDebugMutation.data ? (
                <div className="space-y-4 rounded-md border border-slate-200 p-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={askDebugMutation.data.answer_status === "answered" ? "success" : "warning"}>{askDebugMutation.data.answer_status}</Badge>
                    {askDebugMutation.data.effective_mode ? <Badge tone="info">{askDebugMutation.data.effective_mode}</Badge> : null}
                    <Badge tone={askDebugMutation.data.ai_used ? "success" : "warning"}>{askDebugMutation.data.ai_used ? "AI used" : "AI fallback"}</Badge>
                  </div>
                  <div className="grid gap-2 text-xs text-slate-600">
                    {askDebugMutation.data.fallback_mode ? <p>fallback_mode: {askDebugMutation.data.fallback_mode}</p> : null}
                    {askDebugMutation.data.audit_id ? (
                      <p>
                        audit_id: <code>{askDebugMutation.data.audit_id}</code>
                      </p>
                    ) : null}
                    <p>citations: {askDebugMutation.data.citations?.length ?? 0}</p>
                  </div>
                  <div className="space-y-3">
                    {(askDebugMutation.data.retrieval_results ?? []).map((result, index) => {
                      const firstCitation = result.citations?.[0] ?? {};
                      const chunkId = result.chunk_id ?? firstCitation.chunk_id;
                      const segmentId = result.segment_id ?? firstCitation.segment_id;
                      return (
                        <div className="rounded-md border border-slate-100 bg-slate-50 p-3 text-sm" key={`${result.item?.item_id ?? result.item?.slug ?? index}-${index}`}>
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <p className="font-semibold text-slate-900">{result.item?.title ?? "Knowledge result"}</p>
                              {result.snippet ? <p className="mt-1 text-slate-600">{result.snippet}</p> : null}
                            </div>
                            {typeof result.score === "number" ? <Badge tone="neutral">score {result.score}</Badge> : null}
                          </div>
                          <div className="mt-3 grid gap-1 text-xs text-slate-600">
                            {result.source_mode?.length ? <p>source_mode: {result.source_mode.join(", ")}</p> : null}
                            <p>
                              chunk_id: <code>{citationValue(chunkId)}</code>
                            </p>
                            <p>
                              segment_id: <code>{citationValue(segmentId)}</code>
                            </p>
                            {scorePartEntries(result.score_parts).map((entry) => (
                              <p key={entry}>{entry}</p>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    {!(askDebugMutation.data.retrieval_results ?? []).length ? <p className="text-sm text-slate-500">Retrieval не вернул результатов для debug preview.</p> : null}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Ticket integration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-600">
              <p>Ticket context подключается через параметр ticket_id, чтобы связать статью с тикетом, записать support_used и отметить слабую статью.</p>
              <p>Requester attempts и draft from passport остаются следующим slice.</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Быстрые правила
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-600">
              <p>Requester-safe материалы можно копировать пользователю.</p>
              <p>Support internal runbook, known error и workaround остаются внутренними до публикации через Knowledge Studio.</p>
            </CardContent>
          </Card>
        </aside>
      </div>

      {itemsQuery.isError ? <p className="text-sm text-rose-700">Не удалось загрузить базу знаний поддержки.</p> : null}
    </section>
  );
}
