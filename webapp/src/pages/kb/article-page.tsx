import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bookmark, CheckCircle2, MessageSquarePlus, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  fetchKnowledgePortalArticle,
  sendKnowledgeArticleCorrectionRequest,
  sendKnowledgeArticleFeedback,
  setKnowledgePortalBookmark,
  type KnowledgePortalArticle,
} from "../../features/knowledge/api";

const linkButtonClass =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 hover:border-brand-200 hover:bg-brand-50";

function extractToc(body?: string | null) {
  return String(body || "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("#"))
    .map((line) => line.replace(/^#+\s*/, "").trim())
    .filter(Boolean)
    .slice(0, 12);
}

function ArticleContent({ data }: { data: KnowledgePortalArticle }) {
  const { article, version } = data;
  const toc = extractToc(version.body);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);

  async function runArticleAction(action: () => Promise<unknown>, successMessage: string, errorMessage: string) {
    setActionPending(true);
    setActionMessage(successMessage);
    try {
      await action();
    } catch {
      setActionMessage(errorMessage);
    } finally {
      setActionPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {(article.tags ?? []).map((tag) => (
          <Badge key={tag}>{tag}</Badge>
        ))}
        {article.visibility ? <Badge tone="success">{article.visibility}</Badge> : null}
        {article.review_due_at ? <Badge tone="warning">Проверить до {new Date(article.review_due_at).toLocaleDateString("ru-RU")}</Badge> : null}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <article className="space-y-4">
          <Card>
            <CardContent className="p-6">
              <div className="prose max-w-none whitespace-pre-wrap text-sm leading-7 text-slate-800">{version.body}</div>
            </CardContent>
          </Card>

          {data.segments.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Сегменты и цитаты</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {data.segments.map((segment) => (
                  <div key={segment.segment_id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                    <h2 className="font-semibold text-slate-950">{segment.title}</h2>
                    {segment.text ? <p className="mt-1 leading-6 text-slate-600">{segment.text}</p> : null}
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </article>

        <aside className="space-y-4">
          {toc.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Содержание</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2 text-sm text-slate-600">
                  {toc.map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Действия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  leadingIcon={<ThumbsUp className="h-4 w-4" />}
                  disabled={actionPending}
                  onClick={() =>
                    void runArticleAction(
                      () => sendKnowledgeArticleFeedback(article.slug, { helpful: true }),
                      "Спасибо за оценку.",
                      "Не удалось отправить оценку.",
                    )
                  }
                >
                  Полезно
                </Button>
                <Button
                  variant="outline"
                  leadingIcon={<ThumbsDown className="h-4 w-4" />}
                  disabled={actionPending}
                  onClick={() =>
                    void runArticleAction(
                      () => sendKnowledgeArticleFeedback(article.slug, { helpful: false }),
                      "Спасибо за оценку.",
                      "Не удалось отправить оценку.",
                    )
                  }
                >
                  Не помогло
                </Button>
              </div>
              <Button
                className="w-full"
                variant="outline"
                leadingIcon={<MessageSquarePlus className="h-4 w-4" />}
                disabled={actionPending}
                onClick={() =>
                  void runArticleAction(
                    () => sendKnowledgeArticleCorrectionRequest(article.slug, { comment: "Requester suggested article correction from portal" }),
                    "Запрос на исправление отправлен.",
                    "Не удалось отправить запрос на исправление.",
                  )
                }
              >
                Предложить исправление
              </Button>
              <Button
                className="w-full"
                variant="outline"
                leadingIcon={<Bookmark className="h-4 w-4" />}
                disabled={actionPending}
                onClick={() =>
                  void runArticleAction(
                    () => setKnowledgePortalBookmark(article.slug),
                    "Статья добавлена в закладки.",
                    "Не удалось добавить статью в закладки.",
                  )
                }
              >
                В закладки
              </Button>
              <Link className={`${linkButtonClass} w-full`} to="/app/requester/new">
                Создать обращение
              </Link>
              {actionMessage ? <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">{actionMessage}</p> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Свежесть</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-600">
              {article.owner_actor_id ? <p>Владелец: {article.owner_actor_id}</p> : null}
              {article.updated_at ? <p>Обновлено: {new Date(article.updated_at).toLocaleDateString("ru-RU")}</p> : null}
              {version.published_at ? <p>Опубликовано: {new Date(version.published_at).toLocaleDateString("ru-RU")}</p> : null}
              <p className="flex items-center gap-2 text-slate-700">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Материал опубликован для портала.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

export function KnowledgePortalArticlePage() {
  const { slug = "" } = useParams();
  const query = useQuery({
    queryKey: ["knowledge-portal-article", slug],
    queryFn: () => fetchKnowledgePortalArticle(slug),
    enabled: Boolean(slug),
  });

  return (
    <section className="space-y-6">
      <Link className={linkButtonClass} to="/app/kb">
        <ArrowLeft className="h-4 w-4" />
        База знаний
      </Link>

      {query.isLoading ? <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">Загружаем статью...</div> : null}
      {query.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Статья не найдена или недоступна для портала.
        </div>
      ) : null}
      {query.data ? (
        <>
          <PageHeading
            eyebrow="Knowledge Portal"
            title={query.data.article.title}
            description={query.data.article.summary ?? "Опубликованная статья базы знаний"}
          />
          <ArticleContent data={query.data} />
        </>
      ) : null}
    </section>
  );
}
