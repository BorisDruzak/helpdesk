import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, BookOpen, MessageSquarePlus, Search, ThumbsDown, ThumbsUp } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  askKnowledgePortal,
  sendKnowledgeArticleCorrectionRequest,
  sendKnowledgeArticleFeedback,
  type KnowledgeAskResult,
} from "../../features/knowledge/api";

const fieldClass = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const ASK_TICKET_CONTEXT_STORAGE_KEY = "pc_client.knowledge_ask.ticket_context";

function textValue(value: unknown): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function firstCitationValue(result: KnowledgeAskResult, key: "item_id" | "version_id" | "chunk_id" | "segment_id") {
  return textValue(result.citations?.find((citation) => textValue(citation[key]))?.[key]);
}

function primaryRetrievalResult(result: KnowledgeAskResult) {
  return result.retrieval_results?.find((entry) => entry.item?.item_id || entry.item?.slug) ?? null;
}

function primaryVersionId(result: KnowledgeAskResult, primary: ReturnType<typeof primaryRetrievalResult>) {
  return textValue(primary?.version?.version_id) ?? textValue(primary?.item?.current_version_id) ?? firstCitationValue(result, "version_id");
}

function askAnalyticsMetadata(result: KnowledgeAskResult | null, query: string) {
  const primary = result ? primaryRetrievalResult(result) : null;
  const primaryCitation = primary?.citations?.[0] ?? {};
  return {
    source: "knowledge_ask",
    answer_status: result?.answer_status,
    audit_id: result?.audit_id ?? null,
    ai_used: Boolean(result?.ai_used),
    effective_mode: result?.effective_mode ?? null,
    fallback_mode: result?.fallback_mode ?? null,
    query,
    primary_item_id: textValue(primary?.item?.item_id) ?? firstCitationValue(result ?? { status: "ok", answer_status: "" }, "item_id"),
    primary_version_id: result ? primaryVersionId(result, primary) : null,
    primary_chunk_id: textValue(primary?.chunk_id) ?? textValue(primaryCitation.chunk_id) ?? firstCitationValue(result ?? { status: "ok", answer_status: "" }, "chunk_id"),
    primary_segment_id: textValue(primary?.segment_id) ?? textValue(primaryCitation.segment_id) ?? firstCitationValue(result ?? { status: "ok", answer_status: "" }, "segment_id"),
    primary_score: typeof primary?.score === "number" ? primary.score : null,
    citation_count: result?.citations?.length ?? 0,
  };
}

function buildAskTicketContext(result: KnowledgeAskResult | null, query: string) {
  const primary = result ? primaryRetrievalResult(result) : null;
  const metadata = askAnalyticsMetadata(result, query);
  return {
    source: "knowledge_ask",
    query,
    answer_status: result?.answer_status ?? null,
    effective_mode: result?.effective_mode ?? null,
    ai_used: Boolean(result?.ai_used),
    audit_id: result?.audit_id ?? null,
    created_at: new Date().toISOString(),
    primary_item: primary
      ? {
          item_id: textValue(primary.item?.item_id),
          version_id: metadata.primary_version_id,
          slug: textValue(primary.item?.slug),
          title: textValue(primary.item?.title),
          visibility: textValue(primary.item?.visibility),
          chunk_id: metadata.primary_chunk_id,
          segment_id: metadata.primary_segment_id,
          score: metadata.primary_score,
        }
      : null,
    retrieval_results: (result?.retrieval_results ?? []).slice(0, 5).map((entry) => ({
      item_id: textValue(entry.item?.item_id),
      version_id: textValue(entry.version?.version_id) ?? textValue(entry.item?.current_version_id),
      slug: textValue(entry.item?.slug),
      title: textValue(entry.item?.title),
      visibility: textValue(entry.item?.visibility),
      chunk_id: textValue(entry.chunk_id),
      segment_id: textValue(entry.segment_id),
      score: typeof entry.score === "number" ? entry.score : null,
      source_mode: entry.source_mode ?? [],
    })),
    citations: (result?.citations ?? []).slice(0, 5).map((citation) => ({
      ref_id: textValue(citation.ref_id),
      item_id: textValue(citation.item_id),
      version_id: textValue(citation.version_id),
      chunk_id: textValue(citation.chunk_id),
      segment_id: textValue(citation.segment_id),
      title: textValue(citation.title),
    })),
  };
}

function persistAskTicketContext(result: KnowledgeAskResult | null, query: string) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(ASK_TICKET_CONTEXT_STORAGE_KEY, JSON.stringify(buildAskTicketContext(result, query)));
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
}

function statusTone(status: string) {
  if (status === "answered") {
    return "success" as const;
  }
  if (status === "ai_disabled" || status === "provider_unavailable" || status === "policy_blocked") {
    return "warning" as const;
  }
  return "neutral" as const;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    answered: "Ответ подготовлен",
    not_enough_evidence: "Недостаточно материалов",
    ai_disabled: "AI отключён",
    provider_unavailable: "Провайдер недоступен",
    policy_blocked: "Заблокировано политикой",
  };
  return labels[status] ?? status;
}

export function KnowledgePortalAskPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<KnowledgeAskResult | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const askMutation = useMutation({
    mutationFn: () =>
      askKnowledgePortal({
        query: query.trim(),
        surface: "requester_portal",
      }),
    onSuccess: (data) => {
      setResult(data);
      setActionMessage(null);
    },
  });

  const answerActionMutation = useMutation({
    mutationFn: async (payload: { action: "helpful" | "not_helpful" | "correction"; slug: string }) => {
      if (payload.action === "correction") {
        return sendKnowledgeArticleCorrectionRequest(payload.slug, {
          comment: "Requester suggested correction from Knowledge Ask",
        });
      }
      return sendKnowledgeArticleFeedback(payload.slug, {
        helpful: payload.action === "helpful",
        result: payload.action === "helpful" ? "ask_answer_helpful" : "ask_answer_not_helpful",
        metadata: askAnalyticsMetadata(result, query),
      });
    },
    onSuccess: (_data, variables) => {
      setActionMessage(variables.action === "correction" ? "Запрос на исправление отправлен." : "Спасибо за оценку ответа.");
    },
    onError: (_error, variables) => {
      setActionMessage(variables.action === "correction" ? "Не удалось отправить запрос на исправление." : "Не удалось отправить оценку ответа.");
    },
  });

  const retrievalResults = result?.retrieval_results ?? [];
  const citations = result?.citations ?? [];
  const feedbackSlug = retrievalResults.find((entry) => entry.item?.slug)?.item?.slug;
  const answerActions = result ? (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          leadingIcon={<ThumbsUp className="h-4 w-4" />}
          disabled={!feedbackSlug || answerActionMutation.isPending}
          onClick={() => feedbackSlug && answerActionMutation.mutate({ action: "helpful", slug: feedbackSlug })}
        >
          Ответ полезен
        </Button>
        <Button
          variant="outline"
          leadingIcon={<ThumbsDown className="h-4 w-4" />}
          disabled={!feedbackSlug || answerActionMutation.isPending}
          onClick={() => feedbackSlug && answerActionMutation.mutate({ action: "not_helpful", slug: feedbackSlug })}
        >
          Ответ не помог
        </Button>
        <Button
          variant="outline"
          leadingIcon={<MessageSquarePlus className="h-4 w-4" />}
          disabled={!feedbackSlug || answerActionMutation.isPending}
          onClick={() => feedbackSlug && answerActionMutation.mutate({ action: "correction", slug: feedbackSlug })}
        >
          Предложить исправление
        </Button>
        <a
          className="inline-flex h-11 items-center justify-center gap-2 rounded-pill bg-surface-subtle px-4 text-sm font-semibold text-slate-900 shadow-soft hover:bg-brand-50 hover:text-brand-800"
          href="/app/requester/new"
          onClick={() => persistAskTicketContext(result, query)}
        >
          <MessageSquarePlus className="h-4 w-4" />
          Создать обращение
        </a>
      </div>
      {actionMessage ? <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">{actionMessage}</p> : null}
    </div>
  ) : null;

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Portal"
        title="AI-вопрос по базе знаний"
        description="Задайте вопрос и получите ответ с источниками, если AI-ответы включены. Без AI будут показаны результаты поиска."
      />

      <Card>
        <CardContent className="p-4">
          <div className="space-y-3">
            <label className="block text-sm font-medium">
              Вопрос
              <textarea
                aria-label="Вопрос"
                className={`${fieldClass} mt-1 min-h-28 resize-y`}
                placeholder="Например: как восстановить доступ к VPN?"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <Button
              leadingIcon={<Bot className="h-4 w-4" />}
              disabled={!query.trim() || askMutation.isPending}
              onClick={() => askMutation.mutate()}
            >
              Спросить
            </Button>
          </div>
        </CardContent>
      </Card>

      {askMutation.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          AI-вопрос временно недоступен. Попробуйте поиск или создайте обращение.
        </div>
      ) : null}

      {result ? (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {result.display_message ? <span className="font-medium text-slate-900">{result.display_message}</span> : null}
            <Badge tone={statusTone(result.answer_status)}>{statusLabel(result.answer_status)}</Badge>
            <Badge tone={result.ai_used ? "success" : "warning"}>{result.ai_used ? "AI использовался" : "AI не использовался"}</Badge>
            {result.effective_mode ? <Badge>{result.effective_mode}</Badge> : null}
          </div>

          {result.answer ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Bot className="h-5 w-5" />
                  Ответ
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{result.answer}</p>
                  {answerActions}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {!result.answer ? (
            <Card>
              <CardContent className="p-4">{answerActions}</CardContent>
            </Card>
          ) : null}

          {citations.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Источники</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm text-slate-600">
                {citations.map((citation, index) => (
                  <div key={citation.ref_id ?? `${citation.title}-${index}`} className="rounded-md border border-slate-200 p-3">
                    <p className="font-semibold text-slate-900">[{index + 1}] {citation.title ?? "Источник"}</p>
                    {citation.snippet ? <p className="mt-1">{citation.snippet}</p> : null}
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}

          {retrievalResults.length ? (
            <div className="grid gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Search className="h-4 w-4" />
                Результаты поиска
              </div>
              {retrievalResults.map((entry, index) => (
                <Card key={entry.item?.item_id ?? entry.item?.slug ?? `${entry.item?.title}-${index}`}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <BookOpen className="h-5 w-5" />
                      {entry.item?.title ?? "Материал базы знаний"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-slate-600">
                    {entry.snippet || entry.item?.summary ? <p>{entry.snippet ?? entry.item?.summary}</p> : null}
                    {entry.item?.visibility ? <Badge>{entry.item.visibility}</Badge> : null}
                    {entry.item?.slug ? <p className="text-xs text-slate-500">slug: {entry.item.slug}</p> : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              В базе знаний не найдено подходящих материалов. Создайте обращение, если нужна помощь специалиста.
            </div>
          )}
        </section>
      ) : null}
    </section>
  );
}
