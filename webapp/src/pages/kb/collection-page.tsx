import { useQuery } from "@tanstack/react-query";
import { BookOpen, FolderOpen, Tag } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { PageHeading } from "../../components/ui/page-heading";
import { fetchKnowledgePortalCollection, type KnowledgeItem } from "../../features/knowledge/api";

function ArticleCard({ article }: { article: KnowledgeItem }) {
  return (
    <Link
      className="block rounded-md border border-slate-200 bg-white p-4 transition-colors hover:border-brand-200 hover:bg-brand-50"
      to={`/app/kb/articles/${encodeURIComponent(article.slug)}`}
    >
      <div className="flex items-start gap-3">
        <BookOpen className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" />
        <div className="min-w-0 space-y-2">
          <h2 className="text-base font-semibold text-slate-950">{article.title}</h2>
          {article.summary ? <p className="text-sm leading-6 text-slate-600">{article.summary}</p> : null}
          <div className="flex flex-wrap gap-2">
            {article.visibility ? <Badge>{article.visibility}</Badge> : null}
            {(article.tags ?? []).slice(0, 3).map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
}

export function KnowledgePortalCollectionPage() {
  const { spaceCode, tag } = useParams();
  const collectionType = spaceCode ? "space" : "tag";
  const code = spaceCode ?? tag ?? "";
  const query = useQuery({
    queryKey: ["knowledge-portal-collection", collectionType, code],
    queryFn: () => fetchKnowledgePortalCollection(collectionType, code),
    enabled: Boolean(code),
  });

  const icon = collectionType === "space" ? <FolderOpen className="h-5 w-5" /> : <Tag className="h-5 w-5" />;

  return (
    <section className="space-y-6">
      {query.data ? (
        <PageHeading
          eyebrow="Knowledge Portal"
          title={query.data.title}
          description={query.data.description ?? (collectionType === "space" ? "Раздел базы знаний" : "Статьи с выбранным тегом")}
        />
      ) : (
        <PageHeading
          eyebrow="Knowledge Portal"
          title={collectionType === "space" ? "Раздел базы знаний" : "Тег базы знаний"}
          description="Загружаем опубликованные статьи портала."
        />
      )}

      <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        {icon}
        {collectionType === "space" ? "Раздел" : "Тег"}: {code}
      </div>

      {query.isLoading ? <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">Загружаем статьи...</div> : null}
      {query.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Раздел не найден или недоступен для портала.
        </div>
      ) : null}
      {query.data ? (
        query.data.articles.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {query.data.articles.map((article) => (
              <ArticleCard key={article.item_id ?? article.slug} article={article} />
            ))}
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            В этом разделе пока нет опубликованных статей.
          </div>
        )
      ) : null}
    </section>
  );
}
