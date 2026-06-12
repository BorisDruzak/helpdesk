import { useQuery } from "@tanstack/react-query";
import { BookOpen, Bot, Clock, FolderOpen, Search, Star } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { fetchKnowledgePortalHome, type KnowledgeItem, type KnowledgePortalHome } from "../../features/knowledge/api";

const linkButtonClass =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 hover:border-brand-200 hover:bg-brand-50";

function ArticleCard({ article }: { article: KnowledgeItem }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 transition-colors hover:border-brand-200 hover:bg-brand-50">
      <div className="flex items-start gap-3">
        <BookOpen className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" />
        <div className="min-w-0 space-y-2">
          <Link className="text-base font-semibold text-slate-950 hover:text-brand-700" to={`/app/kb/articles/${encodeURIComponent(article.slug)}`}>
            {article.title}
          </Link>
          {article.summary ? <p className="text-sm leading-6 text-slate-600">{article.summary}</p> : null}
          <div className="flex flex-wrap gap-2">
            {article.visibility ? <Badge>{article.visibility}</Badge> : null}
            {(article.tags ?? []).slice(0, 3).map((tag) => (
              <Link key={tag} className="inline-flex" to={`/app/kb/tags/${encodeURIComponent(tag)}`}>
                <Badge tone="neutral">{tag}</Badge>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ArticlesSection({
  articles,
  emptyText,
  icon,
  title,
}: {
  articles: KnowledgeItem[];
  emptyText: string;
  icon: ReactNode;
  title: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        {icon}
        {title}
      </div>
      {articles.length ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {articles.map((article) => (
            <ArticleCard key={article.item_id ?? article.slug} article={article} />
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">{emptyText}</div>
      )}
    </section>
  );
}

function PortalContent({ data }: { data: KnowledgePortalHome }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <Link className={linkButtonClass} to="/app/kb/search">
          <Search className="h-4 w-4" />
          Поиск
        </Link>
        <Link className={linkButtonClass} to="/app/kb/ask">
          <Bot className="h-4 w-4" />
          AI-вопрос
        </Link>
        <Link className={linkButtonClass} to="/app/requester/new">
          Создать обращение
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5" />
            Пространства
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.spaces.length ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {data.spaces.map((space) => (
                <Link
                  key={space.space_id ?? space.code}
                  className="block rounded-md border border-slate-200 bg-white p-4 transition-colors hover:border-brand-200 hover:bg-brand-50"
                  to={`/app/kb/spaces/${encodeURIComponent(space.code)}`}
                >
                  <h2 className="text-base font-semibold text-slate-950">{space.title}</h2>
                  {space.description ? <p className="mt-2 text-sm leading-6 text-slate-600">{space.description}</p> : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge>{space.visibility}</Badge>
                    <Badge tone="success">{space.lifecycle_status}</Badge>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Активные пространства пока не опубликованы.</p>
          )}
        </CardContent>
      </Card>

      <ArticlesSection
        articles={data.featured_articles}
        emptyText="Рекомендованные статьи пока не опубликованы."
        icon={<BookOpen className="h-4 w-4" />}
        title="Рекомендуемые статьи"
      />
      <ArticlesSection
        articles={data.popular_articles}
        emptyText="Популярные статьи пока не накопили сигналы."
        icon={<Star className="h-4 w-4" />}
        title="Популярные"
      />
      <ArticlesSection
        articles={data.recent_articles}
        emptyText="Недавно обновленные статьи пока не опубликованы."
        icon={<Clock className="h-4 w-4" />}
        title="Недавно обновленные"
      />
    </div>
  );
}

export function KnowledgePortalHomePage() {
  const query = useQuery({
    queryKey: ["knowledge-portal-home"],
    queryFn: fetchKnowledgePortalHome,
  });

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Portal"
        title="База знаний"
        description="Найдите инструкции, решения и ответы без создания обращения."
      />

      {query.isLoading ? <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">Загружаем портал базы знаний...</div> : null}
      {query.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Портал базы знаний временно недоступен. Попробуйте поиск или создайте обращение.
        </div>
      ) : null}
      {query.data ? <PortalContent data={query.data} /> : null}
    </section>
  );
}
